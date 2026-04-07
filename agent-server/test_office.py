"""
test_office.py — Smoke tests for Word + Excel automation via flaui.py engine.
Tests launching both apps, typing content, switching between them at runtime,
reading content back, and closing both cleanly.

Usage:
    cd agent-server
    python test_office.py
"""

import sys
import json
import time

try:
    from flaui import engine, _FLAUI_AVAILABLE, _FLAUI_ERROR
except Exception as e:
    print(f"[FAIL] Could not import flaui: {e}")
    sys.exit(1)

PASS = "✓"
FAIL = "✗"
results = []

def check(name, condition, detail=""):
    status = PASS if condition else FAIL
    results.append((status, name, detail))
    print(f"  {status}  {name}" + (f"  →  {detail}" if detail else ""))

def do(app, actions, label=""):
    r = engine.execute_batch(app, actions)
    if label:
        print(f"     [{label}] {json.dumps(r, ensure_ascii=False)}")
    return r

def all_ok(r):
    return all(x.get("status") == "ok" for x in r)

# ── 0. FlaUI availability ────────────────────────────────────────────────────
print("\n[0] FlaUI availability")
check("FlaUI DLLs loaded",      _FLAUI_AVAILABLE, str(_FLAUI_ERROR) if not _FLAUI_AVAILABLE else "ok")
check("engine singleton exists", engine is not None)

if not _FLAUI_AVAILABLE:
    print("\nFlaUI not available — skipping all live tests.")
    sys.exit(1)

# ── 1. Launch Word ───────────────────────────────────────────────────────────
print("\n[1] Launch Word")
r = engine.launch_app("word")
print(f"     raw: {r}")
check("Word launched or already running", r.get("status") in ("launched", "already_running"))
check("Word window title non-empty",      bool(r.get("window_title")))
check("Word title contains 'Word'",       "word" in r.get("window_title", "").lower())
time.sleep(2)

# ── 2. Launch Excel ──────────────────────────────────────────────────────────
print("\n[2] Launch Excel")
r = engine.launch_app("excel")
print(f"     raw: {r}")
check("Excel launched or already running", r.get("status") in ("launched", "already_running"))
check("Excel window title non-empty",      bool(r.get("window_title")))
check("Excel title contains 'Excel'",      "excel" in r.get("window_title", "").lower())
time.sleep(2)

# ── 3. Inspect Word elements ─────────────────────────────────────────────────
print("\n[3] Inspect Word — find document area")
elements = engine.inspect_window("word", depth=4, filter_types="Document,Edit,Pane")
check("inspect returns list",    isinstance(elements, list))
check("at least 1 element",      len(elements) >= 1, f"{len(elements)} elements")
has_doc = any(e.get("control_type", "").lower() in ("document", "edit", "pane") for e in elements if "error" not in e)
check("document/edit area found", has_doc,
      str([(e.get("name"), e.get("control_type")) for e in elements[:6] if "error" not in e]))

# ── 4. Inspect Excel elements ────────────────────────────────────────────────
print("\n[4] Inspect Excel — find formula bar / cell")
elements = engine.inspect_window("excel", depth=4, filter_types="Edit,Custom")
check("inspect returns list",    isinstance(elements, list))
check("at least 1 element",      len(elements) >= 1, f"{len(elements)} elements")

# ── 5. Type in Word ──────────────────────────────────────────────────────────
print("\n[5] Type text in Word")
# Dismiss Backstage / start screen — click "Blank document" if visible
screen = engine.execute_batch("word", [{"action": "read_screen"}])
screen_text_pre = screen[0].get("value") or ""
if "blank document" in screen_text_pre.lower():
    engine.execute_batch("word", [
        {"action": "click", "target": {"name": "Blank document"}},
        {"action": "wait",  "ms": 1500},
    ])
elif "backstage" in screen_text_pre.lower():
    engine.execute_batch("word", [
        {"action": "key",  "keys": "Escape"},
        {"action": "wait", "ms": 800},
    ])

r = do("word", [
    {"action": "key",  "keys": "ctrl+Home"},
    {"action": "key",  "keys": "ctrl+a"},
    {"action": "key",  "keys": "delete"},
    {"action": "type", "target": {"control_type": "Document", "index": 0}, "text": "Hello from FlaUI Word test"},
    {"action": "wait", "ms": 500},
    {"action": "read", "target": {"control_type": "Document", "index": 0}},
], "word type+read")
check("6 results returned",  len(r) == 6)
check("type ok",             r[3].get("status") == "ok", r[3].get("detail"))
read_val = r[5].get("value") or ""
check("read ok",             r[5].get("status") == "ok", r[5].get("detail"))
check("Word contains typed text", "Hello from FlaUI" in read_val, repr(read_val[:80]))

# ── 6. Switch to Excel ───────────────────────────────────────────────────────
print("\n[6] Switch to Excel (windows_do on excel app)")
# Dismiss Excel start screen — click "Blank workbook" if visible
exc_screen = engine.execute_batch("excel", [{"action": "read_screen"}])
exc_text_pre = exc_screen[0].get("value") or ""
if "blank workbook" in exc_text_pre.lower():
    engine.execute_batch("excel", [
        {"action": "click", "target": {"name": "Blank workbook"}},
        {"action": "wait",  "ms": 1500},
    ])
elif "backstage" in exc_text_pre.lower():
    engine.execute_batch("excel", [
        {"action": "key",  "keys": "Escape"},
        {"action": "wait", "ms": 800},
    ])

r = do("excel", [
    {"action": "read_screen"},
], "switch to excel")
check("Excel read_screen ok",    r[0].get("status") == "ok", r[0].get("detail"))
excel_screen = r[0].get("value") or ""
check("Excel screen has content", len(excel_screen) > 0, f"{len(excel_screen)} chars")

# ── 7. Type in Excel cell A1 ─────────────────────────────────────────────────
print("\n[7] Type in Excel — cell A1")
r = do("excel", [
    {"action": "click",  "target": {"name": "Name Box", "control_type": "Edit"}},
    {"action": "type",   "target": {"name": "Name Box", "control_type": "Edit"}, "text": "A1"},
    {"action": "key",    "keys": "Return"},
    {"action": "wait",   "ms": 300},
    {"action": "type",   "target": {"name": "Formula Bar", "control_type": "Edit"}, "text": "FlaUI Excel Test"},
    {"action": "key",    "keys": "Return"},
    {"action": "wait",   "ms": 300},
], "excel A1")
check("7 results returned", len(r) == 7)
check("Name Box click ok",  r[0].get("status") == "ok", r[0].get("detail"))
check("type A1 ok",         r[1].get("status") == "ok", r[1].get("detail"))
check("formula bar type ok", r[4].get("status") == "ok", r[4].get("detail"))

# ── 8. Read Excel cell back ──────────────────────────────────────────────────
print("\n[8] Read Excel cell A1 back")
r = do("excel", [
    {"action": "click",  "target": {"name": "Name Box", "control_type": "Edit"}},
    {"action": "type",   "target": {"name": "Name Box", "control_type": "Edit"}, "text": "A1"},
    {"action": "key",    "keys": "Return"},
    {"action": "wait",   "ms": 300},
    {"action": "read",   "target": {"name": "Formula Bar", "control_type": "Edit"}},
], "read A1")
check("5 results returned", len(r) == 5)
cell_val = r[4].get("value") or ""
check("read ok",             r[4].get("status") == "ok", r[4].get("detail"))
check("cell contains typed text", "FlaUI Excel Test" in cell_val, repr(cell_val))

# ── 9. Switch back to Word ───────────────────────────────────────────────────
print("\n[9] Switch back to Word")
r = do("word", [
    {"action": "read_screen"},
], "switch back to word")
check("Word read_screen ok",    r[0].get("status") == "ok", r[0].get("detail"))
word_screen = r[0].get("value") or ""
check("Word screen has content", len(word_screen) > 0, f"{len(word_screen)} chars")
check("Word screen still has typed text", "Hello from FlaUI" in word_screen, repr(word_screen[:120]))

# ── 10. Rapid switch: Word → Excel → Word → Excel ────────────────────────────
print("\n[10] Rapid switching Word ↔ Excel (4 switches)")
switch_results = []
for i, app in enumerate(["excel", "word", "excel", "word"]):
    r = do(app, [{"action": "read_screen"}])
    ok = r[0].get("status") == "ok"
    switch_results.append(ok)
    print(f"     switch {i+1} → {app}: {'ok' if ok else 'FAIL — ' + r[0].get('detail','')}")
    time.sleep(0.3)
check("all 4 switches succeeded", all(switch_results), str(switch_results))

# ── 11. Type more in Excel while Word is in background ───────────────────────
print("\n[11] Type in Excel B1 while Word is in background")
r = do("excel", [
    {"action": "click",  "target": {"name": "Name Box", "control_type": "Edit"}},
    {"action": "type",   "target": {"name": "Name Box", "control_type": "Edit"}, "text": "B1"},
    {"action": "key",    "keys": "Return"},
    {"action": "wait",   "ms": 300},
    {"action": "type",   "target": {"name": "Formula Bar", "control_type": "Edit"}, "text": "42"},
    {"action": "key",    "keys": "Return"},
], "excel B1")
check("6 results returned", len(r) == 6)
check("B1 type ok", r[4].get("status") == "ok", r[4].get("detail"))

# ── 12. Verify Word content unchanged after Excel edits ──────────────────────
print("\n[12] Verify Word content unchanged after Excel edits")
r = do("word", [{"action": "read_screen"}])
word_screen2 = r[0].get("value") or ""
check("Word read_screen ok",          r[0].get("status") == "ok")
check("Word text still intact",       "Hello from FlaUI" in word_screen2, repr(word_screen2[:120]))

# ── 13. key combo in Word (ctrl+a, ctrl+c) ───────────────────────────────────
print("\n[13] Key combos in Word — ctrl+a, ctrl+End")
r = do("word", [
    {"action": "key",  "keys": "ctrl+a"},
    {"action": "wait", "ms": 200},
    {"action": "key",  "keys": "ctrl+End"},
    {"action": "wait", "ms": 200},
], "word keys")
check("4 results returned", len(r) == 4)
check("ctrl+a ok",   r[0].get("status") == "ok")
check("ctrl+End ok", r[2].get("status") == "ok")

# ── 14. Close Word without saving ────────────────────────────────────────────
print("\n[14] Close Word without saving")
r = do("word", [
    {"action": "key",      "keys": "ctrl+z"},
    {"action": "key",      "keys": "ctrl+z"},
    {"action": "close_app"},
], "close word")
time.sleep(1)
# Handle "save changes?" dialog if it appears
desktop_wins = engine.get_desktop_windows()
save_dialog = any("save" in (w.get("title") or "").lower() for w in desktop_wins)
if save_dialog:
    print("     save dialog detected — dismissing with 'n'")
    import subprocess
    subprocess.run(["powershell", "-Command",
        "[System.Windows.Forms.SendKeys]::SendWait('n')"], capture_output=True)
    time.sleep(0.5)
close_r = next((x for x in r if x.get("action") == "close_app"), {})
check("close_app ok", close_r.get("status") == "ok", close_r.get("detail"))

# ── 15. Close Excel without saving ───────────────────────────────────────────
print("\n[15] Close Excel without saving")
r = do("excel", [
    {"action": "key",      "keys": "ctrl+z"},
    {"action": "key",      "keys": "ctrl+z"},
    {"action": "close_app"},
], "close excel")
time.sleep(1)
desktop_wins = engine.get_desktop_windows()
save_dialog = any("save" in (w.get("title") or "").lower() for w in desktop_wins)
if save_dialog:
    print("     save dialog detected — dismissing with 'n'")
    import subprocess
    subprocess.run(["powershell", "-Command",
        "[System.Windows.Forms.SendKeys]::SendWait('n')"], capture_output=True)
    time.sleep(0.5)
close_r = next((x for x in r if x.get("action") == "close_app"), {})
check("close_app ok", close_r.get("status") == "ok", close_r.get("detail"))

# ── Summary ──────────────────────────────────────────────────────────────────
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"\n{'='*50}")
print(f"  {passed} passed  |  {failed} failed  |  {len(results)} total")
print(f"{'='*50}\n")
sys.exit(0 if failed == 0 else 1)
