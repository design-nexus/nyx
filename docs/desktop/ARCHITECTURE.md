# Nyx Desktop — Phase 0: audit and architecture

Status: agreed 2026-10-31 (decisions in §8). Nothing here is implemented yet. Mockups of the dock and
control center: `nyx-design/mockups/desktop/` (approved 2026-10-31).

Scope: Nyx Dock, Control Center, Notification Center, Desktop Widgets, the shared
desktop library and widget framework, and their Settings pages. Per-workspace wallpapers
are deferred (§4.6).

---

## 1. What Omarchy 4.5 already runs

Audited on this machine: `omarchy 4.5.0rc2-1`, Hyprland 0.56.2 (Lua config),
Quickshell 0.3.2, GTK 4.24.1, gtk4-layer-shell 1.3.0.

Omarchy's desktop is **one long-lived Quickshell process** (`quickshell -n -p
/usr/share/omarchy/shell`, aka `omarchy-shell`) hosting plugins. Each plugin has a
`manifest.json`; first-party non-bar plugins can be switched off by listing their id in
`disabledPlugins[]` in the user-owned `~/.config/omarchy/shell.json`. **That is the
supported way to replace an Omarchy part with a Nyx one, with no upstream edits.**

| Area | Omarchy today | Where | What Nyx does |
| --- | --- | --- | --- |
| Dock | `omarchy.dock`: shown only on *floating* workspaces, hidden on tiled ones and behind fullscreen; pins in `shell.json` `dock:`; app grid | `shell/plugins/dock/` | Replaced by Nyx Dock. Disable `omarchy.dock` when Nyx Dock is enabled; import its pins once |
| Notifications | `omarchy.notifications` **owns `org.freedesktop.Notifications`**: grouped stacks, actions, DND, history as JSON files | `shell/plugins/notifications/`, state in `~/.local/state/omarchy/notifications/{history/,live.json,quiet.json}` | Stage A reads Omarchy's store; stage B replaces the daemon (§4.4) |
| Wallpaper | `omarchy.background`: one global image or video on every monitor, symlink `~/.local/state/omarchy/current/background`, transitions, theme-switch prepare/transition IPC, decode at screen size, recovery if a file goes missing | `shell/plugins/background/Background.qml` | Kept. Per-workspace wallpapers deferred (§4.6) |
| Workspace mode | Three per-workspace modes: `dwindle`, `scrolling`, `floating`. Floating isn't a Hyprland layout, so the mode is kept in `~/.local/state/omarchy/workspace-layouts/<id>.lua` | `omarchy-hyprland-workspace-layout-{current,toggle,default}` | Control Center reads the files and calls the commands. No layout engine of our own |
| Bar and panels | `omarchy.bar` + bar widgets (audio, bluetooth, network, power, clock, media, tray…); user plugins `ken.workspaces`, `ken.nyx-assistant`, … | `shell/plugins/bar`, `panels/` | The bar stays; **every bar plugin the Control Center duplicates is removed** (§4.7). Nyx adds two small bar widgets (QML) that open Control Center and Notification Center |
| Other services | lock, idle, night light, OSD, polkit, battery, media (MPRIS) | `shell/plugins/*` | Kept. Control Center drives night light/idle through their commands, never re-implements them |

Installed third-party plugin **`jankeesvw.notification-center`** (history panel over
Omarchy's store) is being removed by the user. Note: it was leaving ~20 orphaned
`inotifywait` watchers on the notifications folder.

No `swww`, `awww`, `hyprpaper` or `swaybg` is installed; Omarchy renders the wallpaper itself.

## 2. What Nyx already has

| Need | Existing | Gap |
| --- | --- | --- |
| Look and widgets | `nyx-design`: `nyx-theme` (tokens, Follow Omarchy, live restyle), `nyx-ui` (cards, rows, popovers, switches, segmented), `nyx-icons` | Desktop surfaces (dock bar, edge panel, tile grid) are new components |
| App actions | `nyx-core::control`: `io.github.design_nexus.nyx.Control` `Describe`/`Call`, registered by most apps (primary instance only) | Needs a running app; no state snapshot/changed signal. The integration audit (`nyx-integration-audit/2026-10-30`) already recommends snapshot + changed-signal capabilities for shell consumers |
| Hyprland IPC | Hand-written socket discovery/event loops in **6+ repos** (home, assistant, passwords, activity, files, calculator) | No shared client. A shared one is the first deliverable |
| Layer-shell | `gtk4-layer-shell` already used by Assistant (visual), Capture, Glimpse | Pattern exists; reuse their setup code |
| Media | MPRIS in Music and Media Player | Use MPRIS directly; no new API |
| Home | `nyx-homed` exposes only `…Home.Automation1`; device state and control live in the Home GUI | **New `…Home.Devices1` on homed** (snapshot, changed signal, set light/scene) for the Home widget |
| Transfers, cloud | `nyx-transferd`, `nyx-cloudd` daemons | Quick Panel/Downloads data via their buses |
| Settings | Sections for workspaces, gestures (incl. workspace loop 1..N, placeholder workspaces `settings-loop-start` and id 11), bar layout, plugins, notifications (read-only over Omarchy history), `shell.json` read/write backend | Add Desktop pages; reuse `backend/shell.rs` to set `disabledPlugins` |
| Notifications | Apps send standard `gio::Notification`s | Center owns history/pinning; apps never keep their own |

## 3. Shape of the system

```
               Hyprland (socket1 requests, socket2 events)
                               │  each process subscribes on its own
   ┌──────────┬────────────────┼───────────────┐
   ▼          ▼                ▼               ▼
nyx-dock  nyx-control-   nyx-notification-  nyx-desktop-
(layer:   center         center (GTK:       widgets
 top)     (layer: top,   panel + toasts)    (layer: bottom,
          edge panel)        │ D-Bus        per monitor)
   │          │              ▼                  │
   │          │          nyx-notifyd (stage B:  │
   │          │          owns org.freedesktop.  │
   │          │          Notifications, SQLite) │
   └────┬─────┴──────────────┴─────────┬────────┘
        ▼                              ▼
  nyx-desktop (crate in nyx-core)   nyx-widgets (crate in nyx-design)
  Hyprland client, monitor/         provider trait, registry, sizes,
  workspace/window model, panel     config schema, update scheduler,
  coordination, workspace profiles, shared caches, tile/desktop
  Omarchy mode reader, system       presentations
  service clients (NM, BlueZ,
  UPower, PipeWire, MPRIS, power-profiles)
```

- **No central desktop daemon.** Hyprland's event socket is cheap to subscribe to more
  than once; each process keeps its own model through the shared crate. The only new
  daemon is `nyx-notifyd`, because the notification name must outlive any UI.
- **Separate processes, measured first**: if milestone 1 shows the GTK processes cost
  too much memory, the three UIs merge into one process; the code stays modular either way.
- **Panel coordination** over D-Bus: each panel owns `io.github.design_nexus.nyx.Panel1`
  (`Show`, `Hide`, `Toggle`, signal `Opened(s id)`). Opening one emits `Opened`; the other
  hides on hearing it. If one isn't running, nothing waits on it.
- **Startup**: every process is a systemd user service (`Restart=on-failure`) started by
  the Nyx installer, toggled with `nyx-control-center --toggle` (single-instance
  GApplication) from keybinds in `hypr/nyx.lua` and the bar widgets.

## 4. Components

### 4.1 `nyx-desktop` (new crate in nyx-core)
- Hyprland client: instance discovery (env, else newest socket), socket2 event parsing
  into typed events, socket1 `j/` requests, **reconnect and full resnapshot** when
  Hyprland restarts. No polling.
- Model: monitors (stable id = make + model + serial, fallback connector name),
  workspaces, windows (address, class, title, workspace, floating, fullscreen, focus
  history for "most recently used").
- **User workspaces = ids 1..=10.** Special workspaces, named workspaces (negative ids,
  including Settings' `settings-loop-start`), and id 11 (the loop placeholder) are never
  user workspaces. A future agent-only workspace uses a reserved `special:` or name
  prefix and is invisible to dock counts, widgets and wallpapers.
- Omarchy workspace mode: read `workspace-layouts/<id>.lua` and default; watch that
  folder with inotify (the Omarchy dock is told over shell IPC; we can't be).
- Panel coordination helper, workspace profiles (`~/.config/nyx/desktop/profiles/<id>.toml`,
  done 2026-11-03: named sets applied by Settings; widgets and wallpaper keys go in a
  profile's `[[workspace]]` entries),
  and thin async clients for NetworkManager, BlueZ, UPower, power-profiles-daemon,
  WirePlumber/PipeWire and MPRIS, so the five apps share one implementation.
- Later, the six hand-written Hyprland loops in other apps can move to it (not in scope).

### 4.2 `nyx-widgets` (new crate in nyx-design)
- `Provider` trait: id, capabilities, config schema, `snapshot()`, `subscribe()`,
  `actions()`. Presentation is separate: a provider has several views (tile 1×1/2×1/2×2,
  desktop compact/medium/expanded).
- Registry of trusted native providers compiled in. No third-party code in the desktop
  processes; a later permissions/isolation model would run plugins out of process (like
  Glimpse's sandboxed plugin protocol).
- One scheduler per process: a shared source per data kind (one CPU sampler at 1 Hz for
  every graph), paused when no visible view uses it.
- First providers: Wi-Fi, Bluetooth, VPN, audio, brightness, power profile, DND,
  workspace mode, media (MPRIS), battery, clock, weather (nyx-weather), Home
  (needs Devices1), up next (nyx-calendard), containers, downloads, pinned notifications.

### 4.3 Nyx Dock (`nyx-dock`)
- One layer-shell surface per enabled monitor; `exclusive_zone = 0`; input region limited
  to the dock (and popovers while open), so the rest of the strip is click-through.
- Apps from `.desktop` files (GIO), windows matched by class/app id; MRU focus via the
  model; middle-click = new instance (`Desktop Action new-window` or re-exec).
- Quick Panels: Nyx apps via Control `Describe`/`Call` when running, daemons via their
  own buses (homed, transferd, assistantd), MPRIS for media, and `.desktop` actions for
  everything. Standard entries (New window, Pin, Quit) always present.
- Window previews: **Hyprland IPC gives no pixels.** Spike `hyprland-toplevel-export-v1`
  (and `ext-image-copy-capture-v1` if offered) on a separate Wayland connection.
  Windows on hidden workspaces may give stale or no frames; then the card shows the last
  cached frame or the app icon. Previews ship only after the spike passes.
- Stacks: `gio::FileMonitor`, thumbnails from the freedesktop thumbnail cache
  (`~/.cache/thumbnails`), Downloads by default; Nyx Cloud folders through cloudd mounts.
- Intelligent hiding from window geometry events: hide when any window on the monitor's
  active workspace intersects the dock rect; reveal at the edge (a 2 px always-mapped
  trigger surface); stay while popovers/drags are open.

### 4.4 Notification Center (`nyx-notification-center` + `nyx-notifyd`)
- **Stage A (no conflict):** the GTK panel reads Omarchy's history/live/quiet files (as
  Settings does now) and asks the shell over its IPC to dismiss/toggle DND. Pinning and
  search are Nyx-side in SQLite keyed by Omarchy's history entries.
- **Stage B (replacement):** `nyx-notifyd` (zbus) owns `org.freedesktop.Notifications`:
  IDs, `replaces_id`, timeouts, actions, `ActionInvoked`/`NotificationClosed`, image
  hints, urgency. It must also honour Omarchy's own hints (`omarchy-exec-argv`,
  `omarchy-actions`) and keep `omarchy-notification-{send,dismiss}` and
  `omarchy-toggle-notification-silencing` working, or Omarchy's scripts (layout toasts,
  battery, updates) break. Switch by adding `omarchy.notifications` to `disabledPlugins`
  only after a compatibility test suite passes; import Omarchy history once.
- SQLite schema: `notifications` (content snapshot), independent `read`, `dismissed`,
  `pinned` flags; retention 7/30/90 days never deletes pinned rows; per-app exclusions and
  "hide content on lock / in toasts" privacy flags; DND schedule.
- Toasts are a separate surface/module from the panel; if the GTK UI crashes, notifyd
  keeps receiving and storing.

### 4.5 Control Center (`nyx-control-center`)
Plugin tiles (2026-11-03): planned in `nyx-control-center/docs/PLUGIN_PLAN.md`.
- Right-edge, full-height layer surface (as in the approved mockup), resident and hidden
  between uses for instant open; keyboard-interactive on demand; Esc closes; a catcher
  surface behind it (on its own layer, with an explicit input region) closes it on a
  click anywhere else, the bar and dock included.
- Dashboard pages = `nyx-widgets` tiles in a 4-column grid of **48 px rows**, layout in
  `~/.config/nyx/control-center.toml` (with a `version`; older layouts migrate on load).
  1×1 toggles are just their icon; Wi-Fi, Bluetooth, VPN and Tailscale are slim 2×1
  bars; each tile kind has its own colour from the theme's swatches (`@cc_blue`…).
- Detail views replace the page: Wi-Fi, Bluetooth, VPN, Tailscale, Screens, Battery.
  The sound tile's popover holds outputs, each app's volume and the microphone.
- Workspace-mode tile shows Omarchy's **three** modes (tiling, scrolling, floating);
  a click goes to the next (`omarchy-hyprland-workspace-layout-toggle`).
- Everything is changed through Omarchy's own commands where it has one (brightness,
  DNS, band, Bluetooth pairing, scale, text size, Do not disturb…), so its keys, OSD
  and bar agree. Links to Nyx Settings pages for anything beyond a quick control.

### 4.6 Desktop Widgets
Built (2026-11-03) in [nyxos-project/nyx-desktop-widgets](https://github.com/nyxos-project/nyx-desktop-widgets),
for NyxOS; its plan is that repo's `docs/PLAN.md`. Every widget is an
out-of-process plugin, sandboxed when third-party.
- `nyx-desktop-widgets`: one bottom-layer surface per monitor; layouts keyed by
  (monitor id, workspace id) plus global widgets; on workspace change the host swaps
  which cached widget trees are visible, never rebuilds them; views of inactive
  workspaces are unmapped and their providers unsubscribed. Edit mode makes the surface
  interactive; otherwise widgets are click-through by default.
- **Wallpapers: deferred.** Omarchy's `omarchy.background` stays as is. Notes for later:
  awww/swww decode on every switch (too slow for 4K per-workspace switching) and
  Omarchy's renderer is global-only, so the likely route is a separate `nyx-wallpaper`
  process (background layer, budgeted texture cache, neighbour preloading) that takes
  over only in per-workspace mode and keeps `current/background` in step for the lock
  screen. The workspace-profile config leaves room for a wallpaper key.

### 4.7 Bar plugins the Control Center replaces
No duplicate features: once Nyx covers everything a bar plugin does, the plugin can come
out of the bar. The feature-by-feature record is [PARITY.md](PARITY.md) (complete as of
2026-11-02); the user removes the plugins themselves.

| Bar plugin | Replaced by |
| --- | --- |
| `omarchy.network` | Wi-Fi tile + view (networks, DNS provider, band, sign-in page, connection details, speed test, QR share) |
| `omarchy.bluetooth` | Bluetooth tile + view (connect, pair nearby devices, forget, battery) |
| `omarchy.audio` | Sound tile + popover (outputs, each app's volume, microphone); Microphone tile |
| `omarchy.power` | Power mode tile; Battery tile + view (draw, capacity, cycles, charge limit) |
| `omarchy.monitor` | Brightness slider + Screens view (each screen's brightness, scale, text size, laptop screen) |
| `omarchy.tailscale` | Tailscale tile + view (machines, search, copy, send and receive files, exit nodes, accounts) |
| `design-nexus.privacy-route` | VPN tile + view: any VPN service (NordVPN, ExpressVPN, PIA, Mullvad, Proton VPN through their tools; any NetworkManager WireGuard/OpenVPN connection) or Tor, one at a time; location search; NordVPN's pause, technology, protocol; Tor's mode, exit, bridges, browser, panic. Setup in Settings › Online Accounts › VPN |
| `harshith.system-monitor`, `mryll.meteobar`, `design-nexus.weather` | Nyx Status bar widget (glance) and the Activity and Weather apps (details) |
| `omacal.upcoming` | Up next tile (Nyx Calendar's `agenda.sqlite`) |
| `jankeesvw.notification-center` | Notification Center |

Stay in the bar: menu, workspaces, active window, clock, indicators, system update,
tray, keyboard layout, `design-nexus.ai-hub`, `flux`, `qs-bitwarden-cli`,
`design-nexus.ticktick`, `design-nexus.obsidian-notes`, `omamail`,
`caseonline.omarchy.office365`, `omarchy.dropbox`, and (decided 2026-11-02)
`ken.nyx-assistant` and `ken.omarchy-backup`.

**The bar keeps glanceable information**; controls and details move to the Control
Center. **Nyx Status** (`design-nexus.status`, QML, shipped with the Control Center)
shows the temperature, CPU and memory (with the CPU temperature; GPU where sysfs has it;
disk space on request) and the Wi-Fi, Bluetooth, volume and battery icons. It reads the
shell's own services (Quickshell's Networking, Bluetooth, PipeWire, UPower) and `/proc`,
so it adds no process; clicks open the Control Center on the matching view, Weather or
Activity. Beside it: the Notification Center's bell and the Control Center button.

### 4.8 Settings
One new **Desktop** group (the existing `desktop` section colour) with pages: Dock,
Control Center, Notifications (replacing today's read-only page), Widgets,
Workspace profiles (widget layout, default mode; copy to other workspaces).
Each page also shows whether the Omarchy part is still active and switches the
`disabledPlugins` entry through the existing `backend/shell.rs`.

## 5. Repositories

| Repo | New? | Contents |
| --- | --- | --- |
| `nyx-core` | existing | + crate `nyx-desktop` |
| `nyx-design` | existing | + crate `nyx-widgets`; desktop components in `nyx-ui` |
| `nyx-home` | existing | + `Home.Devices1` on homed |
| `nyx-settings` | existing | + Desktop pages |
| `nyx-dock` | new | dock |
| `nyx-control-center` | new | control center + its bar widget (QML) |
| `nyx-notification-center` | new | `nyx-notifyd` + panel/toasts + its bar widget |
| `nyx-desktop-widgets` | new | widget host (room for `nyx-wallpaper` later) |

No `nyx-widget-kit` repo: the framework is presentation, which lives in nyx-design per the
integration audit; data clients live in nyx-core. Every new repo pins nyx-core/nyx-design
by rev, follows STYLE.md 2.0 and AGENTS_COMMON, and gets added to the umbrella
`suite.toml` and the shared `hypr/nyx.lua` rule list (layer rules, keybinds).

## 6. Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Omarchy is `4.5.0rc2`; plugin API, state files, hints may change | Breaks readers of Omarchy state | Read through one module in `nyx-desktop`; tolerant parsing; test against each Omarchy update |
| Replacing the notification daemon breaks Omarchy scripts | Lost layout/battery/update toasts, broken DND toggle | Stage A first; stage B only behind a compat suite incl. Omarchy's own hints and scripts |
| Window thumbnails unavailable or stale for hidden workspaces | Previews blank | Spike first; icon/last-frame fallback |
| Memory: five GTK4 processes (≈40–70 MB RSS each) | Heavier than the Quickshell equivalents | Measure in milestone 1; if over budget, merge dock + control center + notification UI into one process (the code is already modular) |
| Fullscreen/idle/lock interactions with layer surfaces | Dock over fullscreen, widgets over lock | Layer choice (bottom/background for widgets), hide on fullscreen events, tests on lock |
| Home widget needs a new homed API | Blocks the Home widget | Small additive interface; widget hides if absent |
| Multi-monitor ids unstable (no serial) | Layouts attach to the wrong screen | Fall back to connector name; keep orphaned layouts until the monitor returns |
| Battery/laptop performance | Wakeups, GPU use | 1 Hz shared sampler, pause hidden views, reduce-motion and battery modes; measure wakeups with `powertop`/`perf` |

## 7. Milestones

Each ends with tests, `cargo check`/clippy, install, and a measurement note.

1. **Foundation**: `nyx-desktop` (Hyprland client + model + reconnect, Omarchy mode
   reader, panel coordination) with unit tests over recorded event streams; idle CPU
   and RSS of a minimal layer-shell GTK process measured.
2. **Dock core**: launch/focus/MRU, pins, indicators, badges/progress
   (`com.canonical.Unity.LauncherEntry`), intelligent hiding, per-monitor config;
   `omarchy.dock` disabled when on. Then thumbnail spike → previews, Quick Panels, stacks.
3. **Widget framework + Control Center**: `nyx-widgets`, system providers, dashboard
   pages, popovers, detail views, edit mode, bar widget; Home.Devices1 in nyx-home;
   each bar plugin in §4.7 removed as its replacement is checked.
4. **Notification Center stage A**, then **stage B** (`nyx-notifyd`, compat suite,
   history import, pinning, DND schedule, privacy).
5. **Desktop widgets**: per-monitor hosts, per-workspace layouts, edit mode.
6. **Settings pages, integration, benchmarks** (idle CPU, wakeups, RSS, GPU memory,
   switch latency on 1×4K and 2×4K), reliability passes (Hyprland restart, hotplug,
   sleep/resume, logout).

## 8. Measurements

Milestone 1, 2026-10-31, on the laptop (Intel(R) Core(TM) Ultra 9 285H, eDP 2560×1600 @1.6 + a headless output),
release build, 30 s idle after 8 s settling, while the user worked normally:

| Process | RSS | PSS | Private | CPU over 30 s | Wakeups / 30 s |
| --- | --- | --- | --- | --- | --- |
| `nyx-desktop` watcher alone (no GTK) | 3.2 MiB | | | 0 s | 38 (Hyprland events) |
| Minimal GTK4 layer-shell surface (10 × 48 px icons + watcher) | 127 MiB | 56.6 MiB | 32.7 MiB | 0.01 s (0.03 % of a core) | 62 |

RSS is mostly the shared GL driver and GTK libraries. What each extra GTK desktop process
really adds is its private memory, about 33 MiB at this floor, so three separate panel
processes cost about 65 MiB more than one combined process. That's within reason for the
recoverability it buys: **keep separate processes** (decision 1), and measure again once
the real dock and Control Center exist.

## 9. Decisions (2026-10-31)

1. **Processes**: separate, as the brief says; merge the three UIs into one process only
   if milestone-1 measurements show the memory cost is too high.
2. **Wallpapers**: per-workspace wallpapers skipped for now; Omarchy's renderer stays.
3. **Notifications**: staged (A: Nyx UI over Omarchy's daemon; B: `nyx-notifyd` behind a
   compat suite).
4. **Repos** as in §5 (four new repos, no `nyx-widget-kit`).
5. **Bar**: the Control Center replaces the plugins in §4.7's table and nothing else; the
   bar keeps glanceable indicators (temperature, CPU/RAM, connection/volume/battery)
   that open the Control Center.

## 10. Changes while building (2026-11-01)

- **Widget framework location**: `nyx-widgets` (live values, tile sizes, page layout)
  and `nyx-providers` (system data) live in `nyx-control-center` for now, not in
  nyx-design and nyx-core, so they can change without a shared-crate pin bump each time.
  They move when Desktop Widgets (milestone 5) becomes their second user.
- **`Home.Devices1`** on `nyx-homed` (nyx-home `5860fcf`): `Snapshot()` (lights,
  switches, fans, climate and scenes by room, as JSON) and `Call(entity, service, data)`
  with a short allow-list. The Control Center's Home tile reads it every 3 s while shown.
  A light group whose lights are hidden in Home Assistant stands for them.
- **Window previews** use `ext-image-copy-capture` with the toplevel's identifier, which
  is Hyprland's `stableId` (`nyx-desktop` `44d4d4c`). Windows on hidden workspaces show
  their last frame.

## 11. Notification Center, stage A (2026-11-01)

Built in `nyx-notification-center` (approved mockup: nyx-design `2302785`).

- **What Omarchy keeps**: `history.json` holds closed rows only for 24 hours (at most
  100); `live.json` the pop-ups on screen; `quiet.json` Do not disturb. Each row has a
  stable `key`, the click command (`execArgv`) and Omarchy's command buttons
  (`execActions`), and on closing a `closed_reason`: `expired`, `dismissed`, `activated`
  or `closed` (withdrawn by the app).
- **`nyx-notifyd`** (no GTK, ~6 MiB) watches that folder with inotify, copies every row
  into `~/.local/share/nyx/notifications.db` and serves it as
  `io.github.design_nexus.nyx.Notifications1` (JSON, `Changed` signal). It also runs the
  Do not disturb schedule (switching Omarchy's setting only at the start and end of the
  quiet hours) and hourly retention, and writes `~/.local/state/nyx/notifications.json`
  (unread count) for the bar button to watch.
- **Inbox rule**: `expired` stays in the Inbox; `dismissed`, `activated`, `closed`, and
  Omarchy's passing senders (`omarchy-action`, `notify-send`) go straight to history.
  Replaced text (same key) makes a row unread again. A deleted row leaves a `gone` marker
  for three days so Omarchy's copy doesn't bring it back.
- **Limits until stage B**: an app's own D-Bus action buttons work only while its pop-up
  is up (Omarchy's command buttons keep working); "hide content when locked" waits for
  Nyx-drawn pop-ups and lock-screen surfaces.
- Keys: Super + N (Notification Center), Super + D (Control Center).

## 12. Notification Center, stage B (2026-11-01; built, not switched on)

- **Two modes of `nyx-notifyd`** (`nyx-notifyd --mode`): *Omarchy* (stage A, the
  default) and *Nyx*, where it serves `org.freedesktop.Notifications` itself (Notify,
  CloseNotification, GetCapabilities `actions body icon-static persistence`,
  GetServerInformation; NotificationClosed, ActionInvoked, ActivationToken). Switched
  with `nyx-notification-center --use-nyx-popups` / `--use-omarchy-popups`, which also
  puts `omarchy.notifications` in `disabledPlugins` (or takes it out), turns the bridge
  plugin on or off, and restarts Omarchy's shell only if it keeps the bus name. If Nyx
  doesn't get the name, it switches back on its own.
- **Pop-ups** are drawn by the Notification Center process from `nyx-notifyd`'s `Popup` /
  `PopupClosed` signals: top right, newest on top, at most four, held while hovered,
  5 s / 8 s / until dismissed by urgency (Omarchy's timings). A pop-up timing out leaves
  the notification **open** in the Inbox, so the app's own buttons keep working there;
  it closes (and the app is told) when clicked, dismissed, cleared, withdrawn, or its
  explicit timeout runs out. `transient` ones close with their pop-up. Do not disturb
  still lets critical ones and verification codes through.
- **Omarchy compatibility**: the bridge plugin `design-nexus.notifications` answers the
  shell's `notifications` IPC (ping, isDnd, toggleDnd, setDnd, act, dismissOne,
  dismissAll, invokeLast, invokeAction, keyboard, showHistory, dismiss, count) by calling
  `nyx-notifyd`, so Super + comma and friends, `omarchy-toggle-notification-silencing`,
  `-dismiss` and `-wait` keep working. Omarchy's hints (`omarchy-exec-argv`,
  `omarchy-actions`, `omarchy-glyph`) are honoured; Do not disturb stays in
  `quiet.json` with Omarchy's other fields kept.
- **Compatibility suite**: `cargo test -p nyx-notifyd --test compat`, a private
  `dbus-daemon` with scratch folders, nine tests including the real `notify-send` and
  `omarchy-notification-send`.
- **Known gaps after switching**: Omarchy's centre-bar Do not disturb indicator reads
  Omarchy's own service, so it stops tracking (the Notification Center's bell shows it);
  nothing on the lock screen; Omarchy's per-app snooze isn't carried over.
- **Status (2026-11-01)**: installed, Omarchy mode. The user keeps Omarchy's
  notifications and the old bar plugins for now.

## 13. Deferred (2026-11-01)

- **Desktop Widgets (milestone 5)**, with per-workspace wallpapers (§9.2). The widget
  framework (`nyx-widgets`, `nyx-providers`) stays in `nyx-control-center` until then.

## 14. Milestone 6 (2026-11-01)

### Settings pages

Nyx Settings → Desktop gains **Dock**, **Control Center** and **Notifications** (nyx-settings
`1943fc6`), each shown only when its program is installed and changing it the way the
program does: `dock.toml` (the dock reloads it; the options appear once the dock has
written it on first start) and `nyx-dock --enable/--disable`; the Control Center's
layout file plus a restart of its hidden service; `nyx-notifyd`'s settings over
`Notifications1` (through `busctl`, so Settings links against nothing of the Notification
Center's), including who shows pop-ups. Our bar widgets get on/off switches.

### Measurements

Laptop (Intel Core Ultra 9 285H; GTK on the Intel GPU), release builds, test copies on
the headless output only, while the user worked normally. Scripts: `docs/desktop/bench/`.
"GPU" is the buffers the process holds (DRM `fdinfo`, `drm-total-*`). Wakeups are context
switches per second.

| Process | Private memory | GPU | CPU (idle) | Wakeups |
| --- | --- | --- | --- | --- |
| Control Center, hidden | 10 MiB | 52 MiB once opened (0 before) | 0.00 s / 30 s | 1/s |
| Notification Center, hidden | 10 MiB | 0 | 0.01 s / 30 s | 1/s |
| nyx-notifyd | 8 MiB | 0 | 0.00 s / 30 s | 2/s |
| *Omarchy's shell, same moment* | *453 MiB* | *508 MiB* | *2.02 s / 30 s* | *381/s* |

| Shown on one screen | 2048×1280 @1.6 | 3840×2160 @1 |
| --- | --- | --- |
| Dock: private / GPU | 61 / 28 MiB | 42 / 23 MiB |
| Dock: CPU, wakeups (while the user worked) | 1 % of a core, 148/s | 0.5 %, 131/s |
| Dock: window arrives or leaves → redrawn | 5–23 ms | 5–26 ms |
| Control Center open: private / GPU | 41 / 45 MiB | 60 / 83 MiB |
| Control Center: cold start → on screen | 175 ms | 163 ms |
| Notification Center open: private / GPU | 63 / 39 MiB | 62 / 69 MiB |
| Notification Center: cold start → on screen | 111 ms | 127 ms |

- The dock's wakeups follow Hyprland's events: it recomputes on focus, window and
  workspace changes (never on title-only ones) and rebuilds widgets only when what it shows
  changed. With nobody at the desktop it's near zero (milestone 1's watcher: about 1
  event a second).
- Opening a panel that's already running is one `set_visible`: a frame, not a start.
- **Two 4K screens**: the dock draws one surface per screen in one process, so a second
  4K screen adds about one more dock surface (~23 MiB GPU, a few MiB private); the panels
  are on one screen at a time, so they don't change. (Measured on one 4K output; a second
  wasn't created, to keep test outputs to one.)

### Reliability passes

- **Screen unplugged and plugged in** (a temporary headless output, the dock on it): the
  dock leaves with the screen and comes back with it, one dock and one edge strip after
  three quick unplug–replug cycles; the process never stopped.
- **nyx-notifyd restarting under the panel** (Nyx mode, private bus): the panel stays up,
  the next notification after the restart pops up, history keeps both. A notification
  sent while it was down was refused, so Nyx mode now installs D-Bus activation for
  `org.freedesktop.Notifications` (through systemd); switching back removes it.
- **One nyx-notifyd at a time**: a second copy now exits instead of taking the running
  one's name (an old build started by hand had taken it and systemd stopped the service).
- **Hyprland restarting**: the `nyx-desktop` watcher reconnects (unit-tested over a
  closed socket in milestone 1); not run live, as it would end the user's session.
- **Sleep and resume, logging out**: not run (they'd interrupt the user). All services are
  `PartOf=graphical-session.target` with `Restart=on-failure`.

## 15. Control Center rework (2026-11-02)

After the user tried it: everything was too big, so rows went from 82 to 48 px; toggles
became icon-only; tiles got colours; tooltips say the state and what a click does, in a
lighter style. Then everything the bar plugins did was brought in (§4.7, PARITY.md):

- **New providers** (`nyx-providers`): `tailscale` (status, machines, exit nodes,
  accounts, the Taildrop receiver), `routes` (NordVPN, Tor through `tormarchy`), `dns`
  (DNS provider, band, portal, connection details from `omarchy-network-status`),
  `display` (screens through Omarchy's commands), `calendar` (Nyx Calendar's agenda,
  read-only, a published contract); `audio` gained microphones and who is recording,
  `bluetooth` nearby devices, pairing and forgetting, `power` battery details.
- **Brightness fix**: it set the first backlight (`nvidia_0`), not the one lighting the
  laptop's screen (`intel_backlight`); it now goes through `omarchy-brightness-display`
  for the focused screen (DDC monitors too).
- **Layout migrations**: version 2 renamed the old `vpn` tile (it showed Tailscale) to
  `tailscale` and added the new `vpn`; version 3 added `upcoming` and `microphone`.
- **Lesson**: a tile mustn't hide itself in its own update. A hidden widget is never
  mapped, so its subscription never starts and it never comes back; grey it out instead.
- The suite's shared nyx-design revision moved up to `976fed9`, which the dock, Control
  Center and Notification Center build against.

Status: installed. Not yet tried by hand: the new controls (pairing, VPN switching, DNS
with its polkit prompt, edit-mode dragging). Hyprland restart, sleep/resume and logout
haven't been run live.

### Universal VPN (2026-11-02)

The VPN tile isn't NordVPN's: `nyx-providers::vpn` finds every service set up (each
provider's own tool, or NetworkManager VPN/WireGuard connections for providers without
one) and keeps one connected at a time, Tor included. Adding a service is in Nyx Settings
› Online Accounts › VPN (nyx-settings `9e93615`): install (AUR in a terminal, or the
provider's page), sign in the tool's way, or import a `.conf`/`.ovpn` file. The sign-in
service (nyx-accounts) isn't involved: VPN sign-ins are each tool's own. ExpressVPN's
status and Proton's CLI (beta) follow their documented commands and are untested here.
