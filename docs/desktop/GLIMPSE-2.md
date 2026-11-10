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
