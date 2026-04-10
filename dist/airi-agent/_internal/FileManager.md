# FileManager Skill

Use `file_op` for all programmatic file operations. Use `windows_launch` with `app: "explorer"` when the user wants to visually browse a folder. Combine both when needed.

---

## file_op Parameters

```json
{
  "op":      "list | open | copy | move | delete | create_folder | search",
  "path":    "desktop",
  "dest":    "C:\\Users\\John\\Backup",
  "pattern": "*.pdf"
}
```

### Path Aliases

Always use aliases instead of full paths when possible:

| Alias       | Resolves to                        |
|-------------|------------------------------------|
| `desktop`   | `C:\Users\<user>\Desktop`          |
| `downloads` | `C:\Users\<user>\Downloads`        |
| `documents` | `C:\Users\<user>\Documents`        |
| `pictures`  | `C:\Users\<user>\Pictures`         |

---

## Operations

### list

Returns `[{ name, type, size, modified, ext }]` for each item.

```json
{ "op": "list", "path": "desktop" }
{ "op": "list", "path": "C:\\Projects\\myapp" }
```

### open

Opens with default application. Works on files and folders.

```json
{ "op": "open", "path": "downloads" }
{ "op": "open", "path": "C:\\Users\\John\\report.pdf" }
```

### search

Searches recursively. Use glob (`*.pdf`) or name fragment (`invoice`). Returns up to 100 paths.

```json
{ "op": "search", "path": "documents", "pattern": "*.pdf" }
{ "op": "search", "path": "desktop",   "pattern": "invoice" }
```

### copy

```json
{ "op": "copy", "path": "documents\\report.pdf", "dest": "desktop\\report_backup.pdf" }
```

### move

```json
{ "op": "move", "path": "downloads\\photo.jpg", "dest": "desktop\\photo.jpg" }
```

### delete

```json
{ "op": "delete", "path": "desktop\\old_file.txt" }
```

### create_folder

```json
{ "op": "create_folder", "path": "documents\\ProjectX" }
```

---

## Common Patterns

### "Show me files on my desktop"

```json
{ "op": "list", "path": "desktop" }
```

Then open Explorer so the user can see it visually:

```json
{ "app": "explorer", "args": "shell:Desktop" }
```

### "Open my Downloads folder"

```json
{ "op": "open", "path": "downloads" }
```

### "Find all PDFs in Documents"

```json
{ "op": "search", "path": "documents", "pattern": "*.pdf" }
```

### "Find files named invoice"

```json
{ "op": "search", "path": "documents", "pattern": "invoice" }
```

### "Create a folder on the desktop"

```json
{ "op": "create_folder", "path": "desktop\\NewProject" }
```

### "Move a file from Downloads to Desktop"

```json
{ "op": "move", "path": "downloads\\photo.jpg", "dest": "desktop\\photo.jpg" }
```

---

## Combined file_op + windows_launch

When the user wants to see files AND browse in Explorer:

1. `file_op list` — get the file list to answer the question
2. `windows_launch explorer` — open the folder visually

Explorer shell paths:
- `shell:Desktop` — Desktop
- `shell:Downloads` — Downloads
- `shell:Personal` — Documents
- `shell:My Pictures` — Pictures

---

## file_op vs windows_do on Explorer

- Use `file_op` for listing, searching, copying, moving, deleting — it's faster and returns structured data.
- Use `windows_do` on Explorer only for UI interaction (right-click menu, ribbon, address bar navigation).
- For most file tasks, `file_op` alone is enough — no need to open Explorer.

---

## list_installed_apps

To find the right app name before `windows_launch`:

```json
{}
```

Returns `[{ "name", "app_id" }]`. Search the result for the app name, then pass it to `windows_launch`.
