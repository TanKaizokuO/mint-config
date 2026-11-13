#!/usr/bin/env python3
"""Compact Wi-Fi popover for the Waybar network pill (GTK3 + gtk-layer-shell).

Launch (Waybar ``network.on-click``)::

    /usr/bin/python3 ~/.config/waybar/scripts/wifi_popover.py

Single instance (Gtk.Application ``local.waybar.WifiPopover``): the first launch opens
the popover, any launch while it is open closes it, so clicking the pill again toggles.

Placement
    A fully transparent layer-shell surface (layer TOP, anchored to all four edges,
    exclusive zone 0) is placed by sway in the output's usable area, i.e. directly
    below the Waybar exclusive zone, so the bar and its pills are never covered and
    stay clickable. The glass card sits at that surface's top-right corner, 6px below
    the bar and 12px from the screen edge (the right edge of the right-hand pills).
    It is aligned to the right of the screen, not to the exact pill: Waybar does not
    expose module geometry.

Monitor
    sway's IPC does not expose the pointer's output, so the *focused* output
    (swaymsg -t get_outputs) is used; sway focuses the output under the cursor when
    the pointer crosses onto it, which makes this the clicked bar in practice. When
    no output can be matched, the compositor chooses (also the focused output).

Dismissal
    Escape, a click anywhere outside the card (the transparent surface catches it,
    the click is not forwarded), launching the script again, or Advanced settings.
    The surface takes exclusive keyboard focus while open so Escape and typing the
    password work immediately.

    Dismissal hides the surface at once, cancels a pending password request
    (``submit_password(token, None)``, the token and password never leave memory) and
    then calls ``WifiBackend.close(done=...)``. Teardown/rollback of in-flight NM
    operations is asynchronous, so the Gtk.Application is held and its main loop keeps
    running with the (hidden) window until the backend's ``done`` callback fires; only
    then is the window destroyed and the application quit. A launch arriving in that
    window is ignored, so no ghost popover reopens while the old one is still closing.

Password prompt
    The backend's ``snapshot()['prompt']`` is the live prompt token (or ''). Every
    render drops a pending UI prompt whose token no longer matches it (superseded or
    cancelled in the backend); a plain ``error`` never dismisses a live prompt.

Network access goes through wifi_backend.WifiBackend only; passwords travel through
its ``password-requested`` signal / ``submit_password`` and never touch argv.

Requires the GI namespace GtkLayerShell 0.1 (Debian package gir1.2-gtklayershell-0.1) and
the already-installed libgtk-layer-shell0. If the system typelib is absent, the script uses
the per-user copy in ~/.config/waybar/vendor/gtklayershell/ (unpacked with ``dpkg-deb -x``
from the official Ubuntu noble package gir1.2-gtklayershell-0.1 0.8.2-1build2, the same
version as the installed libgtk-layer-shell0; only the typelib and its copyright notice
are kept, nothing is installed system-wide). Once ``apt install gir1.2-gtklayershell-0.1``
is done the system copy wins and the vendor directory can be deleted.

Colours follow ~/.config/glass-themes/current (light or dark).
"""

import glob
import json
import os
import subprocess
import sys

_TYPELIB = "GtkLayerShell-0.1.typelib"
_VENDOR_TYPELIBS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "vendor", "gtklayershell",
    "usr", "lib", "x86_64-linux-gnu", "girepository-1.0",
)
# Prefer the system typelib; only when it is absent fall back to the per-user copy.
# GI_TYPELIB_PATH has to be set before gi first reads its search path.
if not any(
    glob.glob(f"{base}/{_TYPELIB}")
    for base in ("/usr/lib/*/girepository-1.0", "/usr/lib/girepository-1.0", "/usr/lib64/girepository-1.0")
) and os.path.isfile(
    os.path.join(_VENDOR_TYPELIBS, _TYPELIB)
):
    os.environ["GI_TYPELIB_PATH"] = os.pathsep.join(
        p for p in (os.environ.get("GI_TYPELIB_PATH"), os.path.normpath(_VENDOR_TYPELIBS)) if p
    )

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")


def _fatal(message):
    """Report a prerequisite problem where the user will see it, then exit."""
    print(f"wifi_popover: {message}", file=sys.stderr)
    try:
        subprocess.run(
            ["notify-send", "-a", "Wi-Fi", "Wi-Fi popover unavailable", message],
            check=False, timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    sys.exit(1)


# GtkLayerShell must be imported before Gtk/Gdk load libwayland-client.
try:
    gi.require_version("GtkLayerShell", "0.1")
    from gi.repository import GtkLayerShell
except (ValueError, ImportError):
    _fatal(
        "GtkLayerShell GI namespace missing; install gir1.2-gtklayershell-0.1 "
        f"(or unpack it into {_VENDOR_TYPELIBS})"
    )

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from wifi_backend import WifiBackend  # noqa: E402
except (ValueError, ImportError) as exc:
    _fatal(f"Wi-Fi backend unavailable: {exc}")

APP_ID = "local.waybar.WifiPopover"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CSS_PATH = os.path.join(SCRIPT_DIR, "wifi_popover.css")
THEME_LINK = os.path.expanduser("~/.config/glass-themes/current")

CARD_WIDTH = 340
GAP_BELOW_BAR = 6       # bar is already 6px from the top; keep the same rhythm
EDGE_MARGIN = 12        # bar margin-right 8 + .modules-right margin 4
LIST_MAX_HEIGHT = 240

# Palettes mirror glass-themes/{light,dark}/waybar.css.
PALETTES = {
    "light": {
        "bg": "rgba(170, 170, 174, 0.90)",
        "border": "rgba(255, 255, 255, 0.43)",
        "highlight": "rgba(255, 255, 255, 0.48)",
        "shadow": "rgba(0, 0, 0, 0.25)",
        "fg": "#1D1D1F",
        "dim": "#3A3A3F",
        "ok": "#0A4D1A",
        "warn": "#5C4200",
        "crit": "#8A0012",
        "active": "rgba(60, 60, 64, 0.22)",
        "hover": "rgba(0, 0, 0, 0.08)",
        "btn": "rgba(255, 255, 255, 0.30)",
        "field": "rgba(255, 255, 255, 0.45)",
        "primary_bg": "#2C2C30",
        "primary_fg": "#F2F2F2",
        "primary_hover": "#1D1D1F",
    },
    "dark": {
        "bg": "rgba(18, 18, 18, 0.92)",
        "border": "rgba(255, 255, 255, 0.14)",
        "highlight": "rgba(255, 255, 255, 0.08)",
        "shadow": "rgba(0, 0, 0, 0.55)",
        "fg": "#F2F2F2",
        "dim": "#B8B8B8",
        "ok": "#30D158",
        "warn": "#FFD60A",
        "crit": "#FF453A",
        "active": "rgba(255, 255, 255, 0.10)",
        "hover": "rgba(255, 255, 255, 0.10)",
        "btn": "rgba(255, 255, 255, 0.06)",
        "field": "rgba(255, 255, 255, 0.10)",
        "primary_bg": "#E6E6E6",
        "primary_fg": "#161616",
        "primary_hover": "#FFFFFF",
    },
}

BARS = "\u2582\u2584\u2586\u2588"
ICON_WIFI = "\uf1eb"
ICON_LOCK = "\uf023"
ICON_CHECK = "\uf00c"
ICON_REFRESH = "\uf021"
ICON_GEAR = "\uf013"
OPEN_SECURITY = ("", "open", "none", "--")
WAITING_HINT = "Waiting for password\u2026"


def load_css():
    """Install the popover stylesheet with the palette of the live glass theme."""
    theme = os.path.basename(os.path.realpath(THEME_LINK))
    palette = PALETTES.get(theme, PALETTES["light"])
    prelude = "".join(f"@define-color wifi_{k} {v};\n" for k, v in palette.items())
    with open(CSS_PATH, encoding="utf-8") as fh:
        css = prelude + fh.read()
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_USER
    )


def focused_monitor(display):
    """Gdk.Monitor of the sway-focused output, or None to let the compositor pick."""
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_outputs", "-r"],
            capture_output=True, text=True, timeout=2, check=True,
        )
        outputs = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    rect = next((o["rect"] for o in outputs if o.get("focused")), None)
    if rect is None:
        return None
    # Match on the logical origin: distinct outputs never share one, and it does not
    # depend on how GDK rounds fractional-scale sizes.
    for i in range(display.get_n_monitors()):
        monitor = display.get_monitor(i)
        geo = monitor.get_geometry()
        if (geo.x, geo.y) == (rect["x"], rect["y"]):
            return monitor
    return None


def signal_bars(strength):
    """Signal bucket 1-4 shared by the glyph, the list order and the row signature."""
    return 1 + (strength >= 25) + (strength >= 50) + (strength >= 75)


def network_order(net):
    """Strongest bucket first, then deterministic by name, security and id."""
    return (-signal_bars(net["strength"]), net["ssid"].casefold(), net["security"], net["id"])


def signal_markup(strength):
    lit = signal_bars(strength)
    return "".join(
        ch if i < lit else f'<span alpha="30%">{ch}</span>'
        for i, ch in enumerate(BARS)
    )


def is_secured(net):
    return net.get("security", "").strip().lower() not in OPEN_SECURITY


def make_label(text="", classes=(), xalign=0.0, ellipsize=False, wrap=False):
    label = Gtk.Label(label=text, xalign=xalign)
    for cls in classes:
        label.get_style_context().add_class(cls)
    if ellipsize:
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(28)
    if wrap:
        label.set_line_wrap(True)
        label.set_max_width_chars(36)
    return label


def make_button(text, primary=False):
    button = Gtk.Button(label=text)
    ctx = button.get_style_context()
    ctx.add_class("wifi-btn")
    if primary:
        ctx.add_class("wifi-primary")
    button.set_can_focus(True)
    return button


class PopoverWindow(Gtk.ApplicationWindow):
    def __init__(self, app, monitor, on_closed):
        super().__init__(application=app, title="Wi-Fi")
        self._on_closed = on_closed  # called once, after backend teardown completed
        self._pending_token = None
        self._syncing = False
        self._cleaned_up = False
        self.closing = False
        self._error = ""
        self._hint = ""
        self._was_busy = False
        self._list_signature = None
        self._loading = True  # until the backend's first changed/error (NM.Client starting)

        self.get_style_context().add_class("wifi-popover")
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.set_decorated(False)
        self._init_layer(monitor)
        self._build()

        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self._on_button_press)
        self.connect("key-press-event", self._on_key_press)
        self.connect("destroy", self._on_destroy)

        # WifiBackend.connect()/disconnect() are its own actions, so the GObject
        # signal API has to be called unbound.
        self.backend = WifiBackend()
        self._handler_ids = [
            GObject.Object.connect(self.backend, "changed", self._on_changed),
            GObject.Object.connect(self.backend, "error", self._on_error),
            GObject.Object.connect(
                self.backend, "password-requested", self._on_password_requested
            ),
        ]
        self._render()

    # ---- window setup -------------------------------------------------------

    def _init_layer(self, monitor):
        GtkLayerShell.init_for_window(self)
        GtkLayerShell.set_namespace(self, "wifi-popover")
        GtkLayerShell.set_layer(self, GtkLayerShell.Layer.TOP)
        for edge in (
            GtkLayerShell.Edge.TOP,
            GtkLayerShell.Edge.BOTTOM,
            GtkLayerShell.Edge.LEFT,
            GtkLayerShell.Edge.RIGHT,
        ):
            GtkLayerShell.set_anchor(self, edge, True)
        # Exclusive zone stays 0: sway then lays the surface out below Waybar's zone.
        GtkLayerShell.set_keyboard_mode(self, GtkLayerShell.KeyboardMode.EXCLUSIVE)
        if monitor is not None:
            GtkLayerShell.set_monitor(self, monitor)

    def _build(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.get_style_context().add_class("wifi-card")
        card.set_size_request(CARD_WIDTH, -1)
        card.set_halign(Gtk.Align.END)
        card.set_valign(Gtk.Align.START)
        card.set_margin_top(GAP_BELOW_BAR)
        card.set_margin_end(EDGE_MARGIN)
        self.card = card
        self.add(card)

        # Header: icon, title + state, on/off switch.
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        header.pack_start(make_label(ICON_WIFI, ("wifi-icon",)), False, False, 0)
        titles = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        titles.pack_start(make_label("Wi-Fi", ("wifi-title",)), False, False, 0)
        self.subtitle = make_label("", ("wifi-dim",), ellipsize=True)
        titles.pack_start(self.subtitle, False, False, 0)
        header.pack_start(titles, True, True, 0)
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch.get_style_context().add_class("wifi-switch")
        self.switch.connect("notify::active", self._on_switch_toggled)
        header.pack_end(self.switch, False, False, 0)
        card.pack_start(header, False, False, 0)

        # Current connection.
        self.current_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.current_box.get_style_context().add_class("wifi-current")
        # (current-connection visibility is driven by _render)
        self.current_box.pack_start(make_label(ICON_CHECK, ("wifi-ok",)), False, False, 0)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.current_name = make_label("", ellipsize=True)
        names.pack_start(self.current_name, False, False, 0)
        self.current_detail = make_label("Connected", ("wifi-dim",))
        names.pack_start(self.current_detail, False, False, 0)
        self.current_box.pack_start(names, True, True, 0)
        self.disconnect_button = make_button("Disconnect")
        self.disconnect_button.connect("clicked", self._on_disconnect_clicked)
        self.current_box.pack_end(self.disconnect_button, False, False, 0)
        card.pack_start(self.current_box, False, False, 0)

        # Empty / disabled / unavailable message.
        self.message = make_label("", ("wifi-dim",), xalign=0.5, wrap=True)
        self.message.set_justify(Gtk.Justification.CENTER)
        self.message.set_margin_top(8)
        self.message.set_margin_bottom(8)
        # (message visibility is driven by _render)
        card.pack_start(self.message, False, False, 0)

        # Nearby networks.
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_activate_on_single_click(True)
        self.listbox.get_style_context().add_class("wifi-list")
        self.listbox.connect("row-activated", self._on_row_activated)
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_propagate_natural_height(True)
        self.scroller.set_max_content_height(LIST_MAX_HEIGHT)
        self.scroller.add(self.listbox)
        # (list visibility is driven by _render)
        card.pack_start(self.scroller, False, False, 0)

        # Inline password prompt.
        self.password_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.password_box.get_style_context().add_class("wifi-password")
        # (password prompt stays hidden until the backend asks)
        self.password_label = make_label("", ellipsize=True)
        self.password_box.pack_start(self.password_label, False, False, 0)
        self.entry = Gtk.Entry()
        self.entry.get_style_context().add_class("wifi-entry")
        self.entry.set_visibility(False)
        self.entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.entry.set_placeholder_text("Password")
        self.entry.connect("activate", self._on_password_submit)
        self.entry.connect("changed", self._on_entry_changed)
        self.password_box.pack_start(self.entry, False, False, 0)
        pw_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.show_check = Gtk.CheckButton(label="Show")
        self.show_check.get_style_context().add_class("wifi-show")
        self.show_check.connect("toggled", self._on_show_toggled)
        pw_row.pack_start(self.show_check, True, True, 0)
        self.pw_connect = make_button("Connect", primary=True)
        self.pw_connect.set_sensitive(False)
        self.pw_connect.connect("clicked", self._on_password_submit)
        pw_row.pack_end(self.pw_connect, False, False, 0)
        self.pw_cancel = make_button("Cancel")
        self.pw_cancel.connect("clicked", self._on_password_cancel)
        pw_row.pack_end(self.pw_cancel, False, False, 0)
        self.password_box.pack_start(pw_row, False, False, 0)
        card.pack_start(self.password_box, False, False, 0)

        # Status line.
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        # (spinner visibility is driven by _render)
        status_row.pack_start(self.spinner, False, False, 0)
        self.status = make_label("", ("wifi-dim",), wrap=True)
        status_row.pack_start(self.status, True, True, 0)
        card.pack_start(status_row, False, False, 0)

        # Footer buttons.
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.refresh_button = make_button(f"{ICON_REFRESH}  Refresh")
        self.refresh_button.connect("clicked", self._on_refresh_clicked)
        footer.pack_start(self.refresh_button, False, False, 0)
        advanced = make_button(f"{ICON_GEAR}  Advanced settings")
        advanced.connect("clicked", self._on_advanced_clicked)
        footer.pack_start(advanced, True, True, 0)
        card.pack_start(footer, False, False, 0)

        # Sections toggled by _render: realise their children first, because
        # no_show_all stops show_all() from descending into them.
        for section in (self.current_box, self.scroller, self.password_box):
            section.show_all()
        for section in (self.current_box, self.message, self.scroller,
                        self.password_box, self.spinner):
            section.set_no_show_all(True)
        card.show_all()
        self.password_box.hide()

    # ---- backend -> UI ------------------------------------------------------

    def _on_changed(self, _backend):
        self._loading = False
        self._render()

    def _on_error(self, _backend, message):
        self._loading = False
        self._error = message
        self._hint = ""
        self._render()

    def _on_password_requested(self, _backend, token, ssid):
        if self._pending_token is not None and self._pending_token != token:
            self.backend.submit_password(self._pending_token, None)
        self._pending_token = token
        self.password_label.set_text(f"Password for {ssid or 'hidden network'}")
        self.entry.set_text("")
        self.show_check.set_active(False)
        self.password_box.set_visible(True)
        self._hint = WAITING_HINT
        self.entry.grab_focus()
        self._render()

    def _reconcile_prompt(self, prompt):
        """Drop a pending UI prompt the backend no longer holds (token mismatch).

        The backend already forgot it, so nothing is submitted; a live prompt with
        another token reaches the UI through its own password-requested signal.
        """
        if self._pending_token is None or self._pending_token == prompt:
            return
        self._pending_token = None
        self.entry.set_text("")
        self.password_box.set_visible(False)
        if self._hint == WAITING_HINT:
            self._hint = ""

    def _render(self):
        if self._cleaned_up:
            return
        snap = self.backend.snapshot()
        self._reconcile_prompt(snap.get("prompt", ""))
        available = snap["available"]
        enabled = snap["enabled"]
        busy = snap["busy"]
        scanning = snap["scanning"]
        networks = snap["networks"]

        if available:
            self._loading = False
        if self._was_busy and not busy:
            self._hint = ""
        self._was_busy = busy

        # Header.
        # While an action is in flight the backend may not have caught up yet; keep
        # the switch where the user put it until it settles.
        if not busy:
            self._syncing = True
            self.switch.set_active(bool(available and enabled))
            self._syncing = False
        self.switch.set_sensitive(available and not busy)
        if self._loading:
            subtitle = "Checking\u2026"
        else:
            subtitle = "Unavailable" if not available else ("On" if enabled else "Off")
        self.subtitle.set_text(subtitle)

        # Current connection.
        active = next((n for n in networks if n["active"]), None)
        show_current = available and enabled and (active is not None or bool(snap["active_ssid"]))
        if show_current:
            name = (active or {}).get("ssid") or snap["active_ssid"]
            self.current_name.set_text(name or "Hidden network")
            self.disconnect_button.set_sensitive(not busy)
        self.current_box.set_visible(show_current)

        # Nearby networks.
        others = []
        if available and enabled:
            others = sorted((n for n in networks if not n["active"]), key=network_order)
        self._sync_list(others)
        self.listbox.set_sensitive(not busy)
        self.scroller.set_visible(bool(others))

        # Empty-state message.
        if self._loading:
            text = "Checking Wi-Fi\u2026"
        elif not available:
            text = "Wi-Fi unavailable.\nNo Wi-Fi adapter was found or NetworkManager is not running."
        elif not enabled:
            text = "Wi-Fi is off. Turn it on to see nearby networks."
        elif not others and not show_current:
            text = "Looking for networks\u2026" if scanning else "No networks found. Try Refresh."
        else:
            text = ""
        self.message.set_text(text)
        self.message.set_visible(bool(text))

        # Status line.
        status_error = bool(self._error)
        if status_error:
            status = self._error
        elif busy:
            status = self._hint or "Working\u2026"
        elif scanning:
            status = "Scanning\u2026"
        elif available and enabled and others:
            status = f"{len(others)} network{'s' if len(others) != 1 else ''} nearby"
        else:
            status = ""
        ctx = self.status.get_style_context()
        for cls, on in (("wifi-error", status_error), ("wifi-dim", not status_error)):
            if on:
                ctx.add_class(cls)
            else:
                ctx.remove_class(cls)
        self.status.set_text(status)
        working = busy or scanning
        self.spinner.set_visible(working)
        self.spinner.set_property("active", working)

        self.refresh_button.set_sensitive(available and enabled and not working)

    def _sync_list(self, networks):
        # Signature uses signal buckets, not raw %, so jitter inside a bucket does not
        # rebuild the rows (which would reset scroll and hover).
        signature = tuple(
            (n["id"], n["ssid"], signal_bars(n["strength"]), n["security"], n["saved"])
            for n in networks
        )
        if signature == self._list_signature:
            # Same rows in the same order: only refresh tooltips, whose % may have
            # drifted inside a bucket.
            for row, net in zip(self.listbox.get_children(), networks):
                self._set_tooltip(row, net)
            return
        self._list_signature = signature
        adj = self.scroller.get_vadjustment()
        offset = adj.get_value()
        for child in self.listbox.get_children():
            self.listbox.remove(child)
        for net in networks:
            self.listbox.add(self._make_row(net))
        self.listbox.show_all()
        GLib.idle_add(self._restore_scroll, adj, offset)

    @staticmethod
    def _restore_scroll(adj, offset):
        adj.set_value(offset)
        return GLib.SOURCE_REMOVE

    def _make_row(self, net):
        row = Gtk.ListBoxRow()
        row.get_style_context().add_class("wifi-row")
        row.network_id = net["id"]
        row.network_ssid = net["ssid"]
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bars = Gtk.Label()
        bars.set_markup(signal_markup(net["strength"]))
        bars.get_style_context().add_class("wifi-bars")
        box.pack_start(bars, False, False, 0)
        box.pack_start(make_label(net["ssid"] or "Hidden network", ellipsize=True), True, True, 0)
        if net["saved"]:
            box.pack_start(make_label("Saved", ("wifi-dim",)), False, False, 0)
        if is_secured(net):
            box.pack_start(make_label(ICON_LOCK, ("wifi-dim",)), False, False, 0)
        self._set_tooltip(row, net)
        row.add(box)
        return row

    @staticmethod
    def _set_tooltip(row, net):
        text = f"{net['strength']}%  \u00b7  {net['security'] or 'Open'}"
        if getattr(row, "tooltip", None) != text:
            row.tooltip = text
            row.set_tooltip_text(text)

    # ---- user actions -------------------------------------------------------

    def _begin_action(self, hint):
        """Common preamble of every user action: drop stale error, show progress hint."""
        self._error = ""
        self._hint = hint
        self._dismiss_password()

    def _on_switch_toggled(self, switch, _pspec):
        if self._syncing:
            return
        on = switch.get_active()
        self._begin_action("Turning Wi-Fi on\u2026" if on else "Turning Wi-Fi off\u2026")
        self.backend.set_enabled(on)
        self._render()

    def _on_row_activated(self, _listbox, row):
        self._begin_action(f"Connecting to {row.network_ssid or 'hidden network'}\u2026")
        self.backend.connect(row.network_id)
        self._render()

    def _on_disconnect_clicked(self, _button):
        self._begin_action("Disconnecting\u2026")
        self.backend.disconnect()
        self._render()

    def refresh(self):
        self._begin_action("Scanning\u2026")
        self.backend.refresh()
        self._render()

    def _on_refresh_clicked(self, _button):
        self.refresh()

    def _on_advanced_clicked(self, _button):
        try:
            Gio.Subprocess.new(["nm-connection-editor"], Gio.SubprocessFlags.NONE)
        except GLib.Error as exc:
            self._error = f"Cannot start nm-connection-editor: {exc.message}"
            self._render()
            return
        self.close_popover()

    # ---- password prompt ----------------------------------------------------

    def _dismiss_password(self):
        """Cancel an open password request, if any, and hide the prompt."""
        token, self._pending_token = self._pending_token, None
        self.entry.set_text("")
        self.password_box.set_visible(False)
        if token is not None:
            self.backend.submit_password(token, None)

    def _on_entry_changed(self, entry):
        self.pw_connect.set_sensitive(bool(entry.get_text()))

    def _on_show_toggled(self, check):
        self.entry.set_visibility(check.get_active())

    def _on_password_submit(self, _widget):
        password = self.entry.get_text()
        if self._pending_token is None or not password:
            return
        token, self._pending_token = self._pending_token, None
        self.entry.set_text("")
        self.password_box.set_visible(False)
        self._error = ""
        self._hint = "Connecting\u2026"
        self.backend.submit_password(token, password)
        self._render()

    def _on_password_cancel(self, _button):
        self._dismiss_password()
        self._render()

    # ---- dismissal ----------------------------------------------------------

    def _on_key_press(self, _widget, event):
        if event.keyval != Gdk.KEY_Escape:
            return False
        self.close_popover()
        return True

    def _on_button_press(self, _widget, event):
        """Close on any click outside the card (everything else is a transparent catcher)."""
        origin = self.card.translate_coordinates(self, 0, 0)
        gdk_window = self.get_window()
        if origin is None or gdk_window is None:
            return False
        _ok, win_x, win_y = gdk_window.get_origin()
        alloc = self.card.get_allocation()
        left = win_x + origin[0]
        top = win_y + origin[1]
        inside = (
            left <= event.x_root < left + alloc.width
            and top <= event.y_root < top + alloc.height
        )
        if inside:
            return False
        self.close_popover()
        return True

    def close_popover(self):
        self._begin_close()

    def _begin_close(self):
        """Hide now, cancel the prompt, tear the backend down asynchronously."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        self.closing = True
        self.hide()
        token, self._pending_token = self._pending_token, None
        self.entry.set_text("")
        if token is not None:
            self.backend.submit_password(token, None)
        for handler_id in self._handler_ids:
            GObject.Object.handler_disconnect(self.backend, handler_id)
        self._handler_ids = []
        self.backend.close(done=self._on_backend_closed)

    def _on_backend_closed(self, *_args):
        GLib.idle_add(self._finish_close)  # safe from any context/thread

    def _finish_close(self):
        on_closed, self._on_closed = self._on_closed, None
        if on_closed is not None:
            self.destroy()
            on_closed()
        return GLib.SOURCE_REMOVE

    def _on_destroy(self, _widget):
        # External destruction (e.g. compositor closed the layer surface): same path.
        self._begin_close()


class WifiPopoverApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self._window = None

    def do_activate(self):
        if self._window is not None:
            # Second launch while open = toggle off; while closing = ignore.
            if not self._window.closing:
                self._window.close_popover()
            return
        load_css()
        window = PopoverWindow(
            self, focused_monitor(Gdk.Display.get_default()), self._on_window_closed
        )
        self._window = window
        # Keep the main loop alive until the backend finished its async teardown.
        self.hold()
        window.show_all()
        # Opening shows the cached snapshot only; scans happen via the Refresh button.

    def _on_window_closed(self):
        self._window = None
        self.quit()


def main():
    if Gdk.Display.get_default() is None:
        _fatal("cannot open a display (is WAYLAND_DISPLAY set?)")
    if not GtkLayerShell.is_supported():
        _fatal(
            "layer-shell unavailable: compositor lacks zwlr_layer_shell_v1, or "
            "libgtk-layer-shell must be loaded before libwayland-client "
            "(try LD_PRELOAD=libgtk-layer-shell.so.0)"
        )
    return WifiPopoverApp().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
