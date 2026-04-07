"""
test_flaui.py — Manual smoke tests for the flaui.py automation engine.
Runs against Notepad (always available on Windows).

Usage:
    cd agent-server
    python test_flaui.py
"""

import sys
import json

# ── import engine ────────────────────────────────────────────────────────────
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

# ── 1. FlaUI availability ────────────────────────────────────────────────────
print("\n[1] FlaUI availability")
check("FlaUI DLLs loaded", _FLAUI_AVAILABLE, str(_FLAUI_ERROR) if not _FLAUI_AVAILABLE else "ok")
check("engine singleton created", engine is not None)

if not _FLAUI_AVAILABLE:
    print("\nFlaUI not available — skipping all live tests.")
    sys.exit(1)

# ── 2. get_desktop_windows ───────────────────────────────────────────────────
print("\n[2] get_desktop_windows")
windows = engine.get_desktop_windows()
check("returns a list", isinstance(windows, list))
check("list is non-empty", len(windows) > 0, f"{len(windows)} windows")
if windows:
    w = windows[0]
    check("each entry has 'title'", "title" in w)
    check("each entry has 'process_name'", "process_name" in w)

# ── 3. launch_app (Notepad) ──────────────────────────────────────────────────
print("\n[3] launch_app — Notepad")
result = engine.launch_app("notepad")
print(f"     raw: {result}")
check("status is launched or already_running", result.get("status") in ("launched", "already_running"))
check("window_title is non-empty", bool(result.get("window_title")))

# ── 4. launch_app — already running ─────────────────────────────────────────
print("\n[4] launch_app — already_running detection")
result2 = engine.launch_app("notepad")
check("second launch returns already_running", result2.get("status") == "already_running")

# ── 5. inspect_window ────────────────────────────────────────────────────────
print("\n[5] inspect_window — Notepad")
elements = engine.inspect_window("notepad")
check("returns a list", isinstance(elements, list))
check("no error key", "error" not in (elements[0] if elements else {}))
check("at least 1 element", len(elements) >= 1, f"{len(elements)} elements")
has_edit = any(e.get("control_type", "").lower() in ("edit", "document") for e in elements)
check("contains Edit or Document element", has_edit)
# verify shape of first element
if elements and "error" not in elements[0]:
    e0 = elements[0]
    check("element has 'name'", "name" in e0)
    check("element has 'control_type'", "control_type" in e0)
    check("element has 'rect'", "rect" in e0)
    check("element has 'depth'", "depth" in e0)

# ── 6. inspect_window with filter_types ──────────────────────────────────────
print("\n[6] inspect_window — filter_types=Edit,Document")
filtered = engine.inspect_window("notepad", filter_types="Edit,Document")
check("filtered list is a list", isinstance(filtered, list))
if filtered and "error" not in filtered[0]:
    all_text = all(e.get("control_type", "").lower() in ("edit", "document") for e in filtered)
    check("all returned elements are Edit or Document type", all_text, f"{len(filtered)} elements")

# ── 7. execute_batch — type + read ───────────────────────────────────────────
# Win11 Notepad uses Document; classic Notepad uses Edit. Try Document first.
print("\n[7] execute_batch — type text into Notepad")
# Detect which control type the text area is
_elements = engine.inspect_window("notepad", filter_types="Edit,Document")
_text_ct = "Document" if any(e.get("control_type","").lower() == "document" for e in _elements) else "Edit"
print(f"     detected text area control_type: {_text_ct}")
batch = [
    {"action": "key",  "keys": "ctrl+a"},
    {"action": "key",  "keys": "delete"},
    {"action": "type", "target": {"control_type": _text_ct, "index": 0}, "text": "Hello FlaUI"},
    {"action": "read", "target": {"control_type": _text_ct, "index": 0}},
]
batch_results = engine.execute_batch("notepad", batch)
print(f"     raw: {json.dumps(batch_results, indent=2)}")
check("result count matches action count", len(batch_results) == len(batch), f"{len(batch_results)}/{len(batch)}")
type_result = batch_results[2] if len(batch_results) > 2 else {}
read_result = batch_results[3] if len(batch_results) > 3 else {}
check("type action ok", type_result.get("status") == "ok", type_result.get("detail", ""))
check("read action ok", read_result.get("status") == "ok", read_result.get("detail", ""))
check("read value contains typed text", "Hello FlaUI" in (read_result.get("value") or ""), repr(read_result.get("value")))

# ── 8. execute_batch — read_screen ───────────────────────────────────────────
print("\n[8] execute_batch — read_screen")
rs_results = engine.execute_batch("notepad", [{"action": "read_screen"}])
check("read_screen ok", rs_results[0].get("status") == "ok")
check("read_screen value is a string", isinstance(rs_results[0].get("value"), str))
check("read_screen value non-empty", bool(rs_results[0].get("value", "").strip()))

# ── 9. execute_batch — wait ───────────────────────────────────────────────────
print("\n[9] execute_batch — wait")
import time
t0 = time.time()
wait_results = engine.execute_batch("notepad", [{"action": "wait", "ms": 500}])
elapsed = time.time() - t0
check("wait ok", wait_results[0].get("status") == "ok")
check("wait took ~500ms", 0.4 <= elapsed <= 1.5, f"{elapsed:.2f}s")

# ── 10. execute_batch — window not found ─────────────────────────────────────
print("\n[10] execute_batch — window not found")
nf_results = engine.execute_batch("__nonexistent_app_xyz__", [{"action": "read_screen"}])
check("returns list", isinstance(nf_results, list))
check("status is error", nf_results[0].get("status") == "error")
check("detail mentions window not found", "not found" in nf_results[0].get("detail", "").lower())

# ── 11. execute_batch — element not found (continues batch) ──────────────────
print("\n[11] execute_batch — element not found continues batch")
mixed = [
    {"action": "click",  "target": {"name": "__no_such_element__"}},
    {"action": "wait",   "ms": 100},
]
mixed_results = engine.execute_batch("notepad", mixed)
check("both results returned", len(mixed_results) == 2)
check("first action is error", mixed_results[0].get("status") == "error")
check("second action still ran", mixed_results[1].get("status") == "ok")

# ── 12. close_app ─────────────────────────────────────────────────────────────
print("\n[12] execute_batch — close_app")
close_results = engine.execute_batch("notepad", [
    {"action": "key", "keys": "ctrl+z"},   # undo any edits so no save dialog
    {"action": "key", "keys": "ctrl+z"},
    {"action": "close_app"},
])
close_r = next((r for r in close_results if r.get("action") == "close_app"), {})
check("close_app ok", close_r.get("status") == "ok", close_r.get("detail", ""))

# ── summary ───────────────────────────────────────────────────────────────────
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"\n{'='*50}")
print(f"  {passed} passed  |  {failed} failed  |  {len(results)} total")
print(f"{'='*50}\n")
sys.exit(0 if failed == 0 else 1)
