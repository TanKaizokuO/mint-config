"""Deterministic, offline regression tests for scripts/wifi_backend.py.

Run: python3 -m unittest discover -s ~/.config/waybar/tests -v

Safety: no NetworkManager client, system bus, scan, radio toggle or connection is
ever touched. NM.Client.new_async is replaced while constructing the backend and
the backend gets plain-Python fakes whose asynchronous calls only record the
request; each test completes those requests explicitly, in a chosen order. The
secret-agent bus registration is marked as done so the system bus is never
opened. All passwords are dummy literals.
"""

import os
import sys
import unittest
from unittest import mock

import gi

gi.require_version("NM", "1.0")
from gi.repository import GLib, GObject, NM  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import wifi_backend as wb  # noqa: E402

SENDER = ":1.42"
SSID = b"TestNet"
SAVED_PATH = "/org/freedesktop/NetworkManager/Settings/7"
CREATED_PATH = "/org/freedesktop/NetworkManager/Settings/99"
SEC_NAME = NM.SETTING_WIRELESS_SECURITY_SETTING_NAME
WIFI_NAME = NM.SETTING_WIRELESS_SETTING_NAME
INTERACT = int(NM.SecretAgentGetSecretsFlags.ALLOW_INTERACTION)
REQUEST_NEW = int(NM.SecretAgentGetSecretsFlags.REQUEST_NEW)
AC_ACTIVATING = int(NM.ActiveConnectionState.ACTIVATING)
AC_ACTIVATED = int(NM.ActiveConnectionState.ACTIVATED)
AC_DEACTIVATED = int(NM.ActiveConnectionState.DEACTIVATED)
DEV_ACTIVATED = int(NM.DeviceState.ACTIVATED)
DEV_DISCONNECTED = int(NM.DeviceState.DISCONNECTED)


class Request:
    """One recorded asynchronous call; the test decides when and how it completes."""

    def __init__(self, source, callback, cancellable):
        self.source, self.callback, self.cancellable = source, callback, cancellable
        self.value = self.error = None
        self.completed = False

    def complete(self, value=None, error=None):
        assert not self.completed
        self.completed, self.value, self.error = True, value, error
        self.callback(self.source, self)

    def finish(self):
        if self.error is not None:
            raise self.error
        return self.value


class FakeConn:
    def __init__(self, path):
        self.path = path
        self.deletes = []

    def get_path(self):
        return self.path

    def delete_async(self, cancellable, callback):
        self.deletes.append(Request(self, callback, cancellable))

    def delete_finish(self, res):
        return res.finish()


class FakeAP:
    def get_path(self):
        return "/org/freedesktop/NetworkManager/AccessPoint/1"


class FakeAC:
    def __init__(self, connection, state=AC_ACTIVATING, reason=0):
        self.connection, self.state, self.reason = connection, state, reason
        self.handlers = {}

    def get_state(self):
        return self.state

    def get_state_reason(self):
        return self.reason

    def get_connection(self):
        return self.connection

    def connect(self, _signal, cb):
        hid = len(self.handlers) + 1
        self.handlers[hid] = cb
        return hid

    def disconnect(self, hid):
        self.handlers.pop(hid, None)

    def fire(self):
        for cb in list(self.handlers.values()):
            cb()


class FakeDevice(NM.DeviceWifi):
    """A real in-memory GObject (no D-Bus) with controllable state.

    Real signal registration matters: NM.Device.disconnect(cancellable) shadows
    GObject.Object.disconnect(handler_id), which a plain-Python fake would hide.
    """

    def __init__(self):
        super().__init__()
        self.state = DEV_DISCONNECTED
        self.active = None

    def get_state(self):
        return self.state

    def get_active_connection(self):
        return self.active

    def fire(self):
        self.emit("state-changed", self.state, self.state, 0)


class FakeClient:
    def __init__(self, device):
        self.device = device
        self.adds, self.activations, self.deactivations = [], [], []

    def get_nm_running(self):
        return True

    def wireless_get_enabled(self):
        return True

    def wireless_hardware_get_enabled(self):
        return True

    def get_dbus_name_owner(self):
        return SENDER

    def get_devices(self):
        return [self.device]

    def get_connections(self):
        return []

    def add_connection2(self, settings, flags, args, ignore_out, cancellable, callback):
        req = Request(self, callback, cancellable)
        req.flags = flags
        self.adds.append(req)

    def add_connection2_finish(self, res):
        return res.finish(), None

    def activate_connection_async(self, profile, device, specific_object, cancellable, callback):
        req = Request(self, callback, cancellable)
        req.profile = profile
        self.activations.append(req)

    def activate_connection_finish(self, res):
        return res.finish()

    def deactivate_connection_async(self, ac, cancellable, callback):
        self.deactivations.append(Request(self, callback, cancellable))

    def deactivate_connection_finish(self, res):
        return res.finish()


class FakeInvocation:
    def __init__(self):
        self.value, self.error = None, None

    def return_value(self, value):
        self.value = value

    def return_dbus_error(self, name, message):
        self.error = name

    @property
    def replied(self):
        return self.value is not None or self.error is not None

    def psk(self):
        return self.value.unpack()[0][SEC_NAME]["psk"]


def entry(security="open", saved=False):
    return wb._Entry(
        id=f"{SSID.hex()}/{security}", ssid=SSID, name="TestNet", security=security,
        strength=70, active=False, aps=[FakeAP()],
        profile=FakeConn(SAVED_PATH) if saved else None,
        profile_ap=FakeAP() if saved else None)


def get_secrets_params(path, *, ssid=SSID, key_mgmt="wpa-psk", setting=SEC_NAME, flags=INTERACT):
    settings = {WIFI_NAME: {"ssid": GLib.Variant("ay", ssid)},
                SEC_NAME: {"key-mgmt": GLib.Variant("s", key_mgmt)}}
    return GLib.Variant("(a{sa{sv}}osasu)", (settings, path, setting, [], flags))


class BackendCase(unittest.TestCase):
    def setUp(self):
        # Construct without any NM client; the pending init callback is never delivered.
        with mock.patch.object(NM.Client, "new_async"):
            self.b = wb.WifiBackend()
        self.addCleanup(self.b._cancel.cancel)
        self.device = FakeDevice()
        self.client = FakeClient(self.device)
        b = self.b
        b._pending = 0
        b._init_pending = False
        b._client = self.client
        b._agent_registered = True  # never opens the system bus
        b._schedule_changed = lambda: None
        b._device = lambda: self.device
        self.entries = []
        b._entries = lambda _dev: self.entries
        self.errors, self.prompts, self.changes = [], [], []
        b.connect("error", lambda _b, msg: self.errors.append(msg))
        b.connect("changed", lambda _b: self.changes.append(b.snapshot()["prompt"]))
        b.connect("password-requested", lambda _b, token, ssid: self.prompts.append(
            (token, ssid, b.snapshot()["prompt"])))
        self.done = []

    def use(self, security="open", saved=False):
        e = entry(security, saved)
        self.entries = [e]
        return e

    def close(self):
        self.b.close(lambda: self.done.append(True))

    def start_new_profile(self, activate=True):
        """Connect to an unsaved open network; optionally complete the add reply."""
        e = self.use("open")
        self.b.connect(e.id)
        self.assertEqual(len(self.client.adds), 1)
        created = FakeConn(CREATED_PATH)
        if activate:
            self.client.adds[0].complete(created)
        return created

    def send(self, method, params, sender=SENDER):
        inv = FakeInvocation()
        self.b._on_agent_call(None, sender, "/", "iface", method, params, inv)
        return inv

    def ask_agent(self, path, **kw):
        return self.send("GetSecrets", get_secrets_params(path, **kw))


class ConnectCloseRaceTests(BackendCase):
    def test_new_profile_requested_without_autoconnect(self):
        self.start_new_profile(activate=False)
        flags = self.client.adds[0].flags
        self.assertTrue(flags & NM.SettingsAddConnection2Flags.BLOCK_AUTOCONNECT)

    def test_add_reply_after_close_deletes_profile_without_activating(self):
        created = self.start_new_profile(activate=False)
        self.close()
        self.assertEqual(self.done, [], "close completes while an add is still in flight")
        self.client.adds[0].complete(created)
        self.assertEqual(self.client.activations, [])
        self.assertEqual(len(created.deletes), 1)
        self.assertEqual(self.done, [], "close completes before profile deletion finished")
        created.deletes[0].complete()
        self.assertEqual(self.done, [True])

    def test_cleanup_delete_uses_fresh_uncancelled_cancellable(self):
        created = self.start_new_profile(activate=False)
        self.close()
        self.assertTrue(self.b._cancel.is_cancelled())
        self.client.adds[0].complete(created)
        cancellable = created.deletes[0].cancellable
        self.assertIsNotNone(cancellable)
        self.assertIsNot(cancellable, self.b._cancel)
        self.assertFalse(cancellable.is_cancelled())

    def test_activation_reply_after_close_deactivates_then_deletes(self):
        created = self.start_new_profile()
        self.assertEqual(self.client.activations[0].profile, created)
        self.close()
        ac = FakeAC(created)
        self.client.activations[0].complete(ac)
        self.assertEqual(len(self.client.deactivations), 1)
        self.assertFalse(self.client.deactivations[0].cancellable.is_cancelled())
        self.assertEqual(created.deletes, [], "profile deleted while its activation may continue")
        self.client.deactivations[0].complete()
        self.assertEqual(created.deletes, [], "reply to Deactivate is not the terminal state")
        ac.state = AC_DEACTIVATED
        ac.fire()
        self.assertEqual(len(created.deletes), 1)
        self.assertEqual(self.done, [])
        created.deletes[0].complete()
        self.assertEqual(self.done, [True])

    def test_close_while_delete_fails_still_completes(self):
        created = self.start_new_profile(activate=False)
        self.close()
        self.client.adds[0].complete(created)
        created.deletes[0].complete(error=GLib.Error("boom", "g-io-error-quark", 0))
        self.assertEqual(self.done, [True])

    def test_close_without_inflight_work_completes_immediately(self):
        self.close()
        self.assertEqual(self.done, [True])
        # A late close(done) after completion is still answered.
        self.b.close(lambda: self.done.append("late"))
        self.assertEqual(self.done, [True, "late"])


class FailedAndSuccessfulProfileTests(BackendCase):
    def test_failed_activation_deletes_created_profile_before_idle(self):
        created = self.start_new_profile()
        ac = FakeAC(created)
        self.client.activations[0].complete(ac)
        ac.state, ac.reason = AC_DEACTIVATED, int(NM.ActiveConnectionStateReason.LOGIN_FAILED)
        ac.fire()
        self.assertEqual(len(created.deletes), 1)
        self.assertFalse(created.deletes[0].cancellable.is_cancelled())
        self.assertTrue(self.b.snapshot()["busy"], "action reported done before cleanup")
        created.deletes[0].complete()
        self.assertFalse(self.b.snapshot()["busy"])
        self.assertTrue(any("password" in e.lower() for e in self.errors))

    def test_activation_call_failure_deletes_created_profile(self):
        created = self.start_new_profile()
        self.client.activations[0].complete(error=GLib.Error("nope", "g-io-error-quark", 0))
        self.assertEqual(len(created.deletes), 1)
        created.deletes[0].complete()
        self.assertFalse(self.b.snapshot()["busy"])

    def test_activated_new_profile_is_kept(self):
        created = self.start_new_profile()
        ac = FakeAC(created)
        self.client.activations[0].complete(ac)
        ac.state = AC_ACTIVATED
        ac.fire()
        self.assertEqual(created.deletes, [])
        self.assertEqual(self.client.deactivations, [])
        self.assertFalse(self.b.snapshot()["busy"])

    def test_success_reported_before_activation_reply_survives_close(self):
        created = self.start_new_profile()
        # NM reports the device as activated with our profile before the reply arrives.
        self.device.state = DEV_ACTIVATED
        self.device.active = FakeAC(created, AC_ACTIVATED)
        self.device.fire()
        self.close()
        self.client.activations[0].complete(FakeAC(created, AC_ACTIVATED))
        self.assertEqual(created.deletes, [])
        self.assertEqual(self.client.deactivations, [])
        self.assertEqual(self.done, [True])

    def test_success_observed_during_rollback_prevents_delete(self):
        created = self.start_new_profile()
        self.close()
        ac = FakeAC(created)
        self.client.activations[0].complete(ac)
        self.device.state = DEV_ACTIVATED
        self.device.active = FakeAC(created, AC_ACTIVATED)
        self.device.fire()
        self.client.deactivations[0].complete()
        ac.state = AC_DEACTIVATED
        ac.fire()
        self.assertEqual(created.deletes, [])
        self.assertEqual(self.done, [True])

    def test_other_profile_activation_does_not_count_as_success(self):
        created = self.start_new_profile()
        self.close()
        self.device.state = DEV_ACTIVATED
        self.device.active = FakeAC(FakeConn("/org/freedesktop/NetworkManager/Settings/1"),
                                    AC_ACTIVATED)
        self.device.fire()
        ac = FakeAC(created, AC_DEACTIVATED)
        self.client.activations[0].complete(ac)
        self.assertEqual(len(created.deletes), 1)

    def test_saved_profile_is_never_deleted_on_failure_or_close(self):
        e = self.use("open", saved=True)
        self.b.connect(e.id)
        self.assertEqual(self.client.adds, [], "saved profile must not be re-added")
        self.assertIs(self.client.activations[0].profile, e.profile)
        self.close()
        ac = FakeAC(e.profile)
        self.client.activations[0].complete(ac)
        self.client.deactivations[0].complete()
        ac.state = AC_DEACTIVATED
        ac.fire()
        self.assertEqual(e.profile.deletes, [])
        self.assertEqual(self.done, [True])

    def test_saved_profile_failed_activation_not_deleted(self):
        e = self.use("open", saved=True)
        self.b.connect(e.id)
        ac = FakeAC(e.profile)
        self.client.activations[0].complete(ac)
        ac.state = AC_DEACTIVATED
        ac.fire()
        self.assertEqual(e.profile.deletes, [])
        self.assertFalse(self.b.snapshot()["busy"])

    def test_connecting_active_network_is_a_noop(self):
        e = self.use("open", saved=True)
        e.active = True
        self.b.connect(e.id)
        self.assertEqual((self.client.adds, self.client.activations), ([], []))
        self.assertFalse(self.b.snapshot()["busy"])


class PromptLifecycleTests(BackendCase):
    def test_new_network_prompt_is_established_before_signal(self):
        e = self.use("wpa2")
        self.b.connect(e.id)
        self.assertEqual(len(self.prompts), 1)
        token, ssid, seen_at_emit = self.prompts[0]
        self.assertEqual((ssid, seen_at_emit), ("TestNet", token))
        self.assertEqual(self.b.snapshot()["prompt"], token)

    def test_invalid_password_reprompts_same_token_and_builds_nothing(self):
        e = self.use("wpa2")
        self.b.connect(e.id)
        token = self.prompts[0][0]
        self.b.submit_password(token, "short")
        self.assertTrue(self.errors)
        self.assertEqual(self.b.snapshot()["prompt"], token)
        self.assertEqual(self.prompts[-1][2], token)
        self.assertEqual(self.client.adds, [])

    def test_valid_password_clears_prompt_and_adds_profile(self):
        e = self.use("wpa2")
        self.b.connect(e.id)
        self.b.submit_password(self.prompts[0][0], "dummy-pass-1234")
        self.assertEqual(self.b.snapshot()["prompt"], "")
        self.assertEqual(len(self.client.adds), 1)

    def test_cancelling_new_prompt_clears_token_and_creates_nothing(self):
        e = self.use("wpa2")
        self.b.connect(e.id)
        token = self.prompts[0][0]
        self.changes.clear()
        self.b.submit_password(token, None)
        self.assertEqual(self.b.snapshot()["prompt"], "")
        self.assertIn("", self.changes)
        self.assertEqual(self.client.adds, [])
        self.assertFalse(self.b.snapshot()["busy"])

    def test_stale_token_submission_is_rejected(self):
        e = self.use("wpa2")
        self.b.connect(e.id)
        token = self.prompts[0][0]
        self.b.submit_password(token, None)
        self.errors.clear()
        self.b.submit_password(token, "dummy-pass-1234")
        self.assertEqual(len(self.errors), 1)
        self.assertEqual(self.client.adds, [])

    def saved_agent_prompt(self):
        e = self.use("wpa2", saved=True)
        self.b.connect(e.id)  # saved profile, no password supplied: NM will ask the agent
        inv = self.ask_agent(SAVED_PATH, flags=INTERACT | REQUEST_NEW)
        self.assertFalse(inv.replied)
        self.assertEqual(len(self.prompts), 1)
        token, _ssid, seen_at_emit = self.prompts[0]
        self.assertEqual(seen_at_emit, token)
        return e, token, inv

    def test_agent_prompt_answer_is_returned_to_networkmanager(self):
        _e, token, inv = self.saved_agent_prompt()
        self.b.submit_password(token, "dummy-pass-1234")
        self.assertEqual(inv.psk(), "dummy-pass-1234")
        self.assertEqual(self.b.snapshot()["prompt"], "")

    def test_cancelling_agent_prompt_replies_cancelled_and_clears(self):
        _e, token, inv = self.saved_agent_prompt()
        self.b.submit_password(token, None)
        self.assertTrue(inv.error.endswith("UserCanceled"))
        self.assertEqual(self.b.snapshot()["prompt"], "")

    def test_cancel_get_secrets_clears_only_matching_prompt(self):
        _e, token, inv = self.saved_agent_prompt()
        other = self.send("CancelGetSecrets", GLib.Variant(
            "(os)", ("/org/freedesktop/NetworkManager/Settings/8", SEC_NAME)))
        self.assertIsNone(other.error)
        self.assertFalse(inv.replied)
        self.assertEqual(self.b.snapshot()["prompt"], token)
        self.changes.clear()
        self.send("CancelGetSecrets", GLib.Variant("(os)", (SAVED_PATH, SEC_NAME)))
        self.assertTrue(inv.error.endswith("AgentCanceled"))
        self.assertEqual(self.b.snapshot()["prompt"], "")
        self.assertIn("", self.changes)

    def test_action_end_clears_agent_prompt(self):
        e, _token, inv = self.saved_agent_prompt()
        ac = FakeAC(e.profile)
        self.client.activations[0].complete(ac)
        self.changes.clear()
        ac.state, ac.reason = AC_DEACTIVATED, int(NM.ActiveConnectionStateReason.NO_SECRETS)
        ac.fire()
        self.assertEqual(self.b.snapshot()["prompt"], "")
        self.assertTrue(inv.error.endswith("AgentCanceled"))
        self.assertIn("", self.changes)

    def test_close_clears_prompt_and_answers_waiting_agent(self):
        _e, _token, inv = self.saved_agent_prompt()
        self.changes.clear()
        self.close()
        self.assertEqual(self.b.snapshot()["prompt"], "")
        self.assertTrue(inv.error.endswith("UserCanceled"))
        self.assertIn("", self.changes)

    def test_networkmanager_loss_clears_prompt(self):
        _e, _token, inv = self.saved_agent_prompt()
        self.client.get_nm_running = lambda: False
        self.changes.clear()
        self.b._on_nm_running()
        self.assertEqual(self.b.snapshot()["prompt"], "")
        self.assertTrue(inv.error.endswith("AgentCanceled"))
        self.assertIn("", self.changes)


class DeviceHandlerLifecycleTests(BackendCase):
    """Signal handlers on the (real GObject) device are released through every exit path."""

    def connected(self, hid):
        return GObject.signal_handler_is_connected(self.device, hid)

    def test_close_releases_device_watchers(self):
        self.b._watch_device(self.device)
        ids = list(self.b._dev_handlers[self.device])
        self.assertTrue(ids and all(self.connected(h) for h in ids))
        self.close()
        self.assertFalse(any(self.connected(h) for h in ids))
        self.assertEqual(self.done, [True])

    def test_device_removal_releases_watchers(self):
        self.b._watch_device(self.device)
        ids = list(self.b._dev_handlers[self.device])
        self.b._on_device_removed(self.client, self.device)
        self.assertFalse(any(self.connected(h) for h in ids))
        self.assertNotIn(self.device, self.b._dev_handlers)

    def test_finished_attempt_releases_activation_watcher(self):
        e = self.use("open", saved=True)
        self.b.connect(e.id)
        hid = self.b._action.device_handler
        self.assertTrue(self.connected(hid))
        ac = FakeAC(e.profile)
        self.client.activations[0].complete(ac)
        ac.state = AC_ACTIVATED
        ac.fire()
        self.assertFalse(self.connected(hid))
        self.assertFalse(self.b.snapshot()["busy"])

    def test_close_during_attempt_releases_activation_watcher_after_cleanup(self):
        created = self.start_new_profile()
        hid = self.b._action.device_handler
        self.close()
        self.assertTrue(self.connected(hid), "watcher must outlive close for success detection")
        self.client.activations[0].complete(FakeAC(created, AC_DEACTIVATED))
        created.deletes[0].complete()
        self.assertFalse(self.connected(hid))
        self.assertEqual(self.done, [True])

    def test_terminal_state_signal_after_drain_completes_close(self):
        e = self.use("open", saved=True)
        self.b.connect(e.id)
        hid = self.b._action.device_handler
        self.close()
        ac = FakeAC(e.profile)
        self.client.activations[0].complete(ac)
        self.client.deactivations[0].complete()
        self.assertEqual(self.done, [], "NM has not reported the terminal state yet")
        ac.state = AC_DEACTIVATED
        ac.fire()  # outside any tracked callback: this alone must finish the close
        self.assertEqual(self.done, [True])
        self.assertFalse(self.connected(hid))
        self.assertEqual(e.profile.deletes, [])



class AgentValidationTests(BackendCase):
    def saved_with_password(self):
        e = self.use("wpa2", saved=True)
        self.b.connect(e.id, "dummy-pass-1234")
        self.assertEqual(len(self.client.activations), 1)
        return e

    def test_exact_path_answers_from_supplied_settings_once(self):
        # The fake client's connection cache is empty: only the supplied settings can match.
        self.saved_with_password()
        inv = self.ask_agent(SAVED_PATH)
        self.assertEqual(inv.psk(), "dummy-pass-1234")
        again = self.ask_agent(SAVED_PATH)
        self.assertIsNone(again.value, "one-shot password must not be replayed")
        self.assertEqual(self.prompts[-1][2], self.b.snapshot()["prompt"])

    def test_wrong_connection_path_gets_no_secrets_and_keeps_password(self):
        self.saved_with_password()
        wrong = self.ask_agent("/org/freedesktop/NetworkManager/Settings/8")
        self.assertTrue(wrong.error.endswith("NoSecrets"))
        self.assertEqual((self.prompts, self.b.snapshot()["prompt"]), ([], ""))
        self.assertEqual(self.ask_agent(SAVED_PATH).psk(), "dummy-pass-1234")

    def test_non_networkmanager_sender_is_rejected(self):
        self.saved_with_password()
        inv = self.send("GetSecrets", get_secrets_params(SAVED_PATH), sender=":1.666")
        self.assertTrue(inv.error.endswith("PermissionDenied"))
        cancel = self.send("CancelGetSecrets", GLib.Variant("(os)", (SAVED_PATH, SEC_NAME)),
                           sender=":1.666")
        self.assertTrue(cancel.error.endswith("PermissionDenied"))
        self.assertEqual(self.ask_agent(SAVED_PATH).psk(), "dummy-pass-1234")

    def test_mismatched_supplied_settings_are_refused(self):
        self.saved_with_password()
        cases = {
            "ssid": dict(ssid=b"OtherNet"),
            "key-mgmt": dict(key_mgmt="wpa-eap"),
            "setting": dict(setting="802-1x"),
            "no-interaction": dict(flags=0),
        }
        for name, kw in cases.items():
            with self.subTest(name):
                self.assertTrue(self.ask_agent(SAVED_PATH, **kw).error.endswith("NoSecrets"))
        self.assertEqual(self.ask_agent(SAVED_PATH).psk(), "dummy-pass-1234")

    def test_key_mgmt_must_match_new_profile_choice(self):
        e = self.use("wpa2")
        self.b.connect(e.id, "dummy-pass-1234")
        self.client.adds[0].complete(FakeConn(CREATED_PATH))
        inv = self.ask_agent(CREATED_PATH, key_mgmt="sae")
        self.assertTrue(inv.error.endswith("NoSecrets"))

    def test_request_new_prompts_instead_of_replaying_saved_password(self):
        self.saved_with_password()
        inv = self.ask_agent(SAVED_PATH, flags=INTERACT | REQUEST_NEW)
        self.assertFalse(inv.replied)
        self.assertNotEqual(self.b.snapshot()["prompt"], "")

    def test_created_profile_path_unknown_until_add_replies(self):
        e = self.use("wpa2")
        self.b.connect(e.id, "dummy-pass-1234")
        self.assertTrue(self.ask_agent(CREATED_PATH).error.endswith("NoSecrets"))
        self.assertTrue(self.ask_agent("/").error.endswith("NoSecrets"))
        self.client.adds[0].complete(FakeConn(CREATED_PATH))
        inv = self.ask_agent(CREATED_PATH)
        self.assertFalse(inv.replied, "exact created path must reach the prompt")
        self.assertNotEqual(self.b.snapshot()["prompt"], "")
        self.assertTrue(self.ask_agent(SAVED_PATH).error.endswith("NoSecrets"))

    def test_no_active_attempt_or_closed_backend_refuses(self):
        self.use("wpa2", saved=True)
        self.assertTrue(self.ask_agent(SAVED_PATH).error.endswith("NoSecrets"))
        self.saved_with_password()
        self.close()
        self.assertTrue(self.ask_agent(SAVED_PATH).error.endswith("PermissionDenied"))


if __name__ == "__main__":
    unittest.main()
