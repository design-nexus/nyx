# Handoff 05: Nyx Chat, Glimpse 2.0 and Assistant 2.0

Status: audit done 2026-11-08; the migration follows it stage by stage (Chat, Glimpse,
Nyx Voice, Assistant, Aura). The handoff text is "5. Nyx Chat, Glimpse 2.0 & Assistant
2.0" in the NyxOS handoff set.

Decisions taken with Ken on 2026-11-08:

- Chat first, then Glimpse, then Nyx Voice and the Assistant.
- Glimpse and the Aura get Quickshell front-ends on Nyx Shell Core. The GTK ones stay as
  the fallback where Shell Core isn't running (the laptop, Omarchy).
- Nyx Voice dictation replaces VoxType on NyxOS only. Omarchy's F9 dictation (VoxType)
  stays on the laptop.
- Chat keeps Ollama as an optional provider of its own. Only llama.cpp on this computer
  has to go through AI Core.
- Glimpse keeps Super+Space. The handoff's "Ctrl+Space, unless changed" was changed
  before it was written: Ctrl+Space opens Omarchy's menu.
- Nyx Voice is its own repository (`nyx-voice`), laid out like `nyx-ai`: a protocol
  crate, a client crate and the `nyx-voiced` daemon.

## 1. What each part has today

### Shared Nyx AI Core (`nyx-ai`, HEAD `da5b6f6`)

Ready for all three apps. `nyx-ai-client` over `$XDG_RUNTIME_DIR/nyx-ai/ai.sock` (JSON
lines, API 1): streaming chat with cancel (`Stream::cancel`, the `cancel` operation, or
closing the connection), tool calls, GBNF grammars, JSON output, vision and audio
parts, `embed_inputs` for text, images and audio with the model's `identity` in every
reply, the model registry (list, info, load with keep, unload, remove, settings,
downloads, updates), role defaults (`chat`, `assistant`, `embedding`, `coding`),
battery saver, priorities (`interactive`, `normal`, `background`) with ageing and
fairness, leases, LRU eviction within `max_loaded` and the memory budget, and a
supervised `llama-server` router.

Shared actions: `list_actions`, `invoke_action(action, args, confirmed)`,
`serve_actions`. Sources are running apps' `io.github.design_nexus.nyx.Control` D-Bus
interface and trusted programs serving over the socket. Untrusted callers get read-only
actions; `ask` actions need `confirmed`; arguments are checked against the schema; the
owning app has the last word. `permissions` is metadata the caller's policy reads.

No speech: capture, recognition and synthesis belong to Nyx Voice (`docs/ASSISTANT.md`).

### Nyx Shell Core (`nyx-shell`)

Overlay policy (`passive`, `transient`, `persistent`, `presentation`,
`secure-external`), focus restoration, shortcuts written to `nyx-shell.lua`, component
registry, `shell.glimpse.toggle`. QML: `Nyx.Shell` (`ShellCore`, `OverlaySurface`,
`ShellComponent`, `Theme`, `Motion`, `KeyboardScope`) and, in progress in another
session, `BackendClient` (a component's Rust backend over nyx-core's `nyx-ui-link`) and
`Standalone` (the same rules without Shell Core). Off by default on NyxOS
(`nyx.shell.enable`); `nyx-shell-qs` runs nothing yet.

### Nyx Chat (`nyx-chat`, `13d73f7`)

| Area | Today |
| --- | --- |
| Inference | `nyx-ai-client` (pinned `d0f202b`) when the host is exactly `127.0.0.1:8080`; raw OpenAI-style HTTP for other llama.cpp hosts; Ollama |
| Runner | None left. `ca522f7` removed `nyx-llama-server.service`, the launcher and downloads; `install.sh` retires the old unit |
| Model settings | Chat pushes its own defaults to every model (`presets::sync`) at each start and keeps a copy in `prefs.model_settings` |
| Service settings | Chat keeps `llama_models_max` and `llama_idle_seconds` and unloads models itself |
| Model choice | Chat's `new_chat_model`, then `last_model`, then AI Core's `chat` default; falls back silently to the first installed model |
| History | SQLite `~/.local/share/nyx-chat/chat.db`; attachments `~/.local/share/nyx-chat/attachments/` |
| Personas | System prompt per chat, per folder and global; `/` prompt snippets |
| Attachments | Images (vision models only), text and PDF inlined or retrieved by embeddings |
| Integrations | MCP servers, web search (Brave, Tavily, SearXNG, DuckDuckGo), voice, Hugging Face browsing |
| External providers | None besides Ollama and remote llama.cpp |

### Nyx Glimpse (`nyx-glimpse`, `55ff757`)

| Area | Today |
| --- | --- |
| Processes | `nyx-glimpse` (GTK4 layer shell), `nyx-glimpsed` (indexer), `nyx-glimpse-settings`, `glimpse-embed` (worker) |
| Direct search | Apps, files, plugin content (FTS), power actions, utilities, Omarchy menu, services, plugins, `pw` and `cb` |
| Semantic search | EmbeddingGemma 2 Q8_0 and projector in its own llama.cpp build (`inference/`, `scripts/setup-runtime.sh`, tag `b11461`), models downloaded by Glimpse with SHA-256 checks |
| Identity | Fixed `glimpse-embeddinggemma2-q8-v1`; a different stored identity wipes the index |
| Without AI | Direct results work; keyword search over built-in formats (PDF, docx, txt) is lost because it lives in `Session::search` |
| Actions | Its own `Effect`/`Target`; "press Enter again" for system actions; scope rechecked at dispatch |
| Presentation | GTK layer-shell overlay, exclusive keyboard, the compositor picks the monitor, no focus restoration |
| Activation | Super+Space, written by Glimpse into `hyprland.lua` (NyxOS: `hyprland.nix`) |
| Freshness | Generation counter, 10 ms and 180 ms coalescing, cancel closures, timeouts per provider |

### Nyx Assistant (`nyx-assistant`, `48100ac`)

| Area | Today |
| --- | --- |
| Inference | `assistant-inference`: llama.cpp in the daemon (`llama-cpp-2`, CUDA), GBNF planner grammar, prompt cache, vision projector loaded on first look, battery mode |
| Model API for Notes | `model_generate` from the resident model, `model_embed` forwarded to a loopback endpoint |
| Speech recognition | Nemotron 0.6B streaming (sherpa-onnx, `nyx-assistant-asr`); VoxType Parakeet fallback |
| Speech synthesis | Kokoro 82M (loqui, CPU); optional Chatterbox worker |
| Voice detection | Silero v5, energy fallback; wake by name in the transcript |
| Audio | Native PipeWire capture and playback, `module-echo-cancel` through `pactl`, ducking |
| Sessions | Wake, follow-up, conversation, dictation, paused; rule-based barge-in |
| Actions | Own registry with JSON Schema, capabilities, single-use grants, task scope, audit journal; Nyx apps through `busctl` (`abilities/nyx-apps`); secrets confirmed through Nyx Biometrics |
| Personas | `~/.config/nyx-assistant/personas/*.toml`; voices `voices/*.toml` |
| Aura | GTK4 layer shell (`assistant-visual`): Full and Edge Flow, persistent and activity visibility, reduced motion; states idle, listening, thinking, speaking, attention, done, error |
| HUD | Quickshell approval card and context toast (`quickshell/shell.qml`) |
| Canvas | `canvas.show` tool rendered by `assistant-visual` |

## 2. VoxType inventory

| Feature | Who uses it | Where |
| --- | --- | --- |
| Push-to-talk dictation (F9 hold, Right Alt hold) and toggle (Super+Ctrl+X) | Omarchy, the laptop | `/usr/share/omarchy/default/hypr/bindings/dictation.lua`, `omarchy-dictation` → `omarchy-dictation-voxtype` |
| Whisper `base.en`, English, local | Omarchy dictation | `~/.config/voxtype/config.toml` |
| Typed output with a clipboard fallback, 1 ms per key | Omarchy dictation | same |
| Pause media while recording, 60 s cap | Omarchy dictation | same |
| User service `voxtype.service` | Omarchy dictation | `voxtype setup systemd` |
| Parakeet TDT 0.6B v3, warm daemon or cold `transcribe` | Assistant fallback recognizer | `assistant-agent/src/stt.rs`, `nyx-assistant-stt.service`, `config/voxtype-parakeet.toml` |
| `voxtype.override { onnxSupport = true; }` | NyxOS package | `nyx-packages/pkgs/nyx-assistant.nix` |
| Dictation section | Nyx Settings | `sections/capture.rs` (hidden: it looks for an install script Omarchy renamed) |

Omarchy chooses the dictation program with `omarchy-default-dictation` and runs
`omarchy-dictation-<backend>`, so Nyx Voice can be offered there as one more backend
later without replacing VoxType.

## 3. Migration matrix

| Part | Reuse | Change | Must keep working |
| --- | --- | --- | --- |
| Chat inference | `llama/core.rs` and the client | Bump the pin; every local llama.cpp host through AI Core; clear error messages | Streaming, cancel, tools, thinking, stats |
| Chat models | AI Core's registry | Stop overwriting AI Core settings; no own eviction; no silent swaps | Model picker, marketplace, downloads |
| Chat data | All of it | Nothing | History, folders, prompts, attachments, knowledge bases, MCP |
| Glimpse embeddings | Index, readers, ranking | `embed_inputs` instead of `glimpse-embed`; AI Core's identity; staged reindex | Existing indexes stay valid |
| Glimpse search | Providers, matcher, generations | Keyword content search without AI; backend usable without GTK | Direct search and launching with AI Core down |
| Glimpse actions | Scope checks, confirmation | Shared registry: list, invoke, serve | Plugin actions, power, Omarchy menu, `pw`, `cb` |
| Glimpse UI | GTK UI as the fallback | QML overlay on Shell Core | Keyboard navigation, Super+Space |
| Assistant inference | Planner grammar, prompts, tools | `nyx-ai-client` chat; vision as image parts | Planner, tool calls, battery mode, cancel |
| Assistant speech | sherpa-onnx worker, Kokoro, Silero, PipeWire | Moves to `nyx-voiced` | Wake, follow-up, conversation, barge-in |
| Assistant actions | Registry, policy, grants, journal | AI Core's registry for Nyx apps | Approvals by voice, HUD, TUI, CLI; secrets broker |
| Aura | Styles, settings, theme | QML on Shell Core; real states | Full, Edge Flow, visibility, reduced motion, Canvas |

## 4. Baselines

Recorded before the migration; nothing new was measured for this audit.

- Chat through AI Core: `nyx-ai/docs/BENCHMARKS.md` (RTX 5080 Laptop, 8 November): first
  token 165 to 201 ms on a new prompt, 86 to 158 tokens per second, cold loads 2.8 to
  9.3 s, embeddings 305 short texts per second.
- Glimpse direct search: `nyx-glimpse/docs/PERFORMANCE.md` (catalogue queries, first
  results 63.64 ms and 34.62 ms after a text change).
- Assistant: `nyx-assistant/apps/assistant/docs/BENCHMARKS.md` (788 ms first audio on a
  short turn; 980 ms median text turn; warm Parakeet 175 to 260 ms).

## 5. Data and configuration that must not move

| App | Data | Configuration |
| --- | --- | --- |
| Chat | `~/.local/share/nyx-chat/` | `~/.config/nyx-chat/settings.toml` |
| Glimpse | `~/.local/share/nyx-glimpse/` (index, models, usage) | `~/.config/nyx-glimpse/` |
| Assistant | `~/.local/share/nyx-assistant/` (models, journal) | `~/.config/nyx-assistant/` (config, personas, voices) |
| AI Core | `~/.local/share/nyx-ai/`, Hugging Face cache | `~/.config/nyx-ai/` |

## 6. Progress

Each stage updates this section with what landed and the commits.

### Stage B: Chat (nyx-chat `e4c2086`)

Chat runs every local llama.cpp model in Nyx AI Core (nyx-ai `da5b6f6`) and no longer
manages AI Core on its own:

- Model settings: read from AI Core when Chat starts and when a model's settings open;
  only the keys the person edits are sent, as changes from what a load uses now. Chat
  no longer pushes its defaults to `*` or re-sends every model's settings each launch.
- Service settings (models kept loaded, idle unload) are shown as AI Core has them and
  written straight to it; Chat's own copies are gone. Chat never unloads a model to
  make room: picking another model only drops Chat's pin (AI Core keeps the model while
  another app needs it, and decides what to evict).
- Any loopback address (`localhost`, `127.0.0.0/8`, `::1`, any port) for a llama.cpp host
  is AI Core, so nothing on this computer bypasses it. Ollama stays a separate provider.
- No silent swaps: a chosen model that isn't installed stays chosen, with the banner
  that offers the download; a knowledge base's or long attachment's embedding model and
  Quick ask's model say which model stands in for the missing one.
- Errors name what happened (version mismatch, unknown model, load failure, runner
  restarting, busy or out of memory, permission, unsupported capability, timeout).
  Stop sends AI Core's `cancel`, then closes the stream.
- Marketplace fit uses the GPU memory AI Core reports; `nvidia-smi` isn't asked.

| Must keep working | Status | How it was checked |
| --- | --- | --- |
| History, folders, branches | Unchanged code and storage | Build; store tests |
| Personas (system prompts per chat, folder, global; `/` prompts) | Unchanged | Build |
| Attachments, vision images | Unchanged; images go as `image_url` parts | `tool_results_answer_their_calls` |
| Streaming, tool calls, thinking, stats | Unchanged path, now testable against a socket | `streams_stops_and_reports_through_ai_core` |
| Cancel | Explicit `cancel`, then close | Same test (the fake sees the cancel) |
| Model choice and AI Core's default | Default role still used when Chat has no pick | Build |
| Model settings | Read from AI Core; edits only | `edits_send_only_what_changed` |
| Integrations: MCP, web search, voice, Control (Assistant) | Unchanged | Build |
| Ollama and remote llama.cpp | Unchanged; remote only for llama.cpp | `every_local_address_is_ai_core` |
| Hugging Face token | Chat's file, which AI Core already reads | Unchanged |

Installed to `~/.local/bin/nyx-chat`.

### Stage C: Glimpse backend (nyx-glimpse `873eaa7`, nyx-ai `9633690`)

- Embeddings come from AI Core (`embed_inputs`, background priority while indexing,
  interactive for queries, batches of 16). Glimpse names EmbeddingGemma 2 Q8_0 itself,
  its own folder copy first. The `inference/` crate, `setup-runtime.sh`, the downloader
  and the device logic are gone; nothing of Glimpse runs llama.cpp.
- AI Core gained `configure_service`'s `add_model_dirs` (trusted programs), so Glimpse
  offers `~/.local/share/nyx-glimpse/Models` the first time it needs the model and sets
  its load settings (`pooling=mean`, 2048 batches, 140 to 280 image tokens). The 865 MB
  of models already there are used as they are.
- The index stores AI Core's identity for its vectors. An index from Glimpse's own
  runtime (`glimpse-embeddinggemma2-q8-v1`) is taken over without a rebuild when AI Core
  reports the documented equivalent. Any other change builds `glimpse.next.sqlite`
  beside the live index (searches flag it even when no file changed); the live index
  keeps answering word matches until the new one has every file and replaces it.
- Without AI Core, apps, file names, utilities and word matches in contents keep
  working; the status line says why meaning matches paused. The indexer waits instead
  of marking files failed.
- Shared actions: AI Core's registry is a Glimpse provider (actions without required
  arguments; "ask" actions run on a second Enter). The indexer offers `glimpse.search`
  (read-only, never asks) while `nyx-aid.service` runs; it doesn't start AI Core.
- `nyx-glimpse-backend` serves search and activation without GTK over nyx-ui-link
  (`$XDG_RUNTIME_DIR/nyx-glimpse/ui.sock`) for the Quickshell interface. The GTK panel
  keeps its own threads over the same providers; moving it onto the backend module is
  left for later, since it would touch 3,500 lines of working UI for no visible change.
- Tests: fake AI Core sockets for embedding and identity, the legacy mapping, the staged
  rebuild with word matches while it runs, the AI-free fallback, the served action, the
  action provider, the backend's fast results. `tests/core.rs` was already broken in the
  standalone repository (it includes a file from the old monorepo); not changed here.

Installed; `nyx-glimpsed` restarted on the new build. Its first index pass or search
that needs embeddings registers the folder with AI Core.

### Stage D: Glimpse presentation (nyx-glimpse `54d122f`)

- `quickshell/Glimpse/Main.qml`: a component for `nyx-shell-qs` on `Nyx.Shell`
  (`OverlaySurface`: transient, keyboard exclusive, active screen, focus restored,
  group `launcher`, shown over fullscreen windows) and `Nyx.Ui` (search field, list
  rows, badges, theme, reduced motion). It draws what `nyx-glimpse-backend` publishes and
  drops replies for any query but the current one.
- `nyx-glimpse --toggle`/`--hide` go to the backend while a Quickshell interface is
  connected, else to the GTK panel, so Shell Core's `shell.glimpse.toggle` route and the
  Super+Space bind keep working unchanged. The laptop has no backend: GTK as before.
- `data/nyx-glimpse-backend.service` for NyxOS.
- Checked on a headless output (standalone `Nyx.Shell`, keyboard off, scratch folders):
  file results with the selected row, a calculation answer.
- Depends on two pieces still uncommitted in other sessions' trees: `Nyx.Ui`
  (nyx-design `qml/Nyx/Ui`) and `BackendClient` (nyx-shell), the same ones the Control
  Center's QML uses. The QML panel lacks previews, the action panel, `pw` and `cb`; the
  GTK panel keeps them.

### Stage E: Nyx Voice (new repository design-nexus/nyx-voice `4a3b211`)

Ken approved the new public repository and chose to have the Assistant link the engine
(2026-11-08).

- `nyx-voice-engine`: the Assistant's speech code, moved, not rewritten: PipeWire
  capture and playback, echo cancelling, ducking, Silero and energy voice activity, the
  streaming recognizer client, Kokoro and Chatterbox. Its config types are the
  Assistant's `[audio]`, `[vad]`, `[stt]`, `[tts]`, `[barge_in]` sections, so existing
  files read the same. Each program names itself (`paths::set_app`); the Assistant keeps
  its folders and PipeWire names, and models one program downloaded are found by the
  other (nothing downloads twice).
- `nyx-voice-asr`: the sherpa-onnx worker, depending only on the protocol crate so its
  ONNX Runtime stays apart.
- `nyx-voiced`: one take at a time (`busy` otherwise), dictation captured, transcribed and
  typed with `wtype` (clipboard fallback, media paused with `playerctl` when present, 60 s
  cap), listening for apps in dictation or assistant mode with partial words, speaking,
  devices, state (`watch`, and VoxType's state file values). Listening and typing need a
  trusted program (`nyx-peer`, the same rule as AI Core); raw audio never touches disk,
  transcripts are never logged. Socket-started; engines unload after five idle minutes.
- `nyx-voice` command, `docs/PROTOCOL.md`, `docs/ARCHITECTURE.md`, and the VoxType parity
  table in `docs/VOXTYPE.md`.
- Tests: protocol lines, config (reading the Assistant's file), the trust check and
  request validation over a real socket, engine units. No audio in tests.

Installed on the laptop without enabling its socket (Omarchy keeps VoxType for F9).

### Stage F: Assistant (nyx-assistant `5db2f27`)

- Inference: `assistant-inference` is now an AI Core client with the old runner's
  methods (generate, grammar, look, unload, battery, status), so the planner, prompts and
  sessions are unchanged. Turns are interactive priority with thinking off; grammars go
  as `grammar`; images as image parts (vision only with a model that has it). `[llm]
  model` names a GGUF file (its folder is offered to AI Core, read-only) or `auto` for AI
  Core's `assistant` default. On battery, replies are capped at 256 tokens; AI Core's
  battery saver decides where models run. `keep()` pins the model for a conversation.
  `llama-cpp-2`, its CUDA build and the in-process worker are gone.
- Speech: `assistant-audio` and the agent's recognizer and Kokoro are re-exports of Nyx
  Voice's engine; the Assistant names itself to it, so its folders, caches and PipeWire
  names (`Assistant`, `assistant-echo-cancel`) are as before. VoxType is gone: the
  provider, `stt-daemon`, `nyx-assistant-stt.service`, `voxtype-parakeet.toml`; the
  installer disables and removes them on update. The recognizer test moved to nyx-voice.
- Actions: the `nyx-apps` ability (1.5.0) calls running apps through AI Core's shared
  registry (`nyx-ai act`, after the Assistant's own approval) and falls back to the
  control interface directly only when AI Core isn't running or hasn't seen the app.
  Its schemas, voice routes and starting apps that aren't running stay in the ability.
  Grants, capabilities, the audit journal and the secrets broker are unchanged.
- Not done: offering the Assistant's own tools through `serve_actions`, and a generic
  tool for shared actions the ability doesn't list (each would need a capability class
  in the Assistant's policy). Notes still reaches the model through the Assistant's model
  API, which now uses AI Core; moving Notes to `nyx-ai-client` belongs to nyx-notes.
- Checked: workspace build, unit tests (core, policy, inference, audio, agent). Installed
  (backup in `~/.local/state/nyx-assistant/backups/20261108-225918`). The daemon wasn't
  running; a test start showed echo cancelling, the recognizer ready in 3 s, Kokoro on
  the CPU and Silero from the existing cache, and it was stopped again. No language
  model turn was run.

### Stage G: Aura (nyx-assistant `12aefba`)

- Real states added to the daemon: `activating` while a turn waits for AI Core to
  queue or load the model (from AI Core's `queued`/`model_loading` events), and
  `unavailable` when a turn fails because AI Core can't be reached (instead of `error`).
  `transcribing` and `executing` already existed. Approvals show as attention.
- `quickshell/Aura/Main.qml`: Full Aura (soft light up both sides, wider with the voice)
  and Edge Flow (a segment with a soft glow travelling round the edge, slower while
  thinking); persistent (faint at idle) or activity (only while busy, fading out after);
  reduced motion (`[ui] aura_reduce_motion` or the theme's); `Nyx.Theme` colours; a Shell
  Core `presentation` overlay per screen in `[ui] aura_monitor_mode`, no input, inside
  the bars' reserved space, hidden while locked or over fullscreen windows. It reads
  `nyx-assistant listen`, so nothing in it can hold up listening, speech or the model.
- `[ui] aura_renderer`: `gtk` (default; `nyx-assistant-visual` as before) or `quickshell`.
  Canvas stays in `nyx-assistant-visual`.
- Checked on a headless output: Full Aura while listening, Edge Flow while speaking and
  thinking. Installed (the daemon and the GTK Aura were off and stay off).

### Stages H and I: validation, NyxOS and rollback

- Cross-app test (nyx-ai `8adb415`, against the stand-in worker): Chat and the
  Assistant chatting at once on one model while Glimpse indexes in the background on
  another; both replies finish whole, indexing runs after them (one model loaded at a
  time), and one app's connection can't cancel another's request. AI Core's existing
  tests cover worker crashes and recovery, eviction, cancel and settings.
- Nyx Settings (`efa3eee`): the Assistant's hearing is Nyx Voice's recognizer (no
  VoxType choice); on NyxOS, Dictation is Nyx Voice's (output, pausing media, longest
  take); on Omarchy the VoxType section finds Omarchy 4.5's renamed install script.
  Installed.
- nyx-packages, branch `handoff-05` (`9620621`, worktree `~/Projects/nyx-packages-h05`,
  so the uncommitted lock update in `~/Projects/nyx-packages` is left alone): the
  `nyx-voice` package and `nyx.voice` (on with the Assistant; socket-started); Glimpse
  without llama.cpp, with its backend and Quickshell component (backend started with
  the session under `nyx.shell`); the Assistant without VoxType, the recognizer worker
  and llama.cpp, with its Aura as a shell component. Inputs moved to nyx-chat `e4c2086`,
  nyx-glimpse `916bbfe`, nyx-assistant `12aefba`, nyx-ai `8adb415` and nyx-voice
  `1ebd749`, git hashes regenerated, in a separate folder of the dev VM (`364e0e3`).
  `nix flake check --no-build` passes, the Nix files are formatted, and the whole
  incus-dev system evaluates with both branches; its Hyprland config is valid Lua with
  the dictation keys. Nothing was built or switched (Ken's choice, 2026-11-08).
- nyxos, branch `handoff-05` (`5bd37f5`): Nyx Voice on by default, F9 and Right Alt held
  and Super+Ctrl+X for dictation. It needs the nyx-packages branch first.

#### Rollback

On the laptop, every app reinstalls from an earlier commit with its own `install.sh`
(`git checkout <commit> && ./install.sh …`), and nothing migrated data in a way an older
build can't read:

| App | Back to before Handoff 05 | Notes |
| --- | --- | --- |
| Chat | nyx-chat `13d73f7` | AI Core's settings were never rewritten by the new build; Chat's old copies are in `settings.toml` until it saves again |
| Glimpse | nyx-glimpse `55ff757` | The old runtime is still in `~/.local/share/nyx-glimpse/runtime`; an index AI Core rebuilt has AI Core's identity and the old build wipes and re-indexes it (`glimpse.next.sqlite` can be deleted) |
| AI Core | nyx-ai `da5b6f6` | Glimpse's folder in `model_dirs` stays listed; remove it from `~/.config/nyx-ai/settings.toml` to forget it |
| Assistant | nyx-assistant `48100ac`, or restore `~/.local/state/nyx-assistant/backups/20261108-225918` | The old build needs `nyx-assistant-stt.service` and `voxtype-parakeet.toml` back (both in that backup) |
| Nyx Voice | `systemctl --user disable --now nyx-voiced.socket`; remove `~/.local/bin/nyx-voice*` | Models it found are the Assistant's own and stay |
| Settings | nyx-settings `4073954` | |

On NyxOS, the previous generation (`nixos-rebuild --rollback`, or the boot menu) undoes
the packaging; user data is the same as on the laptop.

#### Left to do

- Merge nyx-packages `handoff-05`, then nyxos `handoff-05` (its `flake.lock` moved to that
  nyx-packages revision), build, rebuild the VM and check Glimpse's QML panel, Nyx Voice
  dictation and the Assistant there.
- `Nyx.Ui` (nyx-design) and `BackendClient` (nyx-shell) are another session's uncommitted
  work; Glimpse's QML panel and the Control Center's need them committed and packaged.
- Benchmarks after the migration (Glimpse's semantic query and indexing through AI Core;
  the Assistant's spoken turn end to end) weren't run: they need real inference on the
  GPU (Ken, 2026-11-08). Baselines are in section 4.
- The Assistant offering its own tools through `serve_actions`, and a generic tool for
  shared actions the `nyx-apps` ability doesn't list.
- Notes calling AI Core directly (nyx-notes) instead of the Assistant's model API.
- Glimpse's GTK panel on the backend module (it runs the same providers itself today).
