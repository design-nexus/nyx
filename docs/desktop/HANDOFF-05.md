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
