# ⚡ EasyDash Unified - Open WebUI Alternative & Homelab Command Center

**EasyDash** is an ultra-lightweight, zero-dependency, self-hosted **Open WebUI alternative** and homelab command center. It unifies **Proxmox VE clusters**, **self-hosted services**, **local LLM engines (LM Studio & Ollama)**, **Model Context Protocol (MCP) & Bionic agentic reasoning suite**, **Google Antigravity (`agy`) CLI**, and **Home Assistant** into a single, responsive, client-side dashboard with **zero external libraries, zero build steps, and zero-auth**.

---

## ⚙️ Provider Settings & Hub Defaults (Advanced Development Architecture)

The EasyDash **Hub Drawer** (`⚙️ Hub`) features a modular 7-tab development control center that provides comprehensive, developer-grade configuration for every AI engine and system preference:

### 1. 🎛️ LM Studio Local Server (:1234)
- **Connectivity & Diagnostic Tools**:
  - **Base URL Endpoint**: Configurable local or LAN address (default `http://localhost:1234/v1`).
  - **⚡ Server Ping & Latency**: Real-time round-trip latency probe (`/api/lmstudio/ping`) with status indicator and loaded model counts.
  - **🔍 1-Click Model Scanner**: Queries `/v1/models` without CORS restrictions via standard library proxy to detect loaded models and auto-populate model pickers.
- **Precision Decoding & Samplers**:
  - **Temperature**: `0.00` – `2.00` precision slider with live readout.
  - **Top P (Nucleus)**: `0.00` – `1.00` slider.
  - **Top K**: `1` – `100` numeric input (default `40`).
  - **Min P**: `0.00` – `1.00` modern tail-cutoff slider (default `0.05`).
  - **Repetition Penalty**: `1.00` – `2.00` slider.
  - **Frequency & Presence Penalties**: `-2.00` – `2.00` sliders for fine-tuned output diversity.
  - **Deterministic Seed**: Custom numeric seed (`-1` for random, or integer for 100% reproducible generations).
- **Context & Token Limits**:
  - **Context Window Length (`num_ctx`)**: Choose from `2048`, `4096`, `8192`, `16384`, `32768`, `65536`, up to `131072` tokens.
  - **Max Generation Tokens**: Numeric cap (`-1` for unlimited).
  - **Custom Stop Sequences**: Comma-delimited stop tokens (e.g. `<|im_end|>`, `\nUser:`).
- **Runtime, Format & Security**:
  - **Chat Templates**: Native Auto-detect, `ChatML`, `Llama 3`, `DeepSeek R1/V3`, `Mistral`, `Gemma`, or `Raw Completion`.
  - **Context Overflow Policy**: Rolling Truncate (drop oldest context), Stop with Warning, or Strict Error.
  - **Structured JSON Schema Mode**: Toggle `response_format: { type: "json_object" }` for guaranteed JSON outputs.
  - **GPU Offload Layers (`n_gpu_layers`)**: Offload control (`-1` for all layers, `0` for CPU only).
  - **JIT Model Keep-Alive**: `5m`, `15m`, `1h`, or indefinite (`-1` keep in VRAM).
  - **Console Payload Logging**: Inspect full JSON request/response bodies in browser DevTools.

### 2. 🔌 Model Context Protocol (MCP) & Bionic Reasoning Suite
- **🔌 Model Context Protocol (MCP) Architecture**:
  - Full integration of MCP tools and multi-step agentic execution for local models.
  - **Built-in Homelab MCP Tools**:
    - `homelab_rag`: Semantic vector and lexical search across local documentation, workspace files, and chat memory. Configurable chunk size (512), overlap (64), top-k (4), min-score threshold (0.60), and local Ollama/LM Studio embedding endpoint. Includes interactive in-drawer "Test RAG Search" query runner.
    - `web_search`: DuckDuckGo zero-key web grounding with real-time citations.
    - `fetch_webpage`: URL readability article extractor.
    - `run_powershell`: Host PowerShell bridge execution with configurable confirmation safety prompt.
    - `read_file` & `list_directory`: Direct workspace and homelab filesystem inspection.
  - **Custom External MCP Servers**:
    - Register external MCP servers over `stdio` (local CLI commands) or `sse` (HTTP Server-Sent Events).
    - 1-click server connection ping test, enable/disable toggle, and removal.
  - **Execution Policy Controls**:
    - `Auto-execute read-only tools`: Automatically runs read tools (RAG, Web, File Read) without interrupting the model.
    - `Require confirmation for host execution`: Prompts user before executing PowerShell host commands.
    - `Max Agentic Turns`: Caps agentic multi-turn loops (1-10 steps, default 5).
- **🧬 Bionic Agentic Runtime & Reasoning Lines (`/thinking`, `	hinking`, `<think>`)**:
  - Full compatibility with LM Studio's Bionic agentic ecosystem, DeepSeek-R1, QwQ, Qwen-2.5-Coder, and reasoning models.
  - **Real-Time Thinking Disclosure**:
    - Collapsible `<details class="thinking-block">` card with distinct accent border and subtle background.
    - Animated pulsing icon (`💭 Thinking...`), real-time duration timer, and token counter during streaming.
    - Supports `/thinking ... /thinking`, `	hinking ... 	hinking`, and `<think> ... </think>` as well as OpenAI `reasoning_content` deltas.
  - **Configurable Thinking Modes**:
    - `Auto` (default): Expands during generation to show live thoughts, automatically collapses when thinking completes so the final answer is front-and-center.
    - `Always Expanded`: Keeps reasoning expanded for deep audits.
    - `Always Collapsed`: Keeps reasoning collapsed as an on-demand expandable block.
    - `Hidden`: Completely hides reasoning blocks.
  - **Instant 1-Click Header Toggle**: Fast-toggle button (`💭 Thinking: Auto`) to cycle modes instantly.
  - **Interactive Test Thought Button**: 1-click button in settings to preview and test the thinking block UI.
  - **Multi-Step Agentic Loop**: Parses tool requests from models, executes MCP tools, renders tool cards in chat, and feeds observations back to the model.

### 3. ⚡ Google Antigravity (`agy`) CLI Subsystem
- **Agent Reasoning & Intelligence**:
  - **Reasoning Effort (`--effort`)**: `Default (Auto)`, `low` (Fast), `medium` (Balanced), `high` (Deep reasoning & verification).
  - **Agent Operational Mode (`--mode`)**: `Autonomous (Full Tool Use)`, `plan` (Architectural Roadmap Only), `accept-edits` (Direct File Modifications).
  - **Autonomy Turn Budget (`--max-steps`)**: Limit autonomous iterations to `5`, `10`, `25`, `50` turns, or `Unlimited`.
- **Workspace & Privileges**:
  - **Custom Working Directory (`-C` & CWD)**: Target project workspace directory for Antigravity code tasks.
  - **Tool Group Privileges**: Granular checkboxes for Terminal Execution (`!cmd`), File Operations, Web Search, and Subagent Orchestration (`/teamwork-preview`).
  - **Conversation Compaction**: Automatic context compaction threshold (`/compress`) or turn-based auto-compression.
  - **Turn Continuation**: Seamless turn continuity (`-c` / `/continue`).

### 4. 🦙 Ollama Local / LAN Server (:11434)
- **Endpoint Configuration**: Connect to local or LAN instances.
- **Full Hyperparameter Suite**: `num_ctx` (2k to 64k), `keep_alive` timeout, temperature, top_p, top_k, repeat penalty, repeat last N, and Mirostat mode (1.0 or 2.0).
- **Hardware Acceleration**: `num_gpu` offload layer control.
- **Raw Prompt Mode**: Pass prompts directly to the model without standard template wrapping.
- **Integrated Model Manager**: 1-click modal to pull models with SSE download progress, inspect parameters/modelfiles, and delete models.

### 5. 🤖 OpenAI & Remote Compatible API
- **Endpoint URL**: `https://api.openai.com/v1` or any remote v1-compatible endpoint (OpenRouter, Groq, DeepSeek, LocalAI).
- **API Key & Org ID**: Secure bearer authentication.
- **Custom Request Headers**: JSON input for custom headers (e.g. `{"HTTP-Referer": "EasyDash"}`).

### 6. 🖥️ Host PowerShell Environment
- **Execution Engine**: Direct execution via host `powershell.exe` (-NoProfile).
- **Execution Controls**: Configurable timeout (seconds), output buffer character limit, and custom CWD.
- **Pipelines**: Full pipeline syntax (`<cmd1> | <cmd2>`) connecting host commands into LLMs or Antigravity.

### 7. ⚙️ Hub Defaults & System Configuration
- **Startup Defaults**: Default provider engine on launch (`agy`, `lmstudio`, `ollama`, `openai`, `powershell`) and default model identifiers for each engine.
- **Developer UI Preferences**:
  - **Code Copy Preference**: Clean Code Only, Markdown Block with ```lang, or With Line Numbers.
  - **Auto-Scroll Behavior**: Always stick to bottom vs pause on manual wheel up.
  - **Telemetry HUD Mode**: Detailed metrics (latency, tok/s, tokens), Compact, or Hidden.
  - **Sound Feedback**: Subtle audio chime upon generation completion.
- **Settings Backup & Sync**:
  - `💾 Save All Hub Defaults`: Persists all settings to `localStorage` and host server `hub_config.json`.
  - `🔄 Reset Factory Defaults`: Restores initial clean settings.
  - `📤 Export Settings (JSON)`: Download backup of your complete homelab configuration.
  - `📥 Import Settings (JSON)`: Restore settings across browsers or devices.

---

## ⌨️ Arrow-Navigable Slash Command Suite

Type `/` in the prompt input to open the floating command palette overlay with instant fuzzy filtering:
- `↓` / `↑`: Cycle through commands with circular wrap-around and auto-scroll into view.
- `Enter` / `Tab`: Auto-complete selected command with trailing space.
- `Escape`: Dismiss autocomplete menu.

### Slash Command Reference
| Command | Arguments | Description |
| :--- | :--- | :--- |
| `/bionic` | `[on\|off\|toggle]` | Toggle or set Bionic reading speed-reader |
| `/rag` | `<query>` | Run local Bionic RAG semantic retrieval over attached files / pipe |
| `/airgap` | `[on\|off]` | Toggle strict airgap zero-trust isolation policy |
| `/redact` | `[on\|off]` | Toggle PII and secrets scrubber |
| `/ping-lm` | — | Ping LM Studio local server and report round-trip latency |
| `/save-defaults`| — | Persist all current Hub defaults to disk & server |
| `/reset-defaults`| — | Restore factory Hub defaults & provider parameters |
| `/goal` | `<prompt>` | Run autonomous goal mode extra thoroughly until completion |
| `/plan` | `<task>` | Architectural analysis and step-by-step planning |
| `/grill-me` | `<topic>` | Interactive interview to resolve design decisions |
| `/boost` | `<task>` | Deep multi-perspective reasoning with rigorous verification |
| `/browser` | `<query/url>` | Browser automation & web exploration |
| `/teamwork-preview`| `<task>` | Orchestrate a team of autonomous subagents |
| `/learn` | `<rule>` | Persist learned instructions, corrections, or rules |
| `/schedule` | `<time/cron>` | Schedule recurring task or set one-time timer |
| `/compress` | — | Compress session conversation history to free context window |
| `/effort` | `<low\|medium\|high>`| Set Antigravity reasoning effort |
| `/mode` | `<plan\|accept-edits>`| Set agent operational mode |
| `/continue` / `/c`| — | Continue previous Antigravity session turn (`-c`) |
| `/agy` | `<prompt>` | Execute Antigravity CLI with options |
| `/lmstudio` | — | Switch active provider to LM Studio (:1234) |
| `/ollama` | — | Switch active provider to Ollama (:11434) |
| `/models` | — | Open Ollama Model Manager dialog |
| `/pull` | `<model:tag>` | Pull model from Ollama registry with live progress |
| `/search` | `<query>` | Zero-key DuckDuckGo web search & grounding |
| `/scrape` | `<url>` | Clean article text extractor from URL |
| `/ps` | `<command>` | Execute host PowerShell command (`!<cmd>`) |
| `/pipe` | `[text\|clear]` | Manage piped context / stdin buffer |

---

## 🎛️ Resizable AI Chat Window & Flexible Workspaces

The AI Chat Window now features smooth, multi-dimensional resizing and workspace optimization:

- **Prompt Textbox Resizer (`#cliResizeBar`)**:
  - **Direct Vertical Drag Handle**: Drag the resize bar up/down to adjust prompt height smoothly from compact single-line (32px) up to 55% of the viewport height.
  - **Quick Preset Buttons**:
    - `🗕` (Compact): 32px single-line command bar.
    - `🗖` (Medium): 110px comfortable multi-line prompt view.
    - `⤢` (Expanded): 240px comprehensive code and prompt editor.
  - **Double-Click Toggle**: Double-click the resize bar to toggle instantly between compact and expanded views.
  - **Persistent Sizing**: User's chosen height is remembered across sessions via `localStorage`.
- **Draggable History Sidebar Resizer (`#sidebarResizer`)**:
  - Seamless splitter handle between the history sidebar and main chat/CLI container.
  - Drag left/right to resize from 160px up to 45% of the window width.
  - Double-click to reset to default (240px). Width is automatically saved to `localStorage`.
- **Multi-Directional Window Edge & Corner Resizers**:
  - Resize the floating chat window from the top edge (`#chatWinResizerTop`), left edge (`#chatWinResizerLeft`), or top-left corner (`#chatWinResizerTopLeft`).
  - Window dimensions are smoothly preserved in `localStorage`.
- **1-Click Compact Toolbar Mode (`↕ Bar`)**:
  - Toggle button in the chat topbar collapses the telemetry bar and tightens padding to maximize chat log space.
  - State is persisted across browser reloads.

---

## 🎨 High-Contrast & Clean Rendering Engine

- **Token-Protected Markdown Formatter**:
  - Fenced code blocks are isolated prior to markdown transformations, preventing `<br>` injection, double line breaks, and indentation mangling.
  - Clean newline preservation with responsive markdown table generation.
- **WCAG AA Compliant Theme Contrast**:
  - **Light Theme Fixes**: High-contrast blue user message bubbles with white text (4.9:1 contrast ratio), clean slate code cards with dark readable text, crisp inline code tags, high-contrast thinking blocks, and light-mode CLI terminal colors.
  - **Dark Theme Optimization**: Deep navy code cards (`#0c1222`), illuminated syntax tokens, and glowing accent borders.

---

## 🔒 Zero Dependencies, Zero Auth & 100% Offline
- **Backend**: 100% Python 3 standard library (`http.server`, `urllib.request`, `subprocess`, `json`, `threading`, `math`). Zero pip packages.
- **Frontend**: 100% vanilla ES6+ JavaScript, standard CSS3, HTML5. Zero npm packages, zero external CDN dependencies.
- **Intranet & Airgap Ready**: Operates completely offline in airgapped homelabs with strict security guardrails.

