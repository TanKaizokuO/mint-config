#!/usr/bin/env python3
"""NetworkManager Wi-Fi backend (libnm over GObject, asynchronous on the GLib main loop).

Supported: open, WPA/WPA2-Personal and WPA3-SAE networks; saved profiles of any
kind are activated as stored (enterprise profiles only work when NetworkManager
already holds their credentials). Not supported: creating WEP, OWE,
802.1X/enterprise or hidden-SSID profiles -- those yield an explicit error that
points at nm-connection-editor / nmtui instead of pretending to work.

Credentials: a typed password lives only in process memory and is passed to
NetworkManager over D-Bus inside the connection settings (new networks) or via a
secret agent reply (saved profiles that need secrets). NM itself persists
system-owned secrets in its own profile storage; this module never writes
files, logs, or puts secrets in process arguments. The agent is registered
lazily, only for secured connects, answers only while a user-initiated connect
is running, and never persists agent-owned secrets (they are asked for again).
A newly added profile is blocked from autoconnect until explicitly activated.
Failed/cancelled attempts roll back only their own never-activated profile.
Cancellation and close drain late add/activate replies, deactivate unfinished
attempts, and await deletion with an independent cleanup cancellable. Successful
and pre-existing profiles are never deleted. close(done=None) notifies callers
only after outstanding callbacks and agent teardown have completed; keep the
GLib main loop alive until then. snapshot()['prompt'] is the current token or ''.

Signals: 'changed', 'error'(str), 'password-requested'(token, ssid).
`security` values: open, wpa, wpa2, wpa3, wpa2/wpa3 (password-capable),
owe, wep, enterprise, unsupported.
"""

import dataclasses
import os
import secrets
from typing import Callable, Optional

import gi

gi.require_version("NM", "1.0")
from gi.repository import Gio, GLib, GObject, NM  # noqa: E402

_SEC = getattr(NM, "80211ApSecurityFlags")
_APF = getattr(NM, "80211ApFlags")
_MODE = getattr(NM, "80211Mode")
_K_PSK = int(_SEC.KEY_MGMT_PSK)
_K_SAE = int(_SEC.KEY_MGMT_SAE)
_K_EAP = int(_SEC.KEY_MGMT_802_1X) | int(_SEC.KEY_MGMT_EAP_SUITE_B_192)
_K_OWE = int(_SEC.KEY_MGMT_OWE) | int(_SEC.KEY_MGMT_OWE_TM)
_PRIVACY = int(_APF.PRIVACY)

_DEV_ACTIVATED = int(NM.DeviceState.ACTIVATED)
_DEV_UNMANAGED = int(NM.DeviceState.UNMANAGED)
_DEV_DISCONNECTED = int(NM.DeviceState.DISCONNECTED)
_AC_ACTIVATED = int(NM.ActiveConnectionState.ACTIVATED)
_AC_DEACTIVATED = int(NM.ActiveConnectionState.DEACTIVATED)
_R = NM.ActiveConnectionStateReason

_PASSWORD_SECURITY = ("wpa", "wpa2", "wpa3", "wpa2/wpa3")
_SCAN_TIMEOUT_S = 15
_CHANGED_DEBOUNCE_MS = 60

_NM_BUS = "org.freedesktop.NetworkManager"
_AGENT_ID = f"org.omp.waybar.wifi.p{os.getpid()}"
_AGENT_PATH = "/org/freedesktop/NetworkManager/SecretAgent"
_AGENT_IFACE = "org.freedesktop.NetworkManager.SecretAgent"
_AGENT_MANAGER_PATH = "/org/freedesktop/NetworkManager/AgentManager"
_AGENT_MANAGER_IFACE = "org.freedesktop.NetworkManager.AgentManager"
_AGENT_XML = """
<node><interface name="org.freedesktop.NetworkManager.SecretAgent">
  <method name="GetSecrets">
    <arg type="a{sa{sv}}" name="connection" direction="in"/>
    <arg type="o" name="connection_path" direction="in"/>
    <arg type="s" name="setting_name" direction="in"/>
    <arg type="as" name="hints" direction="in"/>
    <arg type="u" name="flags" direction="in"/>
    <arg type="a{sa{sv}}" name="secrets" direction="out"/>
  </method>
  <method name="CancelGetSecrets">
    <arg type="o" name="connection_path" direction="in"/>
    <arg type="s" name="setting_name" direction="in"/>
  </method>
  <method name="SaveSecrets">
    <arg type="a{sa{sv}}" name="connection" direction="in"/>
    <arg type="o" name="connection_path" direction="in"/>
  </method>
  <method name="DeleteSecrets">
    <arg type="a{sa{sv}}" name="connection" direction="in"/>
    <arg type="o" name="connection_path" direction="in"/>
  </method>
</interface></node>
"""

_FAILURE_TEXT = {
    int(_R.LOGIN_FAILED): "Authentication failed. The password is probably wrong.",
    int(_R.NO_SECRETS): "NetworkManager has no password for this network.",
    int(_R.CONNECT_TIMEOUT): "Connecting timed out.",
    int(_R.IP_CONFIG_INVALID): "The network did not provide a usable IP configuration.",
    int(_R.DEVICE_DISCONNECTED): "The Wi-Fi device was disconnected during connecting.",
    int(_R.USER_DISCONNECTED): "The connection was deactivated by another program.",
    int(_R.CONNECTION_REMOVED): "The connection profile was removed during connecting.",
    int(_R.DEVICE_REMOVED): "The Wi-Fi device was removed.",
    int(_R.SERVICE_STOPPED): "NetworkManager stopped.",
}


def _is_cancelled(err: GLib.Error) -> bool:
    return err.matches(Gio.io_error_quark(), int(Gio.IOErrorEnum.CANCELLED))


def _is_permission_error(err: GLib.Error) -> bool:
    for enum in (NM.ManagerError, NM.SettingsError, NM.AgentManagerError):
        if err.domain == GLib.quark_to_string(enum.quark()) and err.code == 1:
            return True
    return "not authorized" in err.message.lower() or "permission" in err.message.lower()


def _describe(err: GLib.Error, what: str) -> str:
    if _is_permission_error(err):
        return (f"NetworkManager refused permission to {what}. Check this account's "
                "network permissions (polkit) or use nm-connection-editor.")
    return f"Could not {what}: {err.message}"


def _classify(ap: "NM.AccessPoint") -> str:
    both = int(ap.get_wpa_flags()) | int(ap.get_rsn_flags())
    psk, sae = bool(both & _K_PSK), bool(both & _K_SAE)
    if sae and psk:
        return "wpa2/wpa3"
    if sae:
        return "wpa3"
    if psk:
        return "wpa2" if int(ap.get_rsn_flags()) & _K_PSK else "wpa"
    if both & _K_EAP:
        return "enterprise"
    if both & _K_OWE:
        return "owe"
    if both:
        return "unsupported"
    return "wep" if int(ap.get_flags()) & _PRIVACY else "open"


def _check_password(key_mgmt: str, password: str) -> Optional[str]:
    if not password:
        return "Enter a password."
    if key_mgmt == "wpa-psk" and not NM.utils_wpa_psk_valid(password):
        return "A WPA passphrase must be 8-63 characters (or 64 hex digits)."
    return None


@dataclasses.dataclass
class _Entry:
    id: str
    ssid: bytes
    name: str
    security: str
    strength: int
    active: bool
    aps: list
    profile: Optional["NM.RemoteConnection"] = None
    profile_ap: Optional["NM.AccessPoint"] = None

    def public(self) -> dict:
        return {"id": self.id, "ssid": self.name, "strength": self.strength,
                "security": self.security, "active": self.active,
                "saved": self.profile is not None}


@dataclasses.dataclass
class _Action:
    entry: _Entry
    device: "NM.DeviceWifi"
    password: Optional[str] = None  # one-shot answer for a saved profile
    key_mgmt: str = ""
    ac: Optional["NM.ActiveConnection"] = None
    ac_handler: int = 0
    created: Optional["NM.RemoteConnection"] = None
    cancelled: bool = False
    expected_path: str = ""
    pending: bool = False
    succeeded: bool = False
    cleaning: bool = False
    rollback_done: bool = False
    cleanup_cancel: Optional[Gio.Cancellable] = None
    device_handler: int = 0


@dataclasses.dataclass
class _Prompt:
    token: str
    kind: str  # "new" (we build the profile) or "agent" (NM asked for secrets)
    key_mgmt: str
    invocation: Optional[Gio.DBusMethodInvocation] = None
    conn_path: str = ""
    setting_name: str = ""


class WifiBackend(GObject.Object):
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "error": (GObject.SignalFlags.RUN_LAST, None, (str,)),
        "password-requested": (GObject.SignalFlags.RUN_LAST, None, (str, str)),
    }

    def __init__(self):
        super().__init__()
        self._closed = False
        self._pending = 0
        self._close_callbacks: list = []
        self._close_complete = False
        self._client: Optional[NM.Client] = None
        self._cancel = Gio.Cancellable()
        self._handlers: list = []  # (object, handler id) on the client / active connection
        self._dev_handlers: dict = {}  # device -> [handler ids]
        self._changed_source = 0
        self._op: Optional[str] = None  # "connect" | "disconnect" | "toggle"
        self._action: Optional[_Action] = None
        self._prompts: dict = {}
        self._scanning = False
        self._scan_dev = None
        self._scan_baseline = 0
        self._scan_timeout = 0
        self._agent_conn: Optional[Gio.DBusConnection] = None
        self._agent_reg_id = 0
        self._agent_registered = False
        self._agent_owner = ""
        self._agent_registering = False
        self._agent_waiters: list = []
        self._init_pending = True
        self._refresh_after_init = False
        NM.Client.new_async(self._cancel, self._track(self._on_client_ready))

    # ------------------------------------------------------------------ public

    def snapshot(self) -> dict:
        client = self._client
        snap = {"available": False, "enabled": False, "busy": self._op is not None,
                "scanning": self._scanning, "active_ssid": "", "networks": [],
                "prompt": next(iter(self._prompts), "")}
        if self._closed or client is None or not client.get_nm_running():
            return snap
        dev = self._device()
        if dev is None:
            return snap
        snap["available"] = True
        snap["enabled"] = self._radio_enabled()
        if snap["enabled"]:
            entries = self._entries(dev)
            snap["networks"] = [e.public() for e in entries]
            snap["active_ssid"] = next((e.name for e in entries if e.active), "")
        return snap

    def set_enabled(self, enabled: bool) -> None:
        if not self._begin("toggle"):
            return
        client = self._client
        if enabled and not client.wireless_hardware_get_enabled():
            self._fail_op("Wi-Fi is blocked by a hardware switch (rfkill).")
            return
        if bool(client.wireless_get_enabled()) == bool(enabled):
            self._end_op()
            return
        if not enabled:
            self._stop_scan()
        client.dbus_set_property(
            NM.DBUS_PATH, NM.DBUS_INTERFACE, "WirelessEnabled",
            GLib.Variant("b", bool(enabled)), -1, self._cancel,
            self._track(lambda c, res: self._on_toggle_done(res, bool(enabled))))

    def refresh(self) -> None:
        if self._closed or self._scanning:
            return
        if self._init_pending:
            self._refresh_after_init = True
            return
        if not self._client_ready():
            return
        if self._op is not None:
            self._error("Another Wi-Fi action is still in progress.")
            return
        dev = self._device()
        if dev is None:
            self._error("No Wi-Fi adapter is available.")
            return
        if not self._radio_enabled():
            self._error("Wi-Fi is turned off.")
            return
        self._scanning = True
        self._scan_dev = dev
        self._scan_baseline = dev.get_last_scan()
        self._scan_timeout = GLib.timeout_add_seconds(_SCAN_TIMEOUT_S, self._on_scan_timeout)
        dev.request_scan_async(self._cancel, self._track(self._on_scan_requested))
        self._schedule_changed()

    def connect(self, network_id, password: Optional[str] = None, *extra):
        """Wi-Fi connect. A callable second argument means plain GObject signal connect."""
        if callable(password):
            return GObject.Object.connect(self, network_id, password, *extra)
        if not self._begin("connect"):
            return
        dev = self._device()
        if dev is None:
            self._fail_op("No Wi-Fi adapter is available.")
            return
        if not self._radio_enabled():
            self._fail_op("Wi-Fi is turned off.")
            return
        entry = next((e for e in self._entries(dev) if e.id == network_id), None)
        if entry is None:
            self._fail_op("That network is no longer in range. Refresh and try again.")
            return
        if entry.active:
            self._end_op()
            return
        act = _Action(entry=entry, device=dev,
                      expected_path=entry.profile.get_path() if entry.profile is not None else "")
        self._action = act
        sec = entry.security
        if entry.profile is not None:
            act.password = password if sec in _PASSWORD_SECURITY else None
            self._launch(act, None)
        elif sec == "open":
            self._launch(act, self._build_profile(entry, None, ""))
        elif sec in _PASSWORD_SECURITY:
            act.key_mgmt = "wpa-psk" if "wpa2" in sec or sec == "wpa" else "sae"
            if password is None:
                self._prompt(act, _Prompt(secrets.token_urlsafe(9), "new", act.key_mgmt))
            else:
                self._submit_new(act, password)
        else:
            self._fail_action(
                f"{entry.name}: {sec} networks cannot be set up here. Create the profile in "
                "nm-connection-editor (or nmtui), then connect from this list.")

    def disconnect(self, *handler_id):
        """Wi-Fi disconnect. Any argument means plain GObject handler disconnect."""
        if handler_id:
            return GObject.Object.disconnect(self, *handler_id)
        if not self._begin("disconnect"):
            return
        dev = self._device()
        if dev is None or int(dev.get_state()) <= _DEV_DISCONNECTED:
            self._fail_op("Wi-Fi is not connected.")
            return
        dev.disconnect_async(self._cancel, self._track(self._on_disconnect_done))

    def submit_password(self, token: str, password: Optional[str]) -> None:
        prompt = self._prompts.get(token)
        if prompt is None:
            if password is not None:
                self._error("No password request is pending.")
            return
        act = self._action
        if password is None:
            del self._prompts[token]
            self._cancel_prompt(prompt, act)
            self.emit("changed")
            return
        problem = _check_password(prompt.key_mgmt, password)
        if problem:
            self._error(problem)
            if token in self._prompts and not self._closed:
                self.emit("password-requested", prompt.token, act.entry.name if act else "")
            return
        del self._prompts[token]
        if prompt.kind == "new":
            self._submit_new(act, password)
        else:
            reply = GLib.Variant("(a{sa{sv}})", ({prompt.setting_name: {
                "psk": GLib.Variant("s", password)}},))
            prompt.invocation.return_value(reply)
        self.emit("changed")

    def close(self, done: Optional[Callable[[], None]] = None) -> None:
        if done is not None:
            if self._close_complete:
                done()
                return
            self._close_callbacks.append(done)
        if self._closed:
            return
        self._closed = True
        self._clear_prompts("UserCanceled", "The Wi-Fi popup was closed.")
        if self._action is not None:
            self._action.cancelled = True
            self._end_action()
        self._cancel.cancel()
        for source in (self._scan_timeout, self._changed_source):
            if source:
                GLib.source_remove(source)
        self._scan_timeout = self._changed_source = 0
        for obj, hid in self._handlers:
            obj.disconnect(hid)
        self._handlers.clear()
        for dev, ids in self._dev_handlers.items():
            for hid in ids:
                GObject.Object.disconnect(dev, hid)
        self._dev_handlers.clear()
        self._unregister_agent()
        self._maybe_closed()

    def _track(self, callback):
        """Hold close completion until this asynchronous callback is consumed."""
        self._pending += 1

        def finished(*args):
            try:
                callback(*args)
            finally:
                self._pending -= 1
                self._maybe_closed()

        return finished

    def _unregister_agent(self) -> None:
        conn = self._agent_conn
        if conn is not None and self._agent_registered:
            self._agent_registered = False
            owner, self._agent_owner = self._agent_owner, ""
            conn.call(owner, _AGENT_MANAGER_PATH, _AGENT_MANAGER_IFACE, "Unregister",
                      None, None, Gio.DBusCallFlags.NONE, -1, None,
                      self._track(self._on_agent_unregistered))

    def _on_agent_unregistered(self, conn, res) -> None:
        try:
            conn.call_finish(res)
        except GLib.Error:
            pass  # NM also drops registration when its owner disappears.

    def _maybe_closed(self) -> None:
        if (not self._closed or self._close_complete or self._pending
                or self._action is not None):
            return
        if self._agent_conn is not None and self._agent_reg_id:
            self._agent_conn.unregister_object(self._agent_reg_id)
        self._agent_conn = None
        self._agent_reg_id = 0
        self._agent_waiters.clear()
        self._client = None
        self._op = None
        self._close_complete = True
        callbacks, self._close_callbacks = self._close_callbacks, []
        for callback in callbacks:
            callback()

    # ------------------------------------------------------------ client setup

    def _on_client_ready(self, _src, res) -> None:
        self._init_pending = False
        try:
            client = NM.Client.new_finish(res)
        except GLib.Error as err:
            if not self._closed and not _is_cancelled(err):
                self._error(f"Cannot reach NetworkManager: {err.message}")
            return
        if self._closed:
            return
        self._client = client
        for sig, cb in (
            ("notify::nm-running", self._on_nm_running),
            ("notify::wireless-enabled", self._on_any),
            ("notify::wireless-hardware-enabled", self._on_any),
            ("notify::active-connections", self._on_any),
            ("connection-added", self._on_any),
            ("connection-removed", self._on_any),
            ("device-added", self._on_device_added),
            ("device-removed", self._on_device_removed),
        ):
            self._handlers.append((client, client.connect(sig, cb)))
        for dev in client.get_devices():
            self._watch_device(dev)
        if not client.get_nm_running():
            self._error("NetworkManager is not running.")
        self._schedule_changed()
        if self._refresh_after_init:
            self._refresh_after_init = False
            self.refresh()

    def _client_ready(self) -> bool:
        if self._client is None or not self._client.get_nm_running():
            self._error("NetworkManager is not available.")
            return False
        return True

    def _watch_device(self, dev) -> None:
        if not isinstance(dev, NM.DeviceWifi) or dev in self._dev_handlers:
            return
        self._dev_handlers[dev] = [
            dev.connect("notify::state", self._on_any),
            dev.connect("notify::active-access-point", self._on_any),
            dev.connect("notify::last-scan", self._on_last_scan),
            dev.connect("access-point-added", self._on_any),
            dev.connect("access-point-removed", self._on_any),
        ]

    def _on_device_added(self, _client, dev) -> None:
        self._watch_device(dev)
        self._schedule_changed()

    def _on_device_removed(self, _client, dev) -> None:
        for hid in self._dev_handlers.pop(dev, []):
            GObject.Object.disconnect(dev, hid)
        if dev is self._scan_dev:
            self._stop_scan()
        self._schedule_changed()

    def _on_nm_running(self, *_args) -> None:
        if not self._client.get_nm_running():
            # NM lost its state, including our agent registration and any activation.
            self._agent_registered = False
            self._agent_owner = ""
            self._stop_scan()
            self._clear_prompts("AgentCanceled", "NetworkManager stopped.")
            if self._action is not None:
                self._action.cancelled = True
                self._end_action()
            elif self._op is not None:
                self._end_op()
        self._schedule_changed()

    def _on_any(self, *_args) -> None:
        self._schedule_changed()

    def _schedule_changed(self) -> None:
        if self._closed or self._changed_source:
            return
        self._changed_source = GLib.timeout_add(_CHANGED_DEBOUNCE_MS, self._emit_changed)

    def _emit_changed(self) -> bool:
        self._changed_source = 0
        if self._closed:
            return False
        if self._scanning and (self._scan_dev is None or not self._radio_enabled()):
            self._stop_scan(emit=False)
        self.emit("changed")
        return False

    def _error(self, message: str) -> None:
        if not self._closed:
            self.emit("error", message)

    # ------------------------------------------------------------ state helpers

    def _radio_enabled(self) -> bool:
        c = self._client
        return bool(c.wireless_get_enabled() and c.wireless_hardware_get_enabled())

    def _device(self):
        devs = [d for d in self._client.get_devices()
                if isinstance(d, NM.DeviceWifi) and int(d.get_state()) != _DEV_UNMANAGED]
        return min(devs, key=lambda d: int(d.get_state()) != _DEV_ACTIVATED) if devs else None

    def _entries(self, dev) -> list:
        profiles = [c for c in self._client.get_connections()
                    if c.is_type(NM.SETTING_WIRELESS_SETTING_NAME)
                    and c.get_setting_wireless() is not None
                    and c.get_setting_wireless().get_mode() in (None, "infrastructure")]
        active_ap = dev.get_active_access_point() if int(dev.get_state()) == _DEV_ACTIVATED else None
        active_path = active_ap.get_path() if active_ap is not None else None
        groups: dict = {}
        for ap in dev.get_access_points():
            raw = ap.get_ssid()
            ssid = bytes(raw.get_data()) if raw is not None else b""
            if not ssid.strip(b"\0") or int(ap.get_mode()) != int(_MODE.INFRA):
                continue
            groups.setdefault((ssid, _classify(ap)), []).append(ap)
        entries = []
        for (ssid, sec), aps in groups.items():
            aps.sort(key=lambda a: a.get_strength(), reverse=True)
            entry = _Entry(id=f"{ssid.hex()}/{sec}", ssid=ssid, name=NM.utils_ssid_to_utf8(ssid),
                           security=sec, strength=int(aps[0].get_strength()), aps=aps,
                           active=any(a.get_path() == active_path for a in aps))
            for ap in aps:
                valid = [p for p in profiles if ap.connection_valid(p)]
                if valid:
                    entry.profile = max(
                        valid, key=lambda p: p.get_setting_connection().get_timestamp())
                    entry.profile_ap = ap
                    break
            entries.append(entry)
        entries.sort(key=lambda e: (not e.active, -e.strength, e.name.lower()))
        return entries

    # ------------------------------------------------------------ busy / ops

    def _begin(self, op: str) -> bool:
        if self._closed or not self._client_ready():
            return False
        if self._op is not None:
            self._error("Another Wi-Fi action is still in progress.")
            return False
        self._op = op
        self._schedule_changed()
        return True

    def _end_op(self) -> None:
        self._op = None
        self._schedule_changed()

    def _fail_op(self, message: str) -> None:
        self._end_op()
        self._error(message)

    def _on_toggle_done(self, res, enabled: bool) -> None:
        try:
            self._client.dbus_set_property_finish(res)
        except GLib.Error as err:
            if not _is_cancelled(err):
                self._fail_op(_describe(err, "turn Wi-Fi " + ("on" if enabled else "off")))
            return
        if not self._closed:
            self._end_op()

    def _on_disconnect_done(self, dev, res) -> None:
        # Finish even during close; _track keeps the client/main loop alive.
        try:
            dev.disconnect_finish(res)
        except GLib.Error as err:
            if not _is_cancelled(err):
                self._fail_op(_describe(err, "disconnect"))
            return
        if not self._closed:
            self._end_op()

    # ------------------------------------------------------------ scanning

    def _on_scan_requested(self, dev, res) -> None:
        # Finish even during close so all asynchronous replies are drained.
        try:
            dev.request_scan_finish(res)
        except GLib.Error as err:
            if not _is_cancelled(err):
                self._stop_scan()
                self._error(_describe(err, "scan for networks"))
            return
        if not self._closed:
            self._on_last_scan(dev)

    def _on_last_scan(self, dev, *_args) -> None:
        if self._scanning and dev is self._scan_dev and dev.get_last_scan() != self._scan_baseline:
            self._stop_scan()
        self._schedule_changed()

    def _on_scan_timeout(self) -> bool:
        self._scan_timeout = 0
        if self._scanning:
            self._stop_scan()
            self._error("The Wi-Fi scan did not finish in time.")
        return False

    def _stop_scan(self, emit: bool = True) -> None:
        self._scanning = False
        self._scan_dev = None
        if self._scan_timeout:
            GLib.source_remove(self._scan_timeout)
            self._scan_timeout = 0
        if emit:
            self._schedule_changed()

    # ------------------------------------------------------------ connect flow

    def _build_profile(self, entry: _Entry, key_mgmt: Optional[str], password: str):
        conn = NM.SimpleConnection.new()
        base = NM.SettingConnection.new()
        base.set_property(NM.SETTING_CONNECTION_ID, entry.name)
        base.set_property(NM.SETTING_CONNECTION_UUID, NM.utils_uuid_generate())
        base.set_property(NM.SETTING_CONNECTION_TYPE, NM.SETTING_WIRELESS_SETTING_NAME)
        conn.add_setting(base)
        wifi = NM.SettingWireless.new()
        wifi.set_property(NM.SETTING_WIRELESS_SSID, GLib.Bytes.new(entry.ssid))
        conn.add_setting(wifi)
        if key_mgmt is not None:
            sec = NM.SettingWirelessSecurity.new()
            sec.set_property(NM.SETTING_WIRELESS_SECURITY_KEY_MGMT, key_mgmt)
            sec.set_property(NM.SETTING_WIRELESS_SECURITY_PSK, password)
            conn.add_setting(sec)
        return conn

    def _prompt(self, act: _Action, prompt: _Prompt) -> None:
        self._clear_prompts("AgentCanceled", "Password request superseded.")
        if self._closed or act is not self._action or act.cancelled or act.cleaning:
            if prompt.invocation is not None:
                self._agent_reply_error(prompt.invocation, "AgentCanceled", "Connection attempt ended.")
            return
        self._prompts[prompt.token] = prompt
        self.emit("changed")
        if self._closed or act is not self._action or prompt.token not in self._prompts:
            return
        self.emit("password-requested", prompt.token, act.entry.name)

    def _submit_new(self, act: _Action, password: str) -> None:
        problem = _check_password(act.key_mgmt, password)
        if problem:
            self._error(problem)
            self._prompt(act, _Prompt(secrets.token_urlsafe(9), "new", act.key_mgmt))
            return
        self._launch(act, self._build_profile(act.entry, act.key_mgmt, password))

    def _cancel_prompt(self, prompt: _Prompt, act: Optional[_Action]) -> None:
        if prompt.kind == "agent":
            self._agent_reply_error(prompt.invocation, "UserCanceled", "Password entry was cancelled.")
        if act is not None and act is self._action:
            act.cancelled = True
            self._end_action()

    def _clear_prompts(self, error: str, message: str) -> None:
        prompts, self._prompts = self._prompts, {}
        for prompt in prompts.values():
            if prompt.invocation is not None:
                self._agent_reply_error(prompt.invocation, error, message)
        if prompts:
            self.emit("changed")

    def _launch(self, act: _Action, new_profile) -> None:
        """Add separately so the exact profile path is known before GetSecrets."""
        def go(problem: Optional[str]) -> None:
            if act is not self._action or self._closed or act.cancelled:
                return
            if problem:
                self._fail_action(problem)
            elif new_profile is None:
                self._activate(act, act.entry.profile, act.entry.profile_ap)
            else:
                act.pending = True
                # Do not cancel a mutating call: its late reply owns the profile
                # we must roll back. Block automatic activation until our request.
                flags = (NM.SettingsAddConnection2Flags.TO_DISK
                         | NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT)
                self._client.add_connection2(
                    new_profile.to_dbus(NM.ConnectionSerializationFlags.ALL), flags,
                    None, True, None,
                    self._track(lambda c, res: self._on_profile_added(act, c, res)))
        if act.entry.security in _PASSWORD_SECURITY:
            self._ensure_agent(go)
        else:
            go(None)

    def _on_profile_added(self, act: _Action, client, res) -> None:
        act.pending = False
        try:
            act.created, _result = client.add_connection2_finish(res)
        except GLib.Error as err:
            self._fail_action(_describe(err, f"add a profile for {act.entry.name}"))
            return
        act.expected_path = act.created.get_path()
        if self._closed or act.cancelled:
            self._end_action()
        else:
            self._activate(act, act.created, act.entry.aps[0])

    def _activate(self, act: _Action, profile, ap) -> None:
        act.pending = True
        act.device_handler = act.device.connect(
            "state-changed", lambda *_: self._observe_activation(act))
        self._client.activate_connection_async(
            profile, act.device, ap.get_path(), None,
            self._track(lambda c, res: self._on_activation_started(act, c, res)))

    def _observe_activation(self, act: _Action) -> None:
        # Keep this watcher through close and rollback, including a success that
        # NM reports before the activate callback or during deactivation.
        ac = act.device.get_active_connection()
        profile = ac.get_connection() if ac is not None else None
        if (profile is not None and profile.get_path() == act.expected_path
                and int(act.device.get_state()) == _DEV_ACTIVATED):
            act.succeeded = True

    def _on_activation_started(self, act: _Action, client, res) -> None:
        act.pending = False
        try:
            act.ac = client.activate_connection_finish(res)
        except GLib.Error as err:
            self._fail_action(_describe(err, f"connect to {act.entry.name}"))
            return
        act.ac_handler = act.ac.connect("state-changed", lambda *_: self._check_activation(act))
        if self._closed or act.cancelled:
            self._end_action()
        else:
            self._check_activation(act)

    def _check_activation(self, act: _Action) -> None:
        if act is not self._action or act.ac is None:
            return
        state = int(act.ac.get_state())
        if state == _AC_ACTIVATED:
            act.succeeded = True
            self._end_action()
        elif state == _AC_DEACTIVATED:
            if not act.cleaning:
                self._activation_failed(act, int(act.ac.get_state_reason()))
            elif act.rollback_done:
                self._discard_profile(act)
                self._maybe_closed()

    def _activation_failed(self, act: _Action, reason: int) -> None:
        cancelled, entry = act.cancelled, act.entry
        self._end_action()
        if cancelled:
            return
        text = _FAILURE_TEXT.get(reason)
        if reason == int(_R.NO_SECRETS) and entry.security in ("enterprise", "wep", "owe", "unsupported"):
            text = ("This profile needs credentials NetworkManager does not hold. Edit it in "
                    "nm-connection-editor (or nmtui) and connect again.")
        if text is None:
            try:
                text = f"Connection failed ({_R(reason).value_nick})."
            except ValueError:
                text = f"Connection failed (reason {reason})."
        self._error(f"{entry.name}: {text}")

    def _on_discard_done(self, act: _Action, conn, res) -> None:
        try:
            conn.delete_finish(res)
        except GLib.Error as err:
            self._error(_describe(err, "remove the failed connection profile"))
        self._finish_action(act)

    def _fail_action(self, message: str) -> None:
        self._end_action()
        self._error(message)

    def _end_action(self) -> None:
        act = self._action
        self._clear_prompts("AgentCanceled", "Connection attempt ended.")
        if act is None:
            self._end_op()
            return
        act.password = None
        if act.pending or act.cleaning:
            return
        self._observe_activation(act)
        if act.ac is not None and int(act.ac.get_state()) == _AC_ACTIVATED:
            act.succeeded = True
        if act.succeeded:
            self._finish_action(act)
            return
        act.cleaning = True
        act.cleanup_cancel = Gio.Cancellable()
        if act.ac is not None and int(act.ac.get_state()) != _AC_DEACTIVATED:
            self._client.deactivate_connection_async(
                act.ac, act.cleanup_cancel,
                self._track(lambda c, res: self._on_rollback_deactivated(act, c, res)))
        else:
            self._discard_profile(act)

    def _on_rollback_deactivated(self, act: _Action, client, res) -> None:
        try:
            client.deactivate_connection_finish(res)
        except GLib.Error as err:
            self._error(_describe(err, "cancel the pending connection"))
            # Do not delete a profile whose activation could still succeed.
            if act.ac is not None and int(act.ac.get_state()) != _AC_DEACTIVATED:
                self._finish_action(act)
                return
        # The D-Bus reply acknowledges deactivation, not its terminal state.
        # Preserve the state watcher until NM can no longer activate this AC.
        act.rollback_done = True
        if act.ac is None or int(act.ac.get_state()) == _AC_DEACTIVATED:
            self._discard_profile(act)

    def _discard_profile(self, act: _Action) -> None:
        act.rollback_done = False
        self._observe_activation(act)
        if act.created is not None and not act.succeeded:
            act.created.delete_async(
                act.cleanup_cancel,
                self._track(lambda c, res: self._on_discard_done(act, c, res)))
        else:
            self._finish_action(act)

    def _finish_action(self, act: _Action) -> None:
        if act.ac is not None and act.ac_handler:
            act.ac.disconnect(act.ac_handler)
            act.ac_handler = 0
        if act.device_handler:
            GObject.Object.disconnect(act.device, act.device_handler)
            act.device_handler = 0
        if act is self._action:
            self._action = None
            self._end_op()

    # ------------------------------------------------------------ secret agent

    def _ensure_agent(self, done: Callable[[Optional[str]], None]) -> None:
        if self._agent_registered:
            done(None)
            return
        self._agent_waiters.append(done)
        if not self._agent_registering:
            self._agent_registering = True
            Gio.bus_get(Gio.BusType.SYSTEM, self._cancel, self._track(self._on_bus))

    def _agent_ready(self, problem: Optional[str]) -> None:
        self._agent_registering = False
        waiters, self._agent_waiters = self._agent_waiters, []
        for done in waiters:
            done(problem)

    def _on_bus(self, _src, res) -> None:
        # Consume even a late bus reply; no registration is started after close.
        try:
            conn = Gio.bus_get_finish(res)
            if self._closed:
                self._agent_ready("The Wi-Fi popup was closed.")
                return
            if not self._agent_reg_id:
                node = Gio.DBusNodeInfo.new_for_xml(_AGENT_XML)
                self._agent_reg_id = conn.register_object(
                    _AGENT_PATH, node.interfaces[0], self._on_agent_call, None, None)
        except GLib.Error as err:
            self._agent_ready(f"Could not set up the password agent: {err.message}")
            return
        self._agent_conn = conn
        owner = self._client.get_dbus_name_owner()
        if not owner:
            self._agent_ready("NetworkManager stopped before agent registration.")
            return
        conn.call(owner, _AGENT_MANAGER_PATH, _AGENT_MANAGER_IFACE, "Register",
                  GLib.Variant("(s)", (_AGENT_ID,)), None, Gio.DBusCallFlags.NONE, -1,
                  None, self._track(lambda c, res: self._on_agent_registered(owner, c, res)))

    def _on_agent_registered(self, owner: str, conn, res) -> None:
        # Register is not cancelled: a late success must be explicitly undone.
        try:
            conn.call_finish(res)
        except GLib.Error as err:
            self._agent_ready(f"Could not register the password agent: {err.message}")
            return
        if owner != self._client.get_dbus_name_owner():
            self._agent_ready("NetworkManager restarted during agent registration.")
            return
        self._agent_owner = owner
        self._agent_registered = True
        if self._closed:
            self._unregister_agent()
        self._agent_ready(None)

    @staticmethod
    def _agent_reply_error(invocation, name: str, message: str) -> None:
        invocation.return_dbus_error(f"{_AGENT_IFACE}.{name}", message)

    def _on_agent_call(self, _conn, sender, _path, _iface, method, params, invocation) -> None:
        try:
            if self._closed or self._client is None or sender != self._client.get_dbus_name_owner():
                self._agent_reply_error(invocation, "PermissionDenied", "Only NetworkManager may call this agent.")
            elif method == "GetSecrets":
                self._agent_get_secrets(params, invocation)
            elif method == "CancelGetSecrets":
                self._agent_cancel(params.get_child_value(0).get_string(),
                                   params.get_child_value(1).get_string(), invocation)
            else:  # SaveSecrets / DeleteSecrets: nothing is ever persisted by this agent
                invocation.return_value(None)
        except Exception as exc:  # noqa: BLE001 - NM must always get an answer
            self._agent_reply_error(invocation, "Failed", f"Agent failure: {type(exc).__name__}")
            self._error(f"Password agent failure: {type(exc).__name__}: {exc}")

    def _agent_get_secrets(self, params, invocation) -> None:
        conn_path = params.get_child_value(1).get_string()
        setting_name = params.get_child_value(2).get_string()
        flags = params.get_child_value(4).get_uint32()
        act = self._action
        settings = params.get_child_value(0).unpack()
        sec = settings.get(NM.SETTING_WIRELESS_SECURITY_SETTING_NAME, {})
        wifi = settings.get(NM.SETTING_WIRELESS_SETTING_NAME, {})
        key_mgmt = sec.get("key-mgmt")
        if (act is None or act.cancelled or act.cleaning
                or not act.expected_path or conn_path != act.expected_path
                or not flags & int(NM.SecretAgentGetSecretsFlags.ALLOW_INTERACTION)
                or setting_name != NM.SETTING_WIRELESS_SECURITY_SETTING_NAME
                or key_mgmt not in ("wpa-psk", "sae")
                or (act.key_mgmt and key_mgmt != act.key_mgmt)
                or bytes(wifi.get("ssid", b"")) != act.entry.ssid):
            self._agent_reply_error(invocation, "NoSecrets", "No secrets available for this request.")
            return
        if act.password is not None and not flags & int(NM.SecretAgentGetSecretsFlags.REQUEST_NEW):
            password, act.password = act.password, None
            invocation.return_value(GLib.Variant("(a{sa{sv}})", ({setting_name: {
                "psk": GLib.Variant("s", password)}},)))
            return
        act.password = None
        self._prompt(act, _Prompt(secrets.token_urlsafe(9), "agent", key_mgmt, invocation,
                                  conn_path, setting_name))

    def _agent_cancel(self, conn_path: str, setting_name: str, invocation) -> None:
        for token, prompt in list(self._prompts.items()):
            if prompt.kind == "agent" and prompt.conn_path == conn_path and prompt.setting_name == setting_name:
                del self._prompts[token]
                self.emit("changed")
                self._agent_reply_error(prompt.invocation, "AgentCanceled", "Cancelled by NetworkManager.")
                self._error("NetworkManager cancelled the password request.")
        invocation.return_value(None)
