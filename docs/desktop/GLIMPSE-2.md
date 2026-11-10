# Glimpse 2.0: app actions and mini-app panels

Status: audit and contracts done 2026-11-09 (phase 1 of 7). The handoff text is "Nyx
Glimpse 2.0: Unified Application Commands and Interactive Mini-App Panels".

The contract is [nyx-core/crates/nyx-actions/docs/CONTRACT.md](https://github.com/design-nexus/nyx-core/blob/main/crates/nyx-actions/docs/CONTRACT.md).

Decisions taken with Ken on 2026-11-09:

- One registry, as a library: AI Core's action registry moves into a new nyx-core
  crate, `nyx-actions`, linked by AI Core, the Glimpse backend and the `nyx` command.
  No new daemon. AI Core keeps brokering for the Assistant and agents.
- Apps that aren't running: each app installs a static manifest (the same JSON its
  `Describe` returns) and a D-Bus service file; running an action starts it headless.
  Opening Glimpse reads files and starts nothing.
- Panels and every new Glimpse feature are in the Quickshell panel only, on the
  laptop (Standalone, inside `nyx-shell-qs`) and on NyxOS (Shell Core). The GTK panel
  stays as the fallback and isn't changed.

## 1. What exists today

### Actions

| Piece | Where | Today |
| --- | --- | --- |
| Registry | nyx-ai `nyx-ai-core/src/actions.rs` (`8adb415`) | Lists running apps' Control interfaces (bus names under `io.github.design_nexus.nyx.`, `Describe` with 2 s timeout, 10 s cache) and providers on AI Core connections (`serve_actions`). Checks: action exists and is available, untrusted callers read-only, `ask` needs `confirmed`, arguments against the JSON Schema (256 KiB cap); then routes with a timeout (30 s default, 300 s cap) and cancel. Logs action, caller, owner, outcome and duration only. |
| Types | `nyx-ai-proto` | `ActionSpec` (`id`, `description`, `input_schema`, `output_schema`, `permissions`, `confirmation`, `side_effects`, `timeout_ms`), `ActionInfo` (`owner`, `source`, `available`). `ActionSpec` is `deny_unknown_fields`, so `list_actions` replies can't gain fields without breaking older clients, despite PROTOCOL.md's "replies may gain optional fields". |
| App side | nyx-core `nyx-core/src/control.rs` (`serve`, `serve_async`) | `Describe() -> s`, `Call(s, s) -> s` on the GApplication connection; handlers on the main thread; `home_path` and `save_target` helpers. No caller check. Only while the app runs. |
| Callers | Glimpse `providers.rs` `SharedActions` | Actions without required arguments only, arguments `{}`, "ask" on a second Enter. |
| | Assistant `abilities/nyx-apps` 1.6.0 | `nyx-ai actions` and `nyx-ai act … --yes` after its own approval; falls back to `busctl … Call` when AI Core isn't there. |
| | `nyx-ai actions`, `nyx-ai act ACTION [JSON] [--yes]` | JSON output only. |
| | nyx-share-apps, nyx-clipboard daemon, Control Center's Backup provider | Call Control directly. |

Apps on `nyx_core::control` (about 25): settings, chat, capture, pulse, theater,
contacts, mail, pdf, photos, git (`repo.*`), maps, office (`write.*`), news, torrents,
fonts, notepad, media player (`video.*`), archive, music, calendar, reminders, notes
(through its own integrations module) and weather. Backup's daemon serves its own
`Describe`/`Call` with per-caller grants.

Gaps against the handoff:

- **No risk declared anywhere.** No app sends MCP annotations, so every action is
  "unknown": it asks first and untrusted callers can't run it, even `music.status`.
- **No names, aliases, keywords, positional order, availability or privileged class.**
  Glimpse shows the description's first sentence as a title.
- **Closed apps are invisible.** Only Backup (`nyx-backupd`, D-Bus activated) answers
  without a window.
- **Weather's tools are dropped**: named `current`, `forecast`, … without a
  namespace, with a `parameters` map instead of `inputSchema`.
- **Apps don't know who calls them.** Any same-user program can `Call` any action.
- **No versioning** of the Control interface.

### The `nyx` command

Two different bash scripts: the laptop's installer (`nyx/bin/nyx`: install, update,
uninstall, list, icons, share, dev, release) and NyxOS's Nix wrapper
(`nyxos/pkgs/nyx-cli/nyx.sh`: install, remove, update, list, search, run, shell,
rollback, history, clean, icons, share, plugin, system, service, agent; anything else
goes to `nix`). No Rust `nyx`, no completion, no `--json`; no Nyx CLI uses clap.

### Glimpse

At nyx-glimpse `d851258` the Quickshell panel is Glimpse on the laptop: category
headings, previews (app cards, highlighted text, pictures, PDF pages, audio and video),
the calculator, the action panel (aliases, favorites, desktop and plugin actions),
history, `pw` and `cb`, the plugin window, Add folder. `nyx-glimpse ui qml|gtk`
switches; the install links the panel into `nyx-shell/components` and enables
`nyx-glimpse-backend.service`. On the laptop `nyx-shell-qs` runs without Shell Core
(Standalone); on NyxOS Shell Core is off by default (`nyx.shell.enable`).

Must keep working (all of it is in the backend library or the QML panel now):

- Super+Space, `--toggle`, `--hide`, `--query`, `--plugins`, `--add-folder`, `--add-plugin`.
- Apps, files, content words, semantic search through AI Core (and without it),
  utilities (calculator, units, currency), power rows, Omarchy menu, `service NAME`,
  plugins (sandboxed), shared actions.
- `pw` and `cb` isolation: those queries reach no other provider (`3d0fd1d`).
- Ranking: matcher tiers, aliases, favorites, learning with a 14-day half-life.
- Freshness: generations, 10 ms and 150 ms coalescing, cancel, per-provider timeouts.
- Previews, the action panel, plugin host actions (Notes, Capture, Mail, Calendar,
  Reminders), the plugin window.

### Shell and design

- Shell Core overlays: `passive`, `transient`, `persistent`, `presentation`,
  `secure-external`; groups, keyboard modes, placement, focus restoration; no pin
  operation. `Standalone.qml` emulates the operations in-process without Shell Core.
- `BackendClient` and nyx-ui-link: topics with merge patches, reference-counted
  `watch`/`unwatch`, free-form requests. Glimpse's backend already uses it.
- `Nyx.Ui` and `Nyx.Theme`: live system theme (Catppuccin Mocha by default), semantic
  tokens, typography, spacing, `FocusRing`, `StateView` (loading, empty, error),
  reduced motion. Panels need nothing new from it.

### Backends for the first panels

| App | Today | Missing for its panel |
| --- | --- | --- |
| Music | `music.search`, `play`, `queue`, `status`, `control`; GStreamer and MPRIS inside the window's process; playlists in its SQLite library; volume in-process; the sink only through `MUSIC_AUDIO_SINK` | Risk; volume, playlists, outputs; a `playback` topic; a headless service mode that stays while playing |
| Home | `nyx-homed` (D-Bus activated) over Home Assistant: `Home.Devices1` `Snapshot` (rooms, devices, scenes) and `Call` limited to an allowlist (lights on/off with brightness and colour, switches, fans, scenes, climate temperature); `Home.Automation1` workflows | A Control interface on `nyx-homed`; a `devices` topic; a caller check (`Devices1` has none) |
| Files | One binary crate; `FileSource` listing, `OperationProvider` (trash by default, conflict choices, undo); FileManager1 and the FileChooser portal by D-Bus activation | A Control interface in service mode over those traits; a manifest |

Other apps for later phases: Notes (vault actions; writes are proposals reviewed in
Notes), Calendar and Reminders (full sets, from EDS), Weather (names to fix),
Clipboard (`Clipboard1`, Glimpse scope only), Passwords (its own socket and scopes;
Glimpse's `vault.rs`), Containers (no Control), Backup (grants), Devices
(`nyx-connect`), AI Hub (`omarchy-ai-hub`, outside the suite).

## 2. Reuse and change

| Part | Reuse | Change |
| --- | --- | --- |
| Registry | AI Core's checks, D-Bus routing, `Describe` parsing, limits and tests | Moved into `nyx-actions`; manifests, activation, merging, resolution, typed errors added |
| AI Core | Protocol v1, `serve_actions`, its trust rule | Uses `nyx-actions`; `list_actions` with `detail: true` for API 2 fields; lists installed apps' actions too |
| App helper | `nyx_core::control` and its path helpers | API 2: `Describe` with `x-nyx`, `Invoke`, `State`/`Watch`/`StateChanged`, caller check and risk rules enforced in the helper |
| CLI | Both `nyx` scripts and their built-in words | A Rust frontend (`nyx-actions`) for `nyx apps` and `nyx <namespace> …` |
| Glimpse | Backend providers, matcher, generations, QML panel and action panel | A commands provider on `nyx-actions` in place of `SharedActions`; argument completion, confirmation and results; panel mode |
| Shell | Overlay policies, Standalone | A pin operation in both |
| Assistant | Its approvals, grants and journal | None needed; its `busctl` fallback moves to `nyx-actions` |

## 3. Security findings

To fix within the phases, not left behind:

1. `nyx_core::control` accepts any same-user caller for any action (phase 2: caller
   check and risk rules in the helper).
2. `Home.Devices1.Call` has no caller check, so any program can switch lights and
   set the climate (phase 5).
3. Every action is "unknown" risk, which makes the read-only rule for untrusted
   callers useless and trains people to confirm reads (phases 2, 5 and 6: risk on
   every tool).
4. The Assistant's `busctl` fallback becomes read-only under API 2 (it would be
   untrusted); it moves to the trusted `nyx-actions` command in the same change.

## 4. Phases

1. Audit and contracts (this document and the contract).
2. `nyx-actions`, `nyx_core::control` API 2, AI Core on the library, the CLI.
3. Glimpse commands: arguments, completion, confirmation, results.
4. Panel framework: modes, lazy panels, the state bridge, open in the app.
5. Music, Home and Files.
6. Notes, Calendar, Reminders; Weather's names.
7. Pinning (Shell Core and Standalone), accessibility, performance.

Cross-repository order: nyx-core (crate, helper) → nyx-design's nyx-core pin (apps
carry the revision nyx-design uses) → nyx-ai → nyx-glimpse → each app → nyx and
nyxos (`nyx` routing) → nyx-packages (packages, manifests, service files) on a branch.

## 5. Progress

### Phase 1: audit and contracts

- The contract: nyx-core `crates/nyx-actions/docs/CONTRACT.md`.
- This document.
- Nothing built or installed; no behaviour changed.

### Phase 2: registry and CLI

- **nyx-core `0efc823`, `f6fd2e5`.**
  - `crates/nyx-actions` has:
    - the contract's types, parsing API 1 and API 2 descriptions;
    - `check_call`, shared by every frontend and the app helper;
    - deterministic word resolution (namespaces, aliases with preset arguments, unique prefixes, the default action for free words, positional arguments and flags converted by schema, "did you mean");
    - typed errors with exit codes;
    - the registry (manifests in `nyx/actions`, running apps, D-Bus activation, `Invoke` or API 1's `Call`, timeouts).
  - The `nyx-actions` command (`apps`, `help`, `run`, `call`, `has`, `complete`, `completion bash|zsh|fish`).
  - `nyx_core::control` serves API 2 with the same `serve`/`serve_async`, so no app changes yet:
    - callers identified by their program (`nyx-peer`);
    - only Nyx programs get past read-only;
    - confirmation and schemas checked before the handler;
    - `Invoke` with typed errors;
    - `State`/`Watch`/`Unwatch`/`StateChanged`, sent to watchers only and coalesced to 10 a second;
    - `serve_with` (the caller and `confirmed` for the handler);
    - `describe_if_asked` for installers.
- **nyx-ai `74547c5`.** AI Core's D-Bus discovery and routing are nyx-actions:
  - Installed apps are listed (`source: manifest`) and started for a call.
  - Served actions get the same checks.
  - `list_actions` gains `detail` (the apps as nyx-actions describes them). Replies without it are byte-for-byte version 1, which `ActionSpec`'s strict reading needs.
  - `nyx-ai-client` has `list_actions_detail`, which falls back on an older AI Core.
- **nyx `bin/nyx`, nyxos `0562691` (`pkgs/nyx-cli/nyx.sh`).**
  - `nyx apps`, `nyx APP …` and `nyx completion SHELL`. Built-in words win.
  - The laptop gives nyx-actions' "did you mean" for unknown words. NyxOS still sends them to `nix`.
  - `install-suite.py` builds nyx-actions at `suite.toml`'s new `actions_revision`.
- **nyx-assistant `e13a92d`.** `nyx-apps` 1.6.1 calls apps through `nyx-actions call` when AI Core isn't there; under API 2, `busctl` would be read-only.
- **Tests:**
  - nyx-actions: 18 unit tests, plus a private-bus test of an API 2 app, an API 1 app, an activated app, a closed app, refusals, confirmation, a timeout, typed app errors, state and manifest reloads.
  - nyx-core: a private-bus test of the helper (trusted and untrusted callers through `Invoke` and `Call`, sensitive topics, `StateChanged` to a watcher, refused calls never reaching the handler).
  - nyx-ai: the whole suite against the stub worker, plus a protocol test of `detail`.
  - The umbrella's suite tests; shellcheck on both `nyx` scripts.
- **Installed on the laptop:** `nyx-actions` and `nyx` in `~/.local/bin`, AI Core (`./install.sh`; the pinned llama.cpp build was current, so nothing downloaded), and the `nyx-apps` ability (copied while the Assistant was stopped).
- **No app ships a manifest or API 2 tools yet**, so `nyx apps` lists nothing: phases 5 and 6.
- **Not yet:**
  - nyx-packages (an `nyx-actions` package for `nyx` on NyxOS) waits for nyx-core on GitHub.
  - nyx-design's nyx-core pin moves when apps adopt API 2, not before: Glimpse needs only the separate `nyx-actions` crate.
  - `requires` checks `program:NAME` only; other capability kinds count as present.

### Phase 3: Glimpse commands

- **nyx-core `17fa6ff`, `2b4874e`.** `resolve::complete` (namespaces, verbs and aliases, an argument's values and flags) is shared by the CLI and Glimpse. `Registry::cached` gives the catalog without waiting for apps. Errors from starting an app use its name.
- **nyx-glimpse `485f0d1`.** In the Quickshell panel:
  - A new `commands.rs`, on the same registry. A search starting with an app's name gives command rows:
    - the app's commands;
    - the typed command with its arguments resolved;
    - completions of the word being typed.
  - Typed as a command, they come first under Commands. The app's name alone puts them after apps and files.
  - Other searches match actions by title, alias and keyword. This replaces AI Core's shared actions in the backend, keeps the `action:` IDs so favorites and learning carry over, and drops the old "no required arguments" limit.
  - Each row has a tag: Needs TITLE, Asks first, or Unavailable.
  - Keys: Tab takes the row's words. Enter runs a ready command, fills the search for one with missing arguments, or gives the reason for one that's unavailable.
  - Confirmation: a card in the preview ("…? Notes deletes or overwrites. Press Enter again…") with the arguments. The second Enter sends `confirmed`, and the app checks again.
  - Results show in the preview: lists as lines, objects as fields, messages in the status line.
  - The GTK panel is unchanged and keeps AI Core's shared actions.
- **Tests:**
  - nyx-actions: the completion test.
  - Glimpse: `commands.rs` (rows, fills, tags, IDs, result kinds) and a backend test (commands from a manifest come first when typed as commands, the app's name alone finds the app first, `pw` stays the vault's).
  - Glimpse's library and `search_workflows` suites; clippy clean.
- **Checked on a headless output**, on a test copy with its own backend socket, scratch XDG folders, a private D-Bus with a stand-in Weather app that D-Bus starts, `NYX_SHELL_NO_KEYBOARD=1` and only the Glimpse component. The checks:
  - `notes` lists Notes' commands, tagged Unavailable for a closed app that only answers while open.
  - `notes create Project ideas` resolves the title, and the preview says why it can't run now.
  - `weather ` → Enter starts Weather through D-Bus and shows its result in the preview.
  - Focus never moved.
- **Installed** with `./install.sh glimpse` (backend and `nyx-shell-qs` restarted).
- **Not yet:**
  - Suggestions from apps' `x-nyx.suggest` actions (no app declares one yet).
  - Completion of paths.
  - Natural-language interpretation through AI Core (optional, not started).
  - Commands for actions that only AI Core's connections serve (only `glimpse.search` today, which Glimpse leaves out anyway).

### Phase 4: mini-app framework

- **nyx-core `3e7a698`.** `Registry::watch(app, topic)`: Watch, the state now, then `StateChanged` merge patches (the whole state again after a gap), and an end when the app goes. Dropping it sends `Unwatch`. Also `apply_patch`.
- **nyx-glimpse `897db54`:**
  - **Search, panel and full app.** A query whose first word is exactly an app's name or alias, for an app whose manifest names one of Glimpse's panels, lists the app first under Applications (*Example at a glance*). While that row is selected, the preview area is the panel.
    - Enter moves the keyboard into the panel; Escape gives it back with the search as it was.
    - Ctrl+Enter opens the full app, through its `open` action or its desktop entry.
    - The words after the name reach the panel (`music jazz`, so `jazz`).
  - **Panels.** Panels are Glimpse's QML only (`quickshell/Glimpse/panels/<id>/Panel.qml`, with `commands::PANELS` as the allowlist; `example` exists for test copies alone), loaded asynchronously when shown and destroyed after. They see only `PanelHost`: `query`, `topic(name)`, `run(action, arguments, done)` (only their own app's actions, checked as any other call, with an in-panel "Go ahead" for those that ask), `open`, `say` and `back`. Loading and error states use `StateView`. A panel's preferred size sizes the frame, within the screen.
  - **Live state.** The backend publishes `panel:<app>:<topic>`. The first viewer starts a nyx-actions watch (on nyx-ui-link's `on_watch`); the last one leaving stops it, and the app hears `Unwatch`. The panel is kept across a pending search, so typing on doesn't restart it. The catalog is asked once at start, so the first look already knows which apps run.
  - **Security.** The backend's socket takes only Glimpse's own programs (`qs`/Quickshell and `nyx-glimpse`; `NYX_GLIMPSE_ALLOW_ANY=1` for test copies). Before this, any same-user program could have run commands with `confirmed` as Glimpse.
- **Tests:**
  - nyx-actions: a private-bus watch test (state, a patch, `Unwatch` on drop); merge-patch unit tests.
  - Glimpse: panel offers (only the whole app name, only allowlisted panels, the query and size) and the peer check; 28 library tests; clippy clean.
- **Checked on a headless output** (test copy, private bus, a stand-in app in Python serving Control API 2 with a ticking `status` topic):
  - The panel appears for `example world`, with the query and a live count.
  - `PanelRun` cases: ping; reset asks, then runs once confirmed, and the unconfirmed call never reached the app; another app's action is refused.
  - Leaving the panel sends `Unwatch`, and coming back watches again.
  - Typing `example a`, then `ab`, then `abc` kept one watch.
  - Focus never moved.
- **Installed;** the real `nyx-shell-qs` reconnected to the restricted socket.
- **Not yet:**
  - Real panels (Music, Home, Files in phase 5).
  - Panel keyboard checks on a real keyboard (the test copy runs without one).
  - Pinning (phase 7).

### Phase 5: Music, Home and Files

- **nyx-core:**
  - `80fb009`: apps D-Bus has just started are described once their control interface appears.
  - `3691c99`: the control helper holds an app while its topics are watched.
  - `d78dba3`: `nyx-actions`' `server` feature, the control interface for zbus daemons, with the helper's rules and a private-bus test.
  - `d53074b`: positional lists take their words (`nyx files copy a b ~/Docs`).
  - `69277d8`: 25 s for a cold start.
  - `47c5e0f`: the helper keeps answering when the returned `Service` isn't kept. Before this, every app on `serve`/`serve_async` would have stopped answering once rebuilt on it; a regression test now covers it.
- **nyx-design** `b3bfdcc`, `99d1ef4`, `048e7bf`, `06f65ab`: the one nyx-core pin the apps carry. Committed from a clean worktree each time, leaving another session's work in progress alone.
- **Music** (nyx-music `a0020a3`, `edf9a2d`):
  - API 2 tools with risk, positional arguments and aliases (`nyx music pause`, `nyx music play album Blue Train`), plus `music.volume`, `music.playlists` and `music.open`.
  - `playback` and `playlists` topics, worked out only while watched.
  - A headless service mode: `--gapplication-service` handled by Music itself (GLib leaves it to apps that handle their own command line), held while playing, quitting after 10 s idle.
  - The install writes the manifest and D-Bus service.
  - Not done: output selection (Music has only the developer `MUSIC_AUDIO_SINK`; switching per app needs engine work).
- **Home** (nyx-home `286c9cc`):
  - `nyx-homed` serves `home.devices`, `home.switch` (`nyx home on kitchen`), `home.light`, `home.scene`, `home.climate`, `home.routines`, `home.run` (asks first) and `home.open` beside its own interfaces, through `devices.rs`' allowlist.
  - The `home` topic (rooms, devices with Overview's favorites, scenes, routines) is read every 3 s only while watched.
  - `Home.Devices1.Call` now takes only Nyx programs; Control Center's provider, a Nyx program, still can.
- **Files** (nyx-files `bdd365b6`, `39b206aa`):
  - `files.list`, `files.locations`, `files.search`, `files.open`, `files.reveal`, `files.copy`, `files.move` and `files.trash` (asks), inside the home folder.
  - Copy, move and Trash go through the window's `LocalOperationProvider`: Keep both only where a name is taken, and Trash rather than delete.
  - Headless, Files stays up 30 s after the last call.
  - Places fall back to their usual folders when `user-dirs.dirs` doesn't name them.
- **Glimpse** (`a620549`, `0d93977`, `e0915c9`):
  - **Music panel:** cover, track, progress, controls, volume, playlists filtered by the words after `music`, Open Music.
  - **Home panel:** scenes, favorites, rooms, toggles, dimming, thermostat ±, routines, Open Home, and an error state when Home Assistant isn't reachable.
  - **Files panel:** places, breadcrumbs, folders first, picture previews, open, copy and move with Ctrl+C/X/V, Trash with Delete, Open in Files. `files downloads` opens Downloads; other words search by name.
  - A panel gets its host before it completes. An app's name alone lists its verbs; aliases appear once a word is typed.
- **nyx-ai** `d325462`: on nyx-core `47c5e0f`. The Assistant's action list now includes Files, Home and Music from their manifests.
- **Checked on headless outputs**, with test copies on private buses and the apps under test IDs:
  - **Music:** D-Bus started it headless; it played a generated tone (silent sink), the volume went to 40, the panel updated live, and it quit 10 s after the panel closed.
  - **Home, real daemon:** its interface came up, the panel showed its error state without Home Assistant, and `dbus-send` was refused by `Devices1.Call`.
  - **Home, Python stand-in with sample data:** the full panel, `home kitchen` filtering, and a switch through the panel's path.
  - **Files:** the real build listed Downloads, copied with and without a clash, and moved, all in a scratch folder under `~/.cache` that was removed after.
  - Trash wasn't run end to end, to keep test files out of the real Trash.
- **Installed:** Music, Home (nyx-homed restarted), Files, Glimpse, AI Core and `nyx-actions`. Manifests are in `~/.local/share/nyx/actions` and D-Bus services for Music and Files in `~/.local/share/dbus-1/services`.

### Phase 6: Calendar, Reminders, Notes and Weather

- **Calendar** (nyx-calendar `1aed197`):
  - API 2 tools with risk, aliases and positionals (`nyx calendar today`, `nyx calendar find dentist`). `calendar.delete` asks first.
  - New `calendar.add` turns words that say when into an event, with nyx-when as the quick-add dialog uses it (`nyx calendar add lunch with Sam tomorrow at 1`). New `calendar.open` opens the app at a day.
  - The `upcoming` topic (the next 12 events), read every minute while watched and after a change.
  - Answers while Calendar is open (`activation: running`): its calendar list and the calendars shown belong to the window.
- **Reminders** (nyx-reminders `d910854`):
  - API 2 tools: `nyx reminders add call Sam tomorrow at 9`, `done`, `today`, `find`; delete asks. New `reminders.open`.
  - The `today` topic is sent again whenever the lists load, so a change shows once Evolution Data Server has it.
  - `NYX_REMINDERS_APP_ID` runs a test copy. Answers while Reminders is open.
- **Weather** (nyx-weather `67eed19`):
  - Tools renamed to `weather.current`, `forecast`, `query`, `locations`, `select_location`, `refresh` and `open`, with typed arguments. The old names still work.
  - `weather.current` adds five formatted days and icons. The `now` topic refreshes every 5 minutes while watched, from the forecast cache.
  - D-Bus starts Weather without a window (`--gapplication-service`, as Music), and it quits 10 s after the last call.
- **Notes** (nyx-notes `de8f38d`):
  - Its integration tools have risks and aliases (`nyx notes find garden`). Writes stay proposals that Notes shows for review, and its read and propose-edit permissions still decide.
  - No topic. Answers while Notes is open.
- **Installers** write each app's manifest (Weather also gets its D-Bus service). Uninstallers remove them.
- **Glimpse** (`9f91886`):
  - **Calendar panel:** upcoming events by day; the words after `calendar` become an Add bar (Enter); Open Calendar at the picked event's day.
  - **Reminders panel:** due today and overdue (overdue in red); Space or the checkbox marks one done; the words after `reminders` become an Add bar.
  - **Notes panel:** searches the vault as you type (250 ms pause); Enter opens a note; Ctrl+N or the button proposes a new note titled with the words. Notes' own messages show when it's closed or a permission is off.
  - **Weather panel:** the weather now, feels-like, high and low, wind, humidity, alerts and five days, in Weather's units; the words after `weather` ask a question (`weather tomorrow`).
  - Fix: switching from one app's panel straight to another's followed the first app's topics ("Weather has no topic upcoming"). Topic names now come from the offer itself.
  - Test copies can call a panel's own functions (`qs ipc … call glimpse mini add`).
- **Checked on a headless output**, with test copies under test IDs on a private bus that also started Evolution Data Server with scratch folders:
  - **Weather:** started by D-Bus headless; the panel showed now and five days; `weather tomorrow` answered.
  - **Calendar:** `calendar lunch with sam tomorrow at 1pm` added the event to the scratch Personal calendar; the panel and the Calendar window both showed it.
  - **Reminders:** `reminders call mum today at 6pm` added it; it showed under Today; marking it done removed it.
  - **Notes:** a scratch vault with permissions on. `notes garden` found two notes; one opened in Notes; `notes packing list` proposed a note, and Notes showed its review without creating the file. With Notes closed, the row said "Open Notes to use this".
- **Installed:** Calendar, Reminders, Weather, Notes and Glimpse, with manifests for all four. Ken's real calendars and reminders weren't touched.
- **Left for later:**
  - Calendar and Reminders headless: their data lives in the window.
  - A topic for Notes, such as recent notes.
  - Clipboard, Vault, Containers, Backup, Devices and AI Hub: they can adopt the same contract (`serve_with` plus a description and manifest) when their panels come.

### Phase 7: pinned panels, accessibility and performance

- **Nyx Shell** (nyx-shell `3acaec5`, `56505cf`):
  - **`PinOverlay {id, pinned, size, monitor?}`** pins a persistent overlay. It's shown until unpinned, and other overlays in its group showing leave it alone. Shell Core lays it out: down the right edge of its monitor's usable area, 12 px in and 10 px apart, in pin order, with a new column when one is full. Size is 160×100 to 800×900.
  - Refused when there's no room, for `all`, for other categories, or while locked.
  - Laid out again when the monitor's size or reserved area changes, when the monitor goes (it moves to the active one), when another pin goes, and when its owner disconnects.
  - The state's new `pin {size, at}` is what the surface follows. Hidden over fullscreen windows and while locked; on-demand keyboard, so it never takes focus by itself; no focus restoring.
  - The same rules in `Standalone.qml` for the laptop.
  - `PinnedSurface` (Nyx.Shell) draws one and pins it again after every registration, so a restarted Shell Core gets it back. `OverlaySurface` has a new `registered` signal.
  - Tests: layout and columns, refusals, group, lock, monitors changing and going, removal, and the operation end to end (65 Shell Core tests).
- **Glimpse** (`cfb619c`):
  - Ctrl+P on an app panel pins it, and again unpins it (also a key hint).
  - The pinned panel is the same panel QML and host, under a header with the app, Open and Unpin. It follows its topics only while shown, and shows Open <app> while the app can't answer.
  - The backend keeps pins in the settings (`pinned`, at most six, app IDs and monitor names validated) and publishes them on `pins`, refreshed every 15 s while any exist. `Pin` and `Unpin` accept only apps with one of Glimpse's panels.
  - A watch that ended (the app said no, or went away) starts again for a new viewer.
- **Accessibility:**
  - Nyx.Ui (nyx-design `7d52e29`): buttons, icon buttons (named by their tooltip), switches, sliders, list rows, segmented controls and search fields have roles, names, states, and press, toggle and step actions that do what their keys do.
  - Glimpse: the search, the results list and rows (category, title, subtitle, why one can't run), the ask bar as an alert, and the rows of the Calendar, Reminders, Notes, Home and Weather panels.
- **Performance:**
  - Pinned panels follow their topics only while visible, and the 15 s refresh does nothing when no panel is pinned. Pins are keyed by app, so a refresh never rebuilds a surface. The layout only moves surfaces whose box changed.
  - Measured on a headless output with test copies: a panel action through the backend takes about 5 ms (Weather from its cache); Pin and Unpin take 5 to 10 ms. The backend uses 41 MB; the Quickshell copy (debug runtime, Glimpse and two pins) 196 MB.
- **Checked on a headless output** (standalone mode, private bus, scratch settings):
  - Pinned Weather and Calendar stacked at (848, 38) and (848, 388) below the bar, and stayed after Glimpse closed and with it open.
  - They came back after Quickshell restarted.
  - Unpinning the top one moved the other up.
  - Closing Calendar turned its pin into Open Calendar within 15 s.
  - Found and fixed on the way: a switch case that broke standalone Show and Hide, surfaces rebuilt on every republish, and the unregister id lost on destruction.
- **Installed:** the Nyx.Shell runtime (nyx-shell `56505cf`, nyx-design `7d52e29`) and Glimpse. Glimpse's QML needs the new runtime (`PinnedSurface`), so NyxOS's nyx-shell package must update with it.
- **Left for later:**
  - Moving a pinned panel by hand, which would need a Shell Core move operation.
  - A pin edge or margin setting in `shell.toml`.
  - Fullscreen hiding seen live (unit-tested only, since making a window fullscreen in a test moves focus).
  - Orca on a session with the accessibility bus (it isn't running on the laptop).

### Follow-ups after Phase 7

- **Calendar and Reminders without their window** (nyx-calendar `dbbef8a`, nyx-reminders `9c40d9f`): activation `dbus`. The calendar list, reminder lists and reminders are kept whether or not a window shows, and calls wait for the first load. Reminders started this way sends no alerts. A reminder's source is written to the sidecar directly. Checked on a private bus with scratch Evolution Data Server data: a cold `calendar add`, `calendar next`, `reminders add`, and `list` after a fresh start.
- **Commands** (nyx-core `b2b7509`, Glimpse `b37b803`, Weather `cd0645b`):
  - Local paths complete `format: path` arguments.
  - Running apps' `x-nyx.suggest` actions complete theirs (`weather use Ca` → Calera; Music's outputs), within 300 ms; a key press never starts an app.
  - When no command matches, the CLI says how to ask Nyx Assistant (`nyx-assistant say '…'`), and Glimpse offers an "Ask Nyx Assistant" row that sends the words only when picked.
- **Music outputs** (nyx-music `fe7eb58`): `music.outputs` and `music.output`, through GStreamer's PipeWire devices. The choice is kept, applied to both engines, and switched mid-song where it was. Checked with a silent file, muted.
- **Files** (nyx-files `ad8cfb91`): the `changes` topic. The panel lists the shown folder again when it changes. Trash through the panel was checked end to end with a scratch home: it asks first, and the real Trash was untouched.
- **Pinned panels** (nyx-shell `d2bfcf1`, Glimpse `4de3881`):
  - Drag a pin by its header and it stays there; double-click puts it back in the stack.
  - `[pins]` in `shell.toml` sets edge, margin and gap; standalone reads it too.
  - Glimpse keeps the position with the pin.
- **More apps:**
  - **Containers** (`b67d5c8`, Glimpse `bcc5473`): list, start, stop, restart, open, the `workloads` topic and its panel.
  - **Clipboard** (`5beb9ca`): status, private mode on, clear (only the `nyx` command and Glimpse's backend, a new Command scope, and confirmed), open. Nothing from the history.
  - **Passwords** (`c382c93`): status, lock, open. Never a secret; the daemon keeps its private socket.
  - **Backup** keeps its grant-based Control as it is.
  - **Devices** (nyx-connect) isn't checked out here.
  - nyx-actions `53895a9` adds `x-nyx.sensitive` for private reads; nothing uses it yet.
- **NyxOS packaging** (nyx-packages branch `glimpse-2`, `0c571aa`, unbuilt):
  - action manifests and D-Bus services from `--describe-actions` (`lib.installActions`);
  - the `nyx-actions` package;
  - `share/nyx` linked for every app;
  - Glimpse's Quickshell panel as a Nyx Shell component, with its backend started with the session.
  - After pushing: update the inputs, run `scripts/git-hashes`, build.
- **Devices** (nyx-settings `3e3e66e`, Glimpse `349032c`, nyx-core `cba03d3`, `ebd5869`):
  - Nyx Settings hosts the phones paired through Flux: `devices.list`, `ring`, `send` (the clipboard; asks first) and `open`.
  - The `devices` topic feeds Glimpse's Devices panel. D-Bus starts Settings without a window.
  - Settings' own tools stay read-only.
  - Settings moved to nyx-core `47c5e0f`, which also fixes its control interface: the `3691c99` pin had the dropped-Service bug.
  - In nyx-actions, an app's default action takes free words only in its own namespace, completion lists the typed namespace's verbs, and usage names each action's namespace.
  - Glimpse shows a multi-namespace app's panel for the word that names it.
  - Checked against the real fluxd, read only: the phone listed, and sending asked first. Ringing wasn't run.
  - nyx-packages `glimpse-2` `fb71942` adds Settings' manifest.
