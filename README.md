# Code Agent - AI Code Generator

Code Agent is a lightweight, AI-powered desktop application that reads architecture documentation and generates a native desktop game project using the DeepSeek API.

The generated game is also a local desktop application: Python/tkinter, offline play,
local score storage, and a PyInstaller build script for a standalone Windows `.exe`.
The updated desktop requirement takes precedence over older web/cloud architecture inputs.

## Features
- **GUI Application**: Modern, dark-themed interface built with `customtkinter`.
- **Architecture Parsing**: Reads markdown architecture documentation and PlantUML views.
- **AI Generation**: Uses DeepSeek's OpenAI-compatible API to structure, plan, and write code.
- **Real-time Logging**: Watch the agent create directories, write files, and output logs in real-time.

## Prerequisites
- Python 3.10+
- DeepSeek API Key (from `platform.deepseek.com`)

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage (GUI)

1. Run the application:
   ```bash
   python main.py
   ```
2. Enter your DeepSeek API Key and click **Test Key** to verify it, then **Save**.
3. Select your **Architecture Documentation** and **Architecture Views** markdown files.
4. Choose an **Output Directory** where the project will be generated.
5. Click **Generate Project** and wait for the agent to finish.
6. In the generated project, run `build.bat` to package the game, then double-click
   `dist/SpaceFractions.exe`. Building requires Python and build dependencies; the
   packaged game requires neither Python nor a DeepSeek key.
7. To play from source with Python installed, use `run.bat` or `python main.py`.

The agent writes source files and build instructions. It performs structural checks
before reporting completion, but does not execute generated code, run its tests, or
compile the game. Follow the generated README to test and build it. An earlier
published CodeAgent executable must be rebuilt to include this new generation target.

### API key storage

- The key is entered at runtime in the GUI and is **never** hard-coded or committed.
- **Test Key** makes one tiny request (`max_tokens=5`) so you can confirm the key works
  before a long generation run.
- Only pressing **Save** persists the key, in plaintext at `~/.codeagent/config.json`
  (the "Success" dialog shows the exact path). To remove it, delete that file or clear
  the field and re-save.
- The key is masked by default and is scrubbed from all log/error output.

## Running Tests

```bash
python -m pytest tests/ -v
```

The suite runs fully offline (no API key needed): config persistence, markdown/PlantUML parsing, file tools + path-traversal guards, the agent loop (via a scripted fake LLM client), prompt building, secret redaction, and API client mapping/retry/Test Key behavior.

## Building the .exe

You can build a standalone Windows executable using PyInstaller:

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```
2. Run the build script:
   ```cmd
   build.bat
   ```
3. The executable will be available in the `dist/` directory.

## Project Structure
- `main.py`: Application entry point.
- `gui.py`: CustomTkinter GUI implementation.
- `agent/`: Core agent logic, tool executions, and prompts.
- `api/`: DeepSeek client wrapper.
- `parser/`: Markdown and PlantUML architecture parsers.
- `utils/`: Configuration and helper functions.

## How It Works
1. **Preprocessing**: The `ArchitecturePreprocessor` parses user-provided markdown files into structured JSON context.
2. **Agent Loop**: The `CodeAgent` builds a system prompt and initiates a chat completion with DeepSeek using OpenAI-compatible function calling.
3. **Tool Execution**: DeepSeek calls tools (like `create_directory`, `create_file`) which are handled by the `ToolExecutor`. The outputs are fed back to the LLM until the project generation is complete.

### Architecture

```
                        ┌──────────────────────────────────┐
                        │              GUI (tkinter)        │
                        │  key · docs · views · output dir  │
                        │  Test Key · Generate · Pause/Cancel│
                        └───────────────┬──────────────────┘
                                        │
                   ┌────────────────────┴────────────────────┐
                   │           parser/preprocessor.py        │
                   │     Markdown + PlantUML ──► JSON        │
                   └────────────────────┬────────────────────┘
                                        ▼
                        ┌──────────────────────────────────┐
                        │       agent/core.py  (loop)       │
                        │   bounded turns · DONE detection  │
                        └───────┬──────────────────┬────────┘
                                │                  │
                  ┌─────────────▼─────┐    ┌───────▼──────────┐
                  │ api/deepseek_client│    │  agent/tools.py  │
                  │  OpenAI-compatible │    │ create_file / dir│
                  │  retry · scrub key │    │ read/list · guard│
                  └────────────────────┘    └──────────────────┘
```

### Agent safeguards
- **Path-traversal guard** (`tools.py`) — tool calls cannot escape the chosen output directory (`..`, absolute paths, and drive-letter edge cases are rejected).
- **Bounded turns + idle detection** (`core.py`) — `MAX_TURNS=60`; after 2 idle turns the model is nudged, after 5 it aborts cleanly.
- **Strict completion** — generation only ends on a word-bounded `DONE`, so prose can't false-trigger success.
- **Desktop output checks** — `DONE` also requires the desktop entry point, game/storage
  modules, manifests, launch/build scripts, README, and tests written during the current
  run. Python syntax, native toolkit imports, and PyInstaller build flags are checked.
  Missing artifacts are returned to the model for correction; repeated failure aborts.
  These checks do not prove runtime or packaging correctness.
- **Result truncation** — tool results are capped at 4000 chars to keep context bounded.
- **Tool-call recovery** — malformed JSON, missing fields, and invalid argument types
  are rejected before files are opened. The model is asked to resend corrected calls;
  three consecutive failed tool turns stop generation with a specific error. Failed
  writes must be retried before completion, including files outside the required set.
- **Output-limit handling** — responses marked as cut short by the provider are not
  executed or accepted as completion. The model is instructed to write one complete
  file per response and split large modules when necessary.
- **Secret scrubbing** — the API key is redacted from all logs and error messages (`utils/security.py`).

## Troubleshooting

**File creation reports missing arguments or invalid JSON.**
These errors come from the model's tool calls, not missing GUI inputs. The updated
agent reports the specific problem and requests corrected calls automatically. If
repeated corrections fail, generation stops instead of reporting success. Relaunch
the rebuilt executable to use this fix; an already-running app still uses its old code.

**"Using SOCKS proxy, but the 'socksio' package is not installed" on Generate.**
Your machine sets a SOCKS proxy via the `all_proxy`/`ALL_PROXY` environment variable.
The bundled HTTP client refuses SOCKS without `socksio`. The client detects this and
connects to `api.deepseek.com` directly (plain HTTP/HTTPS proxies are still honored).
If you still hit it, unset the proxy for the run or set it to an HTTP proxy.

**The exe opens and closes instantly (or no window appears).**
A windowed build swallows errors. Look for `CodeAgent.log` next to `CodeAgent.exe` — it
captures the startup exception. Rebuild or fix the reported cause, then relaunch.

**Generate fails with "invalid API key" / 401.**
Use **Test Key** first; it makes one tiny request to confirm the key before a long run.
The key is never stored unless you press **Save**, and is read at runtime from the GUI.

## License
MIT License
