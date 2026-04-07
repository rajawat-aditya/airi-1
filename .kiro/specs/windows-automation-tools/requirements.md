# Requirements: Windows Automation Tools

## Introduction

This document defines the requirements for a general-purpose Windows UI automation engine exposed as Qwen agent tools. The engine replaces the existing multi-step FlaUI session workflow (and removes the Appium/browser-use dependencies) with a batch-action model that minimises tool calls and agent context usage. Screen content is read via the UIA3 accessibility tree — not screenshots — keeping responses fast and lightweight.

This spec also covers: Chrome browser navigation skill, File Manager skill, agent.py cleanup, OpenAI-compatible API settings, and Electron main.js cleanup.

---

## Requirements

### 1. Automation Engine Core

#### 1.1 FlaUI/UIA3 Singleton

The system MUST initialise a single `UIA3Automation` instance at module load time and reuse it for all operations within the process lifetime.

**Acceptance Criteria:**
- `UIA3Automation` is created once and stored as a module-level singleton
- All tool calls share the same automation instance
- Disposing and recreating the instance per call is not permitted

#### 1.2 Desktop Access

The system MUST obtain the desktop element via `automation.GetDesktop()` to enable switching between any running application.

**Acceptance Criteria:**
- `get_desktop_windows()` returns a list of all top-level window titles and their process names
- The desktop element is used as the root for all window searches

---

### 2. Application Resolution

#### 2.1 Known App Registry

The system MUST maintain a registry mapping common app names to their executable names and title hints, covering at minimum: chrome, excel, word, explorer, whatsapp, cmd, settings, notepad, vlc, spotify.

**Acceptance Criteria:**
- Resolving "chrome" finds a Chrome window without the agent specifying an exe path
- Resolving "excel" finds Microsoft Excel
- Resolving "cmd" finds a Command Prompt window
- Registry is case-insensitive

#### 2.2 Multi-Strategy Resolution

The system MUST attempt 4 resolution strategies in order before returning None:
1. Exact window title match
2. Window title contains app name (case-insensitive)
3. Process name match via psutil
4. Fuzzy title match (difflib ratio > 0.6)

**Acceptance Criteria:**
- If strategy 1 fails, strategy 2 is attempted automatically
- None is returned only after all 4 strategies are exhausted
- Resolution never raises an unhandled exception

#### 2.3 Unknown Apps

The system MUST handle app names not in the known registry by falling back to strategies 2-4 using the raw app name string.

---

### 3. Element Finding

#### 3.1 Multi-Strategy Element Resolution

The system MUST resolve UI elements using up to 5 strategies in priority order: automation_id, exact name, name contains, control_type+index, text_contains scan.

#### 3.2 No Exception on Miss

The system MUST return None (not raise) when no element matches the target descriptor.

#### 3.3 Partial Name Matching

The system MUST support partial, case-insensitive name matching so the agent does not need to know exact element labels.

---

### 4. Action Execution

#### 4.1 Supported Actions

The system MUST support the following action types: click, double_click, right_click, type, key, scroll, focus, read, read_screen, wait, screenshot, close_app.

**Acceptance Criteria:**
- `type` clears the element before typing unless `append: true` is set
- `key` supports modifier combos in the format "ctrl+c", "alt+F4", "ctrl+shift+esc"
- `scroll` accepts direction (up/down/left/right) and amount (number of ticks)
- `read` returns the current text/value of a specific target element
- `read_screen` returns all visible text content from the entire window as a flat string — no target required, no screenshot needed; preferred over screenshot for reading content
- `screenshot` saves a PNG and returns the file path (use sparingly)
- `close_app` closes the target window (explicit only)

#### 4.2 Batch Execution

The system MUST execute all actions in a batch sequentially and return one result per action.

**Acceptance Criteria:**
- Result array length equals input actions array length
- A failed action does not abort subsequent actions
- Each result contains: action, target, status, detail, value

#### 4.3 Explicit Close Only

The system MUST NOT close any application window unless a `close_app` action is explicitly present in the batch.

---

### 5. Agent Tools (flaui.py -> agent.py)

#### 5.1 windows_launch Tool

Starts a Windows application by name. If already running, returns `already_running`.

**Acceptance Criteria:**
- Accepts `app` (required) and `args` (optional)
- Waits up to 5 seconds for window to appear
- Returns `{"status": "launched"|"already_running"|"error", "window_title": str, "detail": str}`

#### 5.2 windows_inspect Tool

Returns a compact UI element tree for a running application.

**Acceptance Criteria:**
- Accepts `app`, `depth` (default 4), `filter_types` (optional comma-separated)
- Returns max 200 elements sorted by depth
- Returns error dict if window not found

#### 5.3 windows_do Tool

Executes a batch of UI actions. Primary interaction tool.

**Acceptance Criteria:**
- Accepts `app` and `actions` (JSON array or JSON string)
- Returns JSON array of ActionResult objects

#### 5.4 Tool Count

Exactly 3 FlaUI tools: `windows_launch`, `windows_inspect`, `windows_do`. All old tools removed.

---

### 6. agent.py Cleanup

#### 6.1 Remove Appium and browser-use

**Acceptance Criteria:**
- `from browser_use import ...`, `from browser_use.browser.service import Browser`, `from langchain_openai import ChatOpenAI` deleted
- `ChromeBrowser` class deleted
- `BrowserAutomationTool` (`browser_automation`) deleted
- `import win` and all `win.*` calls deleted
- `ACTIVE_SESSIONS` dict deleted
- Old FlaUI tools (`search_win_app_by_name`, `start_app_session`, `inspect_ui_elements`, `list_element_names`, `get_element_details`, `stop_app_session`) deleted

#### 6.2 OpenAI-Compatible API Settings

The system MUST support switching the LLM backend to any OpenAI-compatible API at runtime via settings endpoints.

**Acceptance Criteria:**
- A `GET /settings` endpoint returns current LLM config: `{model_server, model, thinking_enabled}`
- A `POST /settings` endpoint accepts `{model_server, model, api_key, thinking_enabled}` and hot-reloads the agent with the new config without restarting the process
- Settings are persisted to `agent-server/settings.json` so they survive restarts
- On startup, agent.py loads `settings.json` if it exists, falling back to defaults (local llama-server at port 11434, model "default")
- The frontend Settings page can call these endpoints to let the user switch between local Qwen and any third-party OpenAI-compatible API (OpenAI, Groq, Together, Ollama, etc.)

#### 6.3 Preserve Non-Automation Features

Memory tools, file upload, audio transcription, WebSocket, library, and health endpoints are unchanged.

#### 6.4 Updated System Prompt

The SYSTEM_PROMPT must be updated to reference the 3 new tools and remove references to old tools and browser_automation.

---

### 7. flaui.py Module

#### 7.1 Module Structure

The system MUST implement the automation engine in `agent-server/flaui.py`, replacing the existing proof-of-concept code.

**Acceptance Criteria:**
- `flaui.py` exports `WindowsAutomationEngine`, `AppResolver`, `ElementFinder`, `ActionExecutor`
- The module initialises the FlaUI DLL path and loads CLR references at import time
- A module-level `engine` singleton is available for import by `agent.py`

#### 7.2 DLL Loading

The system MUST load FlaUI DLLs from `deps/flaui/` relative to the module file, using the existing pythonnet/clr pattern.

---

### 8. Electron main.js Cleanup

#### 8.1 Remove Appium Process

**Acceptance Criteria:**
- `startAppium()` function deleted
- `appiumProcess` variable deleted
- `startAppium()` call removed from `app.whenReady()`
- `appiumProcess` removed from `before-quit` cleanup

#### 8.2 LLM Server Configurability

**Acceptance Criteria:**
- `startLlama()` reads model name from `agent-server/settings.json` at launch time
- If `model_server` in settings points to an external URL (not localhost/127.0.0.1), llama-server is NOT started — the external API is used directly

---

### 9. WindowsAutomator.md Skill

**Acceptance Criteria:**
- Located at `agent-server/WindowsAutomator.md`
- Covers: tool reference, action type table, target descriptor syntax
- Includes ready-to-paste example JSON batches for: Chrome navigation, Excel cell editing, WhatsApp message, CMD command, File Explorer navigation, Settings
- Explains `read_screen` as the preferred content-reading method (fast, no image overhead)
- Explains explicit `close_app` requirement and when to call `windows_inspect` vs `windows_do` directly
- Written in imperative language suitable for an LLM system prompt section

---

### 10. ChromeNavigator.md Skill

#### 10.1 Chrome Navigation via FlaUI

The system MUST provide a skill file that teaches the agent to navigate Chrome using `windows_do` actions — no Playwright, no browser-use.

**Acceptance Criteria:**
- Located at `agent-server/ChromeNavigator.md`
- Covers: opening Chrome, typing in address bar, searching Google, clicking links, reading page content via `read_screen`, switching tabs, closing tabs
- Includes complete example JSON batches for: "Go to youtube.com and search for X", "Click the first result", "Read the current page title"
- Uses FlaUI element patterns specific to Chrome (address bar automation_id, tab strip, etc.)
- Agent can follow this skill to handle natural language browser requests like "Go to YouTube and search for MCP and click the first video"

---

### 11. FileManager.md Skill + file_op Tool

#### 11.1 file_op Tool

A new `file_op` tool for fast programmatic file operations without needing FlaUI.

**Acceptance Criteria:**
- Registered as `file_op` in agent.py
- Accepts `{"op": "list"|"open"|"copy"|"move"|"delete"|"create_folder"|"search", "path": "...", ...}`
- `list` returns: name, size, modified, type (file/folder), extension for each item
- `open` launches the file with its default application via `os.startfile`
- `search` accepts `path` and `pattern` (glob or name fragment), returns matching files recursively
- Special path aliases: "desktop", "downloads", "documents", "pictures" resolve to actual Windows paths

#### 11.2 FileManager.md Skill

**Acceptance Criteria:**
- Located at `agent-server/FileManager.md`
- When user says "show me files on my desktop", agent calls `file_op(op=list, path=desktop)` AND `windows_launch(app=explorer, args=shell:Desktop)`
- Covers: listing files, opening files, navigating folders, searching by name/extension, creating folders
- Includes examples for "show me files on my desktop", "open Downloads folder", "find all PDFs in Documents"

---

### 12. InstalledApps Tool

#### 12.1 list_installed_apps Tool

**Acceptance Criteria:**
- Registered as `list_installed_apps` in agent.py
- Uses PowerShell `Get-StartApps` via subprocess to enumerate installed apps
- Returns a JSON array of `{name, app_id}` objects
- Falls back to scanning `%APPDATA%\Microsoft\Windows\Start Menu` shortcuts if PowerShell fails
- Agent uses this to answer "what apps do I have installed?" or to find the right app name before `windows_launch`

---

### 13. Non-Functional Requirements

#### 13.1 Performance
- `windows_inspect` completes within 3 seconds
- `read_screen` completes within 1 second
- `file_op list` completes within 500ms for typical directories

#### 13.2 Robustness
- No unhandled exception propagates to the agent framework
- All errors returned as JSON error responses

#### 13.3 Model Compatibility
- All tools and prompts are optimised for `Qwen/Qwen3-VL-2B-Instruct-GGUF` with thinking enabled
- Tool descriptions are kept short and unambiguous to minimise token usage on a 2B model
- JSON action batches reduce round-trips, keeping the model's context window usage low
