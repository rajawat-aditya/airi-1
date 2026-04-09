# WindowsAutomator Skill

Control any Windows application using three tools: `windows_launch`, `windows_inspect`, `windows_do`.

- `windows_do` — all interaction (click, type, key, read, etc.)
- `windows_inspect` — discover element names/IDs when you don't know them
- `windows_launch` — open an app that isn't running yet

---

## Tool Reference

### windows_launch

```json
{ "app": "chrome" }
{ "app": "notepad", "args": "C:\\file.txt" }
```

Returns: `{ "status": "launched" | "already_running" | "error", "window_title": "...", "detail": "..." }`

If `already_running` — do not launch again, proceed directly to `windows_do`.

### windows_inspect

Returns a list of UI elements. Use when you need to find element names or automation IDs.

```json
{ "app": "excel", "depth": 5 }
```

- Default `depth` is 4. Use 5 for Chrome (address bar is nested inside a ToolBar).
- Do NOT use `filter_types` for Chrome — it filters out elements inside ToolBars.
- Use `filter_types` for Office apps to narrow results: `"Button,Edit,Document"`

Returns: `[{ "name", "automation_id", "control_type", "value", "rect", "depth" }]`

### windows_do

Primary interaction tool. Submit all actions for a task in one call.

```json
{ "app": "chrome", "actions": [ ... ] }
```

Returns: `[{ "action", "target", "status", "detail", "value" }]`

On error, each failed result includes `"inspect_fallback"` — a snapshot of what's currently on screen. Use this to understand unexpected UI (dialogs, popups, wrong state) and recover.

---

## Action Types

| action        | Required fields                | Notes                                                              |
|---------------|--------------------------------|--------------------------------------------------------------------|
| `click`       | `target`                       | Left-click center of element                                       |
| `double_click`| `target`                       | Double-click                                                       |
| `right_click` | `target`                       | Opens context menu                                                 |
| `type`        | `target`, `text`               | Clears then types. `"append": true` to keep existing content       |
| `key`         | `keys`                         | `"ctrl+c"`, `"alt+F4"`, `"ctrl+shift+esc"`, `"Return"`, `"Escape"`|
| `scroll`      | `target`, `direction`, `amount`| direction: up/down/left/right. amount: ticks                       |
| `focus`       | `target`                       | Set keyboard focus                                                 |
| `read`        | `target`                       | Return text/value of one element                                   |
| `read_screen` | —                              | Return ALL visible text in window. No target. Preferred for reading.|
| `wait`        | `ms`                           | Sleep N milliseconds                                               |
| `screenshot`  | —                              | Save PNG, return file path. Use sparingly.                         |
| `close_app`   | —                              | Close window. Only runs when explicitly included.                  |

---

## Target Descriptor

```json
{
  "name": "OK",
  "automation_id": "btn_ok",
  "control_type": "Button",
  "index": 0,
  "text_contains": "Submit"
}
```

Resolution order (first match wins):
1. `automation_id`
2. `name` exact
3. `name` contains (case-insensitive)
4. `control_type` + `index`
5. `text_contains` scan

---

## App Names

Apps are resolved from `installed_apps.json` (built at startup from Start Menu shortcuts). These always work:

`chrome`, `word`, `excel`, `explorer`, `cmd`, `notepad`, `settings`

For any other app, pass the name as you know it — the engine tries title match, process name, and fuzzy match.

---

## Error Recovery

When `windows_do` returns `"status": "error"`, check `"inspect_fallback"` in the result — it contains the current UI tree. Use it to:
- Identify unexpected dialogs (save dialog, error popup, UAC prompt)
- Find the correct element name to retry with
- Understand what state the app is in

Do NOT call `windows_inspect` separately after an error — the fallback is already there.

---

## Example Batches

### Chrome — navigate to URL

```json
{
  "app": "chrome",
  "actions": [
    { "action": "key",  "keys": "ctrl+l" },
    { "action": "wait", "ms": 300 },
    { "action": "type", "target": { "name": "Address and search bar", "control_type": "Edit" }, "text": "https://www.google.com" },
    { "action": "key",  "keys": "Return" },
    { "action": "wait", "ms": 2000 },
    { "action": "read_screen" }
  ]
}
```

### Excel — type in cell A1

```json
{
  "app": "excel",
  "actions": [
    { "action": "click", "target": { "name": "Name Box", "control_type": "Edit" } },
    { "action": "type",  "target": { "name": "Name Box", "control_type": "Edit" }, "text": "A1" },
    { "action": "key",   "keys": "Return" },
    { "action": "type",  "target": { "name": "Formula Bar", "control_type": "Edit" }, "text": "Hello World" },
    { "action": "key",   "keys": "Return" }
  ]
}
```

### Word — type and read back

```json
{
  "app": "word",
  "actions": [
    { "action": "key",  "keys": "ctrl+Home" },
    { "action": "type", "target": { "control_type": "Document", "index": 0 }, "text": "Hello World" },
    { "action": "wait", "ms": 300 },
    { "action": "read", "target": { "control_type": "Document", "index": 0 } }
  ]
}
```

### CMD — run a command and read output

```json
{
  "app": "cmd",
  "actions": [
    { "action": "type", "target": { "control_type": "Edit", "index": 0 }, "text": "dir C:\\Users" },
    { "action": "key",  "keys": "Return" },
    { "action": "wait", "ms": 1000 },
    { "action": "read_screen" }
  ]
}
```

### Explorer — navigate to folder

```json
{
  "app": "explorer",
  "actions": [
    { "action": "key",  "keys": "ctrl+l" },
    { "action": "wait", "ms": 300 },
    { "action": "type", "target": { "name": "Address", "control_type": "Edit" }, "text": "C:\\Users\\Public\\Documents" },
    { "action": "key",  "keys": "Return" },
    { "action": "wait", "ms": 800 },
    { "action": "read_screen" }
  ]
}
```

### WhatsApp — send a message

```json
{
  "app": "whatsapp",
  "actions": [
    { "action": "click", "target": { "name": "Search", "control_type": "Edit" } },
    { "action": "type",  "target": { "name": "Search", "control_type": "Edit" }, "text": "John" },
    { "action": "wait",  "ms": 1000 },
    { "action": "click", "target": { "name": "John", "control_type": "ListItem" } },
    { "action": "type",  "target": { "name": "Type a message", "control_type": "Edit" }, "text": "Hello!" },
    { "action": "key",   "keys": "Return" }
  ]
}
```

### Settings — open a section

```json
{
  "app": "settings",
  "actions": [
    { "action": "click", "target": { "name": "System", "control_type": "ListItem" } },
    { "action": "wait",  "ms": 500 },
    { "action": "read_screen" }
  ]
}
```

---

## When to Inspect vs Go Direct

- Go direct to `windows_do` when element names are predictable (OK, Cancel, Search, Address bar, Name Box).
- Call `windows_inspect` with `depth: 5` when the app is unfamiliar or a previous action returned "element not found" and `inspect_fallback` didn't help.
- For Chrome, always use `depth: 5` with no `filter_types`.

## Reading Content

Always use `read_screen` — it reads the UIA3 accessibility tree directly, returns all visible text as a flat string, and takes < 1 second. Use `screenshot` only when visual layout matters.

## Closing Apps

`close_app` only fires when explicitly in the batch. The engine never auto-closes. If a save dialog appears after close, check `inspect_fallback` on the close result and handle it.
