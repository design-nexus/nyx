# Adaptive window management: audit and integration plan

Status: Stage 1 (audit and plan) done 2026-11-09. The handoff is "NyxOS Adaptive Window
Management" in the NyxOS handoff set. Each later stage is built, installed and shown
before the next starts.

Decisions taken with Ken on 2026-11-09:

- The compositor plugin (third-party headerbar, chromeless floating button) is
  NyxOS only: hyprland-nyx 0.57.1, tested in the NyxOS VM. On the laptop, Omarchy's
  hyprbars titlebar and the Dock's hover dots stay as they are.
- The native Nyx control (nyx-ui) ships everywhere, as nyx-ui changes always have.
- One stage at a time, with screenshots, waiting for a go-ahead between stages.

## 1. What exists

| Piece | Where | What it does today |
| --- | --- | --- |
| Window state | `nyx-core/crates/nyx-desktop/src/model.rs` (`Window`) | address, `stable_id`, class, title, workspace, monitor, `floating`, `fullscreen` (0 none, 1 maximized, 2 fullscreen), `at`/`size`, pid, pinned, hidden, grouped |
| Shell Core state | `nyx-shell/crates/nyx-shell-core/src/state.rs`, proto `WindowState` | The normalized registry with generations and deltas; `minimized` = on Omarchy's `special:minimized`. No geometry or pid on the wire |
| Shell Core actions | `nyx-shell/crates/nyx-shell-core/src/compositor.rs` `window_dispatch` | `focus`, `close`, `toggle_floating`, `toggle_maximized`, `move_to_workspace`, `move_to_monitor`, checked against the state. Needs `desktop.act`, which only Quickshell and `nyx-shellctl` get (`docs/SECURITY.md`) |
| Dispatchers | `nyx-core/crates/nyx-desktop/src/actions.rs` | Lua form with classic fallback. `minimize` runs `omarchy-hyprland-window-minimize` (Omarchy only) |
| Native header | `nyx-design/crates/nyx-ui/src/chrome.rs` `app_header` | Icon and name left, app actions in `end`, then minimize, maximize and close while floating. Follows its own window with a per-app `nyx-desktop` watcher, matched by pid and title. Tags the window `nyx-own-controls`. Used by about 35 apps |
| Omarchy titlebar | hyprbars plugin, on Omarchy's floating workspaces | Settings writes `hyprbars:no_bar` for apps with their own titlebar (`nyx-settings/apps/settings/src/backend/titlebars.rs`) |
| Dock hover dots | `nyx-dock/apps/dock-backend/src/controls.rs`, `qml/Dock/WindowControls.qml` | A layer surface placed at the focused floating window, re-read every 150 ms while shown. This is the loosely positioned overlay the handoff rules out |
| Plugin precedent | `nyx-dock/hyprland-plugin/main.cpp` (`nyx-dock-swipe`) | A Nyx plugin built against the running Hyprland's headers, posting IPC events |
| Theme to Hyprland | `nyx-system/apps/themed/src/outputs.rs` `hyprland_lua` | Writes `~/.config/hypr/nyx-theme.lua` and runs `hyprctl reload` on theme changes |
| Shell config | `nyx-shell/crates/nyx-shell-core/src/config.rs` | Typed `shell` domain over nyx-config layers, `UpdateShellConfig` and reset, watched with inotify |
| Settings | `nyx-settings/apps/settings/src/sections/workspaces.rs`, `own_titlebars.rs` | Tiling & Workspaces page with the window-controls choice and the own-titlebar list |
| NyxOS Hyprland | `nyxos/modules/home/hyprland.nix`, `nyx-packages/pkgs/hyprland.nix` | No titlebar, no plugins. `SUPER + T` toggles floating. The nyx-hyprland patch series is applied |

## 2. Compositor facts that shape the design

- `IHyprWindowDecoration` (`Hyprland/src/render/decorations/`) is the attachment
  mechanism: `CDecorationPositioner` reserves space on an edge, the decoration moves,
  resizes and animates with its window, gets mouse input with
  `DECORATION_ALLOWS_MOUSE_INPUT`, and dies with the window. Plugins add one with
  `HyprlandAPI::addWindowDecoration` (hyprbars works this way).
- The renderer skips decorations in true fullscreen and keeps them when maximized
  (`src/render/Renderer.cpp:660`), so fullscreen hiding comes for free.
- Hyprland remembers each window's last floating size, not its position. Tile to float
  recentres on the tiled slot (`DefaultFloatingAlgorithm::movedTarget`). Restoring the
  previous floating position needs our own memory.
- Maximize (`fullscreen` mode 1) on a tiled window expands it over the layout and keeps
  it tiled; restoring returns it to its slot. On a floating window it fills the work
  area. True fullscreen is mode 2. So the three operations the handoff separates are
  already separate; the controls only have to label them by mode.
- xdg-decoration: Hyprland answers every client with server-side mode and records what
  the client requested (`src/protocols/XDGDecoration.cpp`). GTK4 doesn't use the
  protocol. Qt and Electron apps do, and drop their own titlebar. Wayland gives no
  reliable way to see whether a client's own titlebar has working buttons, so this
  is a hint for defaults only.
- `hl.plugin.load(path)` loads plugins from Lua config; plugins can add config values
  (`addConfigValueV2`), dispatchers (`addDispatcherV2`) and hyprctl commands.
- `~/Projects/Hyprland` has another session's uncommitted virtual-monitor work. The
  plugin lives outside it and builds against the packaged hyprland-nyx headers.

## 3. Mechanism per presentation

| Presentation | Mechanism | Why |
| --- | --- | --- |
| Native Nyx (`native-nyx`) | Rework `nyx-ui` `app_header`'s `window_controls` into one Close button plus a `gtk::Popover` | Already in every Nyx header; the popover is an xdg_popup of the app, so it can't cover other compositor surfaces or drift |
| Third-party without controls (`custom-headerbar`) | New plugin `nyx-decor`: an `IHyprWindowDecoration` on the top edge | Attached geometry, input and lifecycle; hidden in fullscreen by the renderer |
| Chromeless (`chromeless-floating`) | Same plugin: a small decoration in the `DECORATION_LAYER_OVER` layer at a corner, only while floating | Same attachment, no reserved space, so content isn't pushed |
| Apps with working controls (`preserve-native`) | Nothing | No duplicated titlebar |

The panels these open (the chromeless button's panel, the headerbar's right-click menu)
are transient Shell Core overlays in `nyx-shell-qs`. The plugin posts
`nyxdecor>>menu,ADDRESS,X,Y`; the overlay opens once at that point and closes on Escape,
a click outside, focus loss, or the window moving, closing or going fullscreen. It never
follows a window, so it isn't the fragile tracking overlay. The persistent pieces are all
compositor decorations.

## 4. Shared window actions (Stage 2)

One action table, in Shell Core (`window_actions.rs`, new): for a window's state it lists
each action with `available` and `active`, and every presentation shows only what's
available.

| Action | Tiled | Floating | Dispatch |
| --- | --- | --- | --- |
| `close` | yes | yes | `hl.dsp.window.close` |
| `toggle_floating` | "Float" | "Tile" | `hl.dsp.window.float`, with the plugin's geometry memory |
| `toggle_maximized` | "Expand" / "Restore" | "Maximize" / "Restore" | `hl.dsp.window.fullscreen({ mode = "maximized" })` |
| `toggle_fullscreen` (new) | yes | yes | `hl.dsp.window.fullscreen({ mode = "fullscreen" })` |
| `toggle_pinned` (new) | no | yes | `hl.dsp.window.pin` |
| `minimize` (new) | where supported | where supported | Omarchy's `special:minimized`; unavailable on NyxOS, which has no hide mechanism |
| `move_to_workspace`, `move_to_monitor` | yes | yes | existing |

- **Capability:** a new `window.own` capability for every same-user client: it may act
  on windows whose pid equals its peer pid (`SO_PEERCRED`), nothing else. Nyx apps then
  drive their own window through Shell Core without getting `desktop.act`.
- **Geometry memory:** in the plugin, keyed by the window object (not the pid). On float
  to tile it saves the floating box; on tile to float it places the window there before
  the first frame, clamped to the current monitor's work area (reserved edges and scale
  included). With no saved box, Hyprland's own placement. A disconnected monitor's box is
  clamped onto the monitor the window is on now. This covers `SUPER + T` as well as the
  buttons, as both run the same dispatcher.
- **Policy:** `[window_controls]` in `shell.toml` with per-app rules
  (`match = { app_id | class | desktop }`, `controls = …`, `float = …`). Precedence: user
  override, then NyxOS defaults, then the `nyx-own-controls` tag (`native-nyx`), then the
  xdg-decoration hint (requested server-side means `custom-headerbar`), then
  `preserve-native`. Shell Core resolves it into each `WindowState` (`controls`) and
  writes `~/.config/hypr/nyx-window-controls.lua` (tags `nyx-controls:KIND` by rule,
  checked with `configerrors` and rolled back on error, as the shortcuts file is). The
  plugin reads the tags.
- **Exclusions:** windows with a parent (dialogs, transients), X11 override-redirect and
  utility windows, popups and pinned special-workspace scratchpads get no headerbar.
- **Stale references:** every action is checked against the current generation;
  `not_found` for a window that's gone, and presentations close their popover or panel
  on the window's removal delta.

## 5. Stages

| Stage | Repositories | Result | Checked by |
| --- | --- | --- | --- |
| 2 Shared actions | nyx-shell (proto, core, shellctl), nyx-core (nyx-desktop dispatchers) | Action table, new actions, `window.own`, `[window_controls]` policy, rules file | Unit tests in nyx-shell-core; `nyx-shellctl` against a test Shell Core |
| 3 Native control | nyx-design (nyx-ui), then one app (nyx-weather), then a pin bump per app | Close button with a 200 ms hover popover, click or keyboard opens it too, touch long-press; mode-specific rows | `cargo test` in nyx-ui; headless-output screenshots tiled and floating; install |
| 4 Custom headerbar | nyx-hyprland (`plugins/nyx-decor`), nyx-packages, nyxos | Icon, title, drag, double-click, right-click menu, minimize where supported, maximize or expand, float or tile, close; themed | Built in nyx-packages; tested in the NyxOS VM with GTK, Qt, Electron and XWayland apps |
| 5 Chromeless button | same plugin, nyx-shell-qs overlay | Corner button while floating, panel on click | NyxOS VM with foot and other terminals |
| 6 Settings and rules | nyx-settings, nyxos defaults | Window Controls group on Tiling & Workspaces, shown by capability (plugin loaded, Shell Core running) | Settings tests; VM |
| 7 Validation | all of the above | The handoff's test table | VM and laptop |

Theme: `nyx-themed` adds the plugin's colours (surface, text, dim text, accent, border,
danger, inactive) to `nyx-theme.lua`, which it already reloads on every theme change. No
new theme path.

## 6. Stage 2 results (2026-11-09)

Built in nyx-shell; no nyx-core change.

- `nyx-shell-proto::window` holds the policy, so Shell Core, Nyx apps and Settings share
  one copy: `controls()` (a `[window_controls.apps]` rule for the app id or initial app
  id, then the built-in rules, then `native-nyx` for `io.github.design_nexus.nyx.*`,
  else none and the compositor decides), `available()` (the table in section 4), and
  `rules_lua()`.
- New actions `set_floating`, `set_tiled`, `toggle_fullscreen`, `toggle_pinned` and
  `minimize`. Shell Core refuses an action that isn't in the window's `actions` now
  (`invalid`), so a stale button can't double-toggle. `minimize` runs Omarchy's own
  script and is offered only on Omarchy's floating workspaces, which the watcher thread
  reads; on NyxOS it is never offered.
- `WindowState` carries `pid`, `controls` and `actions`, all optional on the wire. A
  change to `[window_controls]` updates the windows at once.
- `window.own` for every same-user client: window actions except `focus` on windows of
  its own process.
- `[window_controls]` in `shell.toml`: `enabled`, `hover_delay_ms` (200), and
  `apps.ID = { controls, float }`. Height, corner and double-click settings come with
  the stages that use them.
- `nyx-shellctl window ADDRESS ACTION [TARGET]`, and `nyx-shellctl window-controls
  --print | --apply` writing `~/.config/hypr/nyx-window-controls.lua` (with the same
  reload and roll-back as `shortcuts --apply`).
- Checked: 95 unit and integration tests in the workspace, clippy clean, and a read-only
  test copy of Shell Core against the laptop's Hyprland (foot windows came out
  `chromeless-floating` with tiled actions, ChatGPT with no presentation).

Deviations from section 4:

- The tag is `nyx-controls-KIND` (no colon, like Hyprland's other tags).
- Shell Core doesn't see Hyprland tags or the xdg-decoration request, so the
  `nyx-own-controls` tag and the decoration hint aren't part of its resolution. Nyx apps
  are recognized by their app id prefix. The hint stays with the plugin, for windows
  with no presentation.
- Floating geometry memory stays in the plugin (Stage 4), as planned; nothing in Stage 2
  moves windows.

Left for later stages: NyxOS's Hyprland config has to load
`nyx-window-controls.lua` (Stage 4, with the plugin). nyx-shell `a5d1c61` (virtual
monitors) needs nyx-core `ec92333`, which isn't pushed or pinned yet; Stage 2 was built
and tested against the local nyx-core checkout until that pin moves.

## 7. Stage 3 results (2026-11-10)

nyx-design `3584628` (nyx-ui `chrome.rs`, `base2.css`), nyx-shell `814a9b6`.

- Every app using `app_header` gets one Close button at the header's end, tiled or
  floating (before: three buttons, floating only). A click closes. After the pointer
  rests on it for `[window_controls] hover_delay_ms`, or on a right-click, long press,
  Menu, Shift+F10 or Down, a popover opens below it, right-aligned, so it only covers
  content. A hover-opened popover doesn't take clicks or focus (Close still closes) and
  stays open for 350 ms outside both, so the way into it doesn't close it; one opened
  from the keyboard or a click takes focus. It closes when the window's mode changes,
  the window loses focus, or the window goes away.
- Rows come from `nyx_shell_proto::window::available` on the window's state, named for
  the mode: floating Minimize (Omarchy's floating workspaces only), Maximize/Restore
  size, Tile, Fullscreen, Keep on top; tiled Expand/Restore to the layout, Float,
  Fullscreen; both Move to workspace (1 to 10) and Move to monitor (when there's
  another). Outside Hyprland, GTK's own minimize, maximize and fullscreen.
- Actions go through Shell Core (`window.own`) when its socket answers, else straight
  to Hyprland with the same dispatchers.
- The Hyprland check found that float takes `enable`/`disable`, not `set`/`unset` (any
  other word toggles). Shell Core's `set_floating`/`set_tiled` were fixed
  (`814a9b6`). Pin, maximize, fullscreen and float were all checked on a test window,
  each restoring its floating geometry.
- Installed on the laptop: Weather, built against the local nyx-design (its pin moves
  to `3584628` once nyx-design is pushed; then the other apps follow by pin bump, no
  code change).

Limits found:

- Headless captures of an unfocused tiled test window show no popovers at all (the
  Maps session saw the same); floating ones do. The tiled popover's placement is
  checked live.
- The hover delay is read once per app start.
- Move to workspace lists 1 to 10, not a virtual monitor region's own numbers.

## 8. Stage 4 results (2026-11-10)

nyx-hyprland `00a1f4c` (`plugins/nyx-decor`), nyx-packages `1fae17e` (`nyx-decor`),
nyx-system `1c78f1c` (theme colours), nyx-shell `e82feaa` (`window-controls` without
Shell Core, unchanged files left alone).

- **Headerbar:** an `IHyprWindowDecoration` on the top edge, priority 10010, so it
  sits inside the window's border and the border goes round bar and window as one. Title
  at the left; maximize (restore once maximized; expand on a tiled window), float or
  tile, and close at the right, drawn with cairo. Hover lights a button, close turns the
  danger colour. Empty space drags a floating window, a double-click maximizes, a
  right-click posts `nyxdecor>>menu,ADDRESS,X,Y` (for Stage 5's menu). Not on dialogs,
  transient, modal or override-redirect windows; hidden in true fullscreen (the window
  then takes the whole output); kept when maximized. Inactive windows dim the title.
- **Actions** run the same dispatchers as Shell Core, deferred to Hyprland's idle loop.
- **Floating geometry:** each floating window's place is read every frame once it has
  floated for 500 ms; floating it again after tiling puts it back there, clamped to its
  monitor's work area (moved in, or centred, if that monitor went away).
- **Settings** `plugin.nyx_decor`: `enabled`, `height` (32, 24 to 48), `font_size` (12),
  `font_family`, `double_click_maximize`, `restore_float_geometry`, and `col.*`.
  nyx-themed sets the colours from the theme (panel, text, tertiary text, hover
  strength, danger) once the plugin is loaded; Hyprland reads its config again when
  plugins load, so this holds from the first start.
- **Checked** in a nested Hyprland 0.57.2 inside the NyxOS VM's session, with `foot`
  tagged for a headerbar: tiled and floating bars, the border round both, float/tile and
  maximize/restore glyphs, Close's hover colour, live colour changes, fullscreen without
  a bar, float at (90, 80), tile, float again at (90, 80), two windows (inactive
  styling), closing a window and unloading the plugin with Hyprland still running.

Not checked yet: pointer clicks on the bar (dragging, double-click, right-click,
pressing buttons). The nested session had no way to inject clicks; they need a person at
the VM's console or Stage 7's run on NyxOS itself.

Limits: no app icon in the bar yet; no minimize on NyxOS; a window's headerbar changes
only when the rules do (a config reload), as rule tags are static.

### Found on the way (for the Hyprland 0.57.2 packaging, d54327d)

- The patch series' `hyprtester/` hunks don't apply: Hyprland's flake source leaves
  `hyprtester` out, and `patch` stops at "File to patch".
- Hyprland 0.57.2 needs wayland-protocols 1.49; with `inputs.nixpkgs.follows` it gets
  nixpkgs' 1.48.
- `patchSeries = "${inputs.nyx-hyprland}/patches/0.57.2"` makes Hyprland depend on the
  whole nyx-hyprland source, so any change there (the plugin included) rebuilds
  Hyprland. `builtins.path { path = …/patches/0.57.2; name = …; }` would make it depend
  on the series alone.

The VM test worked around the first two in a scratch copy only (`/root/nyxdecor`).

### VM note

A nested Hyprland started as ken inside the VM's session shares ken's systemd user
manager; stopping the first one ended ken's desktop session in the VM. The test then ran
nested Hyprland with its own `XDG_RUNTIME_DIR` and a bare environment, stopped with
SIGKILL, and the session stayed up. Any later nested test must do the same.

### Turning it on in NyxOS

`patches/nyxos-window-controls.patch` (next to this file) loads the plugin, the
window-controls rules file and runs `nyx-shellctl window-controls --apply` at Hyprland's
start. It goes into nyxos once nyx-packages `1fae17e` is pushed and pinned there, and
NyxOS's Hyprland is 0.57.2 (the plugin needs it).

## 9. Stage 5 results (2026-11-10)

nyx-hyprland `02c2784`, nyx-shell `48d5082`, nyx-packages `ceed423`.

- **Chromeless control** (nyx-decor): windows tagged `nyx-controls-chromeless-floating`
  get a three-dot pill in a corner while they float; hidden when tiled, maximized or
  fullscreen. It is a zero-size sticky decoration on all four edges, so its box is the
  window's: clicks on the pill are its own (never half a click to the app), all others
  pass through. Faint until hovered, then the theme's hover tint. Settings
  `corner_button` and `corner_button_corner` (`top-right`, `top-left`, `bottom-right`,
  `bottom-left`), applied live.
- **Window menu** (`nyx-shell/qml/components/nyx-window-menu`, in nyx-shell-qs): opened
  by Hyprland's custom event `nyx-window-menu,0xADDRESS,X,Y`, which the headerbar's
  right-click and the chromeless control post (the event format moved from Stage 4's
  `nyxdecor>>menu,…` to Hyprland's own custom event, so `hl.dsp.event` can raise it in
  tests). Entries come from the window's `actions`, named as the native popover names
  them, plus Close; Move to workspace lists the window's monitor's workspaces 1 to 10
  (a virtual monitor's own, past its base), Move to monitor the others. Actions go
  through Shell Core's `RequestWindowAction`. It is a transient, keyboard-exclusive
  overlay over the point's monitor; Escape, a click outside, the window going away or
  another window taking focus close it.
- **Checked:** the control in a nested Hyprland 0.57.2 in the VM (tiled none, floating,
  hover, maximized none, fullscreen none, bottom-left corner), next to a headerbar window;
  the menu on the laptop on a headless output with a read-only test Shell Core, opened
  by its test switch and by `hl.dsp.event("nyx-window-menu,…")`, placed at the event's
  point.

Not checked yet: clicking the control or a menu row (no click injection in either test),
and the menu with the plugin in one session (needs NyxOS on Hyprland 0.57.2, with Shell
Core and nyx-shell-qs).

## 10. Stage 6 results (2026-11-10)

nyx-settings `cb27014`, nyx-shell `c631045`.

Tiling & Workspaces gets the window controls, shown by what the system has:

- **Everywhere** (group "Nyx apps' window controls" on Omarchy, "Window controls" on
  NyxOS): adaptive controls on or off, and how long the pointer rests on a Nyx app's
  Close button (0 to 1000 ms; written once the slider rests). They're
  `[window_controls]` in `shell.toml`: through Shell Core where it runs, else the user's
  layer (Nyx apps read it there on Omarchy too).
- **Where nyx-decor is loaded** (`hyprctl -j plugin list`, asked once per run): headerbar
  height (24 to 48 px), double-click to maximize, float windows where they were, the
  control on floating terminals and its corner. These are Hyprland values
  (`plugin.nyx_decor.*`), live through `hl.config` and kept in Settings' managed file in
  a block that applies only while the plugin is loaded, so they never become config
  errors without it.
- **Window controls per app** (with nyx-decor): each app's presentation (Automatic, Nyx
  headerbar, small control while floating, its own controls) and how it opens
  (Automatic, floating, tiled); add an installed app (keyed by its `StartupWMClass`,
  else its desktop id), or remove one. The list is saved whole and then
  `nyx-shellctl window-controls --apply` brings Hyprland's rules up to date.
- With nyx-decor loaded, Omarchy's titlebar choice and its "Apps with their own
  titlebar" list are left out; they stay on Omarchy.
- App ids now match without regard to case, in Shell Core and in the rules, since the
  app index lowercases window classes and classes vary (`Alacritty`).

Checked: Settings tests (215, including the managed file's plugin block), a test copy
on a headless output showing the Omarchy variant, and the NyxOS variant with a test-only
switch (removed again) and sample per-app rules. Installed on the laptop; the managed
Hyprland file came out unchanged.

## 11. Stage 7: validation so far (2026-11-10)

The handoff's tests. "Nested VM" is a nested Hyprland 0.57.2 with nyx-decor in the
NyxOS VM's session; "headless" a test copy on the laptop's own headless output. NyxOS
itself can't run the whole stack yet (section 8: Hyprland 0.57.2 doesn't build in
nyx-packages, and the NyxOS change waits for the pin).

| Test | Result | Where |
| --- | --- | --- |
| Native Nyx app tiled: one Close button, hover controls | Close button shown; popover content right; its placement in a tiled window not visible in headless captures | headless (Weather) |
| Native Nyx app floating: same header, floating controls | Passed: popover under Close, right-aligned, floating rows | headless |
| Native app toolbar actions never obstructed | Passed: the popover opens below the header | headless |
| Third-party app with controls: no duplicated headerbar | Passed by design: only tagged windows get one; untagged foot has none | nested VM |
| Third-party app without controls: integrated headerbar | Passed: inside the border, flush with the content, themed | nested VM |
| Chromeless terminal tiled: no control | Passed | nested VM |
| Chromeless terminal floating: compact control | Passed (corner setting live) | nested VM |
| Float, tile, float: previous geometry | Passed: (90, 80) 700×420 back | nested VM |
| Tiled expand, restore: original arrangement | Passed: tiled slot back | nested VM |
| Maximize, restore: floating geometry | Passed | nested VM |
| True fullscreen: decorations hidden | Passed: no bar, no reserved space, no control | nested VM |
| Leave fullscreen: presentation back | Passed | nested VM |
| Change the theme: controls follow | Plugin colours change live through `hl.config` (what nyx-themed writes); nyx-ui's popover uses the theme's CSS. Not run end to end with nyx-themed | nested VM |
| Move to another monitor | Passed: moved with its control | nested VM |
| Disconnect a monitor: window recoverable | Passed: on the remaining screen (its workspace moved there); floating again centred it at its size | nested VM |
| Close a window during the popover | Passed: Weather exited cleanly with the popover open | headless |
| Restart shell UI: state valid | Plugin unloaded and loaded again with windows open: bars and controls back. Shell Core's restart was already covered (Handoff 01) | nested VM |
| Rapid mode switching: no duplicate or orphaned decorations | Passed: 60 float toggles and 8 fullscreen toggles across two windows, then one bar and one control; native: 20 toggles with the popover open | nested VM, headless |
| Dialogs, transients, popups, utility windows | Not tested: no dialog-capable app in the VM's test session. The plugin skips windows with a parent, transient, modal or override-redirect | — |

Still to do on NyxOS once it runs Hyprland 0.57.2 with nyx-decor (section 8): clicks on
the headerbar and control (drag, double-click, right-click, buttons), the window menu
opened by them with Shell Core and nyx-shell-qs in the same session, dialogs from real
apps (GTK, Qt, Electron, XWayland), the theme changed through Settings, and Settings'
NyxOS page against the live plugin.

### Deviations from the handoff

- Floating geometry memory lives in the compositor plugin, not in Shell Core: it has to
  act before Hyprland's own placement shows, and it then covers every way a window
  changes mode.
- Minimize is offered only where something brings a window back (Omarchy's floating
  workspaces); NyxOS has no hide mechanism, so it isn't offered there.
- The headerbar has no app icon yet.
- Native apps find their own window by process and title (GTK can't learn its Hyprland
  address); the hover delay is read once per app start.

## 12. Constraints and open points

- **Native window identity:** nyx-ui finds its own Hyprland window by pid and title.
  GTK4 can't learn its window's address or `stableId`. Stage 3 keeps pid plus title,
  remembers the matched address, and re-matches only when the address disappears.
- **NyxOS VM and builds:** stages 4 to 7 need nyx-packages builds and the VM. Each time,
  Ken is asked before the VM starts or anything large is built or downloaded.
- **GTK decoration layout:** whether NyxOS's GTK settings hide GTK's own buttons for
  non-Nyx GTK4 apps decides their default (`preserve-native` or `custom-headerbar`).
  Checked in the VM in Stage 4.
- **Icons in the compositor:** the plugin draws the Nyx symbolic icons from SVG if
  Hyprland's graphics library can rasterize them, otherwise with cairo paths matching
  the icons.
- **Not in this phase:** a snap-layout engine, a NyxOS minimize mechanism, replacing
  hyprbars on Omarchy.
