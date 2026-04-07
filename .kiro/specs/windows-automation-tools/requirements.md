# Requirements: Windows Automation Tools

## Introduction

This document defines the requirements for a general-purpose Windows UI automation engine exposed as Qwen agent tools. The engine replaces the existing multi-step FlaUI session workflow (and removes the Appium/browser-use dependencies) with a batch-action model that minimises tool calls and agent context usage. Screen content is read via the UIA3 accessibility tree — not screenshots — keeping responses fast and lightweight.

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

The system MUST maintain a registry mapping common app names to their executable names and title hints, covering at minimum: chrome, excel, word, explorer, whatsapp, cmd, settings.

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
- If strategies 1–3 fail, fuzzy match is attempted
- None is returned only after all 4 strategies are exhausted
- Resolution never raises an unhandled exception

#### 2.3 Unknown Apps

The system MUST handle app names not in the known registry by falling back to strategies 2–4 using the raw app name string.

**Acceptance Criteria:**
- Passing an unknown app name does not raise a KeyError
- Fuzzy matching still runs against all open window titles

---

### 3. Element Finding

#### 3.1 Multi-Strategy Element Resolution

The system MUST resolve UI elements using up to 5 strategies in priority order: automation_id, exact name, name contains, control_type+index, text_contains scan.

**Acceptance Criteria:**
- If `automation_id` is provided and matches, it is used without trying other strategies
- If only `name` is provided, exact match is tried first, then contains match
- If only `control_type` is provided, the nth element (default index 0) of that type is returned
- `text_contains` scans Edit and Document control types for matching value

#### 3.2 No Exception on Miss

The system MUST return None (not raise) when no element matches the target descriptor.

**Acceptance Criteria:**
- Any valid target dict that matches nothing returns None
- The batch executor handles None by recording an error result and continuing

#### 3.3 Partial Name Matching

The system MUST support partial, case-insensitive name matching so the agent does not need to know exact element labels.

**Acceptance Criteria:**
- Target `{"name": "address"}` matches an element named "Address bar"
- Matching is case-insensitive

---

### 4. Action Execution

#### 4.1 Supported Actions

The system MUST support the following action types: click, double_click, right_click, type, key, scroll, focus, read, read_screen, wait, screenshot, close_app.

**Acceptance Criteria:**
- Each action type executes without error when given valid inputs
- `type` clears the element before typing unless `append: true` is set
- `key` supports modifier combos in the format "ctrl+c", "alt+F4", "ctrl+shift+esc"
- `scroll` accepts direction (up/down/left/right) and amount (number of ticks)
- `read` returns the current text/value of a specific target element in the result's `value` field
- `read_screen` returns all visible text content from the entire window as a flat string — no target required, no screenshot needed
- `screenshot` saves a PNG to the screenshots directory and returns the file path (use sparingly)
- `close_app` closes the target window

#### 4.2 Batch Execution

The system MUST execute all actions in a batch sequentially and return one result per action.

**Acceptance Criteria:**
- Result array length equals input actions array length
- A failed action (element not found, FlaUI error) does not abort subsequent actions
- Each result contains: action, target (resolved name or None), status, detail, value

#### 4.3 Explicit Close Only

The system MUST NOT close any application window unless a `close_app` action is explicitly present in the batch.

**Acceptance Criteria:**
- Completing a batch without `close_app` leaves the application running
- The agent must explicitly include `{"action": "close_app"}` to close a window

---

### 5. Agent Tools

#### 5.1 windows_launch Tool

The system MUST provide a `windows_launch` tool that starts a Windows application by name.

**Acceptance Criteria:**
- Accepts `app` (required) and `args` (optional) parameters
- If the app is already running, returns `status: "already_running"` with the window title
- If launch succeeds, waits up to 5 seconds for the window to appear before returning
- Returns `{"status": "launched"|"already_running"|"error", "window_title": str, "detail": str}`
- Registered via `@register_tool('windows_launch')` following the existing agent.py pattern

#### 5.2 windows_inspect Tool

The system MUST provide a `windows_inspect` tool that returns a compact UI element tree for a running application.

**Acceptance Criteria:**
- Accepts `app` (required), `depth` (optional, default 4), `filter_types` (optional)
- Returns a JSON array of elements with: name, automation_id, control_type, value, rect, depth
- Limits output to 200 elements maximum, sorted by depth ascending
- `filter_types` accepts a comma-separated list of control type names to include
- Returns an error dict if the window is not found
- Registered via `@register_tool('windows_inspect')`

#### 5.3 windows_do Tool

The system MUST provide a `windows_do` tool that executes a batch of UI actions against a running application.

**Acceptance Criteria:**
- Accepts `app` (required) and `actions` (required, JSON array) parameters
- Parses `actions` from JSON string if passed as string
- Returns a JSON array of ActionResult objects
- Registered via `@register_tool('windows_do')`
- This is the primary interaction tool; all UI interaction goes through it

#### 5.4 Tool Count

The system MUST expose exactly 3 tools to the agent: `windows_launch`, `windows_inspect`, `windows_do`.

**Acceptance Criteria:**
- No other FlaUI-related tools are registered
- The existing `search_win_app_by_name`, `start_app_session`, `inspect_ui_elements`, `list_element_names`, `get_element_details`, `stop_app_session` tools are removed
- The `browser_automation` tool (browser-use / Playwright) is removed from agent.py
- All Appium/browser-use imports and the `win.py` session management are removed from agent.py

---

### 6. agent.py Cleanup

#### 6.1 Remove Appium and browser-use

The system MUST remove all Appium/WinAppDriver and browser-use dependencies from agent.py.

**Acceptance Criteria:**
- `from browser_use import Agent as BrowserAgent` and related imports are deleted
- `from browser_use.browser.service import Browser` is deleted
- `ChromeBrowser` class is deleted
- `BrowserAutomationTool` (`browser_automation`) is deleted
- `import win` and all `win.*` calls are deleted
- `ACTIVE_SESSIONS` dict is deleted
- `langchain_openai` import is deleted (was only used by BrowserAgent)
- The agent server starts cleanly without any of the above

#### 6.2 Preserve Non-Automation Features

The system MUST keep all non-automation features intact.

**Acceptance Criteria:**
- Memory tools (add_memory, search_memories, get_memories, get_memory, update_memory, delete_memory, delete_all_memories) are unchanged
- File upload, audio transcription, WebSocket, and health endpoints are unchanged
- mem0 / qdrant initialisation is unchanged

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

**Acceptance Criteria:**
- DLL path is computed relative to `__file__`, not hardcoded
- `FlaUI.Core`, `FlaUI.UIA3`, `Interop.UIAutomationClient` are loaded via `clr.AddReference`

---

### 8. Skill Steering File

#### 8.1 WindowsAutomator.md

The system MUST include a `WindowsAutomator.md` skill file that instructs the Qwen agent precisely how to use the 3 tools.

**Acceptance Criteria:**
- Located at `agent-server/WindowsAutomator.md` (or a path the agent system prompt references)
- Covers: when to use each tool, action type reference, target descriptor syntax, example action batches for common tasks (open Chrome and navigate, type in Excel cell, send WhatsApp message, run CMD command)
- Explains `read_screen` as the preferred way to read window content (fast, text-only, no screenshot overhead)
- Explains that `close_app` must be explicit
- Explains when to call `windows_inspect` vs going straight to `windows_do`
- Written in clear, imperative language suitable for an LLM system prompt

---

### 9. Non-Functional Requirements

#### 9.1 Performance

- `windows_inspect` MUST complete within 3 seconds for typical applications
- `windows_do` batch execution MUST add no more than 100ms overhead per action beyond the FlaUI call itself
- `read_screen` MUST complete within 1 second for typical windows by scanning only visible text nodes

#### 9.2 Robustness

- No unhandled exception from any tool call must propagate to the agent framework; all errors MUST be caught and returned as JSON error responses
- The engine MUST remain usable after a failed action (no broken state)

#### 9.3 Compatibility

- MUST work with the existing `@register_tool` / `BaseTool` pattern in `agent.py`
- MUST NOT require changes to the agent server startup or DLL loading infrastructure
