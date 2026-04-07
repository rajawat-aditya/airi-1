# ChromeNavigator Skill

Navigate Google Chrome using `windows_do` with FlaUI/UIA3 actions. No Playwright, no browser-use.

---

## Opening Chrome

```json
{ "app": "chrome" }
```

If `already_running` is returned, skip launch and go straight to `windows_do`.

---

## Verified Chrome Element Names

These names come from live `read_screen` output — use them exactly:

| Element              | Target descriptor                                                          |
|----------------------|----------------------------------------------------------------------------|
| Address / search bar | `{ "name": "Address and search bar", "control_type": "Edit" }`            |
| Back                 | `{ "name": "Back", "control_type": "Button" }`                            |
| Forward              | `{ "name": "Forward", "control_type": "Button" }`                         |
| Reload               | `{ "name": "Reload", "control_type": "Button" }`                          |
| New Tab button       | `{ "name": "New Tab", "control_type": "Button" }`                         |
| Page content         | `read_screen` — no target needed                                           |

> Do NOT use `filter_types` when inspecting Chrome — the address bar lives inside a ToolBar and gets filtered out. Use `windows_inspect` with `depth: 5` and no `filter_types`.

---

## Navigating to a URL

Use `ctrl+l` to focus the address bar — faster and more reliable than clicking:

```json
{
  "app": "chrome",
  "actions": [
    { "action": "key",  "keys": "ctrl+l" },
    { "action": "wait", "ms": 300 },
    { "action": "type", "target": { "name": "Address and search bar", "control_type": "Edit" }, "text": "https://www.youtube.com" },
    { "action": "key",  "keys": "Return" },
    { "action": "wait", "ms": 2500 }
  ]
}
```

---

## Searching Google

Type the query directly into the address bar — Chrome treats it as a Google search:

```json
{
  "app": "chrome",
  "actions": [
    { "action": "key",  "keys": "ctrl+l" },
    { "action": "wait", "ms": 300 },
    { "action": "type", "target": { "name": "Address and search bar", "control_type": "Edit" }, "text": "FlaUI windows automation" },
    { "action": "key",  "keys": "Return" },
    { "action": "wait", "ms": 2500 },
    { "action": "read_screen" }
  ]
}
```

---

## Full Example: Go to YouTube, Search, Click First Video

```json
{
  "app": "chrome",
  "actions": [
    { "action": "key",  "keys": "ctrl+l" },
    { "action": "wait", "ms": 300 },
    { "action": "type", "target": { "name": "Address and search bar", "control_type": "Edit" }, "text": "https://www.youtube.com" },
    { "action": "key",  "keys": "Return" },
    { "action": "wait", "ms": 2500 },
    { "action": "click", "target": { "name": "Search", "control_type": "Edit" } },
    { "action": "type",  "target": { "name": "Search", "control_type": "Edit" }, "text": "MCP tutorial" },
    { "action": "key",   "keys": "Return" },
    { "action": "wait",  "ms": 2000 },
    { "action": "read_screen" }
  ]
}
```

Parse the `read_screen` output to find the first video title, then click it by name:

```json
{
  "app": "chrome",
  "actions": [
    { "action": "click", "target": { "name": "MCP tutorial for beginners" } },
    { "action": "wait",  "ms": 2000 },
    { "action": "read_screen" }
  ]
}
```

If the exact title is unknown, use `text_contains`:

```json
{ "action": "click", "target": { "text_contains": "MCP tutorial" } }
```

---

## Reading Page Content

`read_screen` returns all visible text from the UIA3 tree as a flat newline-separated string. It is fast (< 1s) and requires no screenshot. Always use this to read page content.

```json
{ "action": "read_screen" }
```

---

## Tab Management

| Task                    | Action                                              |
|-------------------------|-----------------------------------------------------|
| Open new tab            | `{ "action": "key", "keys": "ctrl+t" }`             |
| Close current tab       | `{ "action": "key", "keys": "ctrl+w" }`             |
| Next tab                | `{ "action": "key", "keys": "ctrl+Tab" }`           |
| Previous tab            | `{ "action": "key", "keys": "ctrl+shift+tab" }`     |
| Jump to tab N (1–8)     | `{ "action": "key", "keys": "ctrl+1" }` etc.        |

---

## Navigation

| Task      | Action                                              |
|-----------|-----------------------------------------------------|
| Back      | `{ "action": "key", "keys": "alt+left" }`           |
| Forward   | `{ "action": "key", "keys": "alt+right" }`          |
| Reload    | `{ "action": "key", "keys": "ctrl+r" }`             |

> Use keyboard shortcuts for back/forward — they are more reliable than clicking the Back/Forward buttons.

---

## Closing Chrome

Only close when explicitly asked:

```json
{ "action": "close_app" }
```

---

## Handling Natural Language Requests

"Go to YouTube and search for X and click the first video":
1. `windows_launch` `chrome` if not running
2. `windows_do` — navigate to youtube.com, type search, press Enter, wait, `read_screen`
3. Parse `read_screen` output for first video title
4. `windows_do` — click that title by name

If an action fails with "element not found", call `windows_inspect` with `depth: 5` (no `filter_types`) to see what's actually on screen, then retry with the correct element name.
