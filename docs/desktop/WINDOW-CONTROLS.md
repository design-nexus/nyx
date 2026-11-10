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

## 7. Constraints and open points

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
