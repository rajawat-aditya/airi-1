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
    import flaui as flaui_module
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
print("\n[7] execute_batch — type text into Notepad")
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
    {"action": "key", "keys": "ctrl+z"},
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


# ── Unit tests (mock-based, no live FlaUI/Windows required) ──────────────────

import unittest
import ctypes
from unittest.mock import MagicMock, patch, call

# Shared helper: patch all external side-effects of execute_batch so unit tests
# run fast and headless.
def _batch_patches(mock_window, mock_execute_side_effect=None, mock_execute_return=None):
    """Return a list of context managers that suppress overlay, lock, and executor."""
    patches = [
        patch.object(engine._resolver, "resolve", return_value=mock_window),
        patch.object(flaui_module._overlay, "show"),
        patch.object(flaui_module._overlay, "hide"),
        patch("ctypes.windll.user32.LockSetForegroundWindow"),
    ]
    if mock_execute_side_effect is not None:
        patches.append(patch.object(engine._executor, "execute",
                                    side_effect=mock_execute_side_effect))
    elif mock_execute_return is not None:
        patches.append(patch.object(engine._executor, "execute",
                                    return_value=mock_execute_return))
    return patches


class _MultiPatch:
    """Simple context manager that enters/exits a list of patches."""
    def __init__(self, patches):
        self._patches = patches
        self._mocks = []

    def __enter__(self):
        self._mocks = [p.__enter__() for p in self._patches]
        return self._mocks

    def __exit__(self, *args):
        for p in reversed(self._patches):
            p.__exit__(*args)


# ── Bug condition exploration tests ──────────────────────────────────────────

class TestExecuteBatchFocusBugCondition(unittest.TestCase):
    """Task 1.1 — SetForeground must be called before any action."""

    def test_set_foreground_called_before_actions(self):
        mock_window = MagicMock(spec=False)
        call_order = []
        mock_window.Patterns.Window.Pattern.SetForeground.side_effect = (
            lambda: call_order.append("set_foreground")
        )
        dummy_result = {"action": "wait", "target": None, "status": "ok", "detail": "ok", "value": None}

        with _MultiPatch(_batch_patches(
            mock_window,
            mock_execute_side_effect=lambda *a, **kw: call_order.append("execute") or dummy_result,
        )):
            results = engine.execute_batch("notepad", [{"action": "wait", "ms": 0}])

        mock_window.Patterns.Window.Pattern.SetForeground.assert_called_once()
        self.assertIn("set_foreground", call_order)
        self.assertIn("execute", call_order)
        self.assertLess(call_order.index("set_foreground"), call_order.index("execute"),
                        "SetForeground must be called BEFORE the first action")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "ok")


class TestExecuteBatchResolveNone(unittest.TestCase):
    """Task 1.2 — When resolve() returns None, no focus/overlay and all results are errors."""

    def test_no_focus_and_error_results_when_resolve_returns_none(self):
        with patch.object(engine._resolver, "resolve", return_value=None), \
             patch.object(flaui_module._overlay, "show") as mock_show, \
             patch.object(flaui_module._overlay, "hide") as mock_hide, \
             patch("ctypes.windll.user32.LockSetForegroundWindow"), \
             patch.object(engine._executor, "execute") as mock_execute:

            results = engine.execute_batch("notepad", [
                {"action": "click", "target": {"name": "OK"}},
                {"action": "type",  "target": {"name": "input"}, "text": "hello"},
            ])

        mock_execute.assert_not_called()
        mock_show.assert_not_called()   # overlay must not show when window not found
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r["status"], "error")


# ── Fix-checking tests (Property 1) ──────────────────────────────────────────

class TestFixCheckingProperty1(unittest.TestCase):
    """Tasks 3.1 & 3.2 — SetForeground called before actions; exceptions don't abort."""

    def test_set_foreground_called_before_first_action(self):
        mock_window = MagicMock(spec=False)
        call_order = []
        mock_window.Patterns.Window.Pattern.SetForeground.side_effect = (
            lambda: call_order.append("set_foreground")
        )
        dummy_result = {"action": "wait", "target": None, "status": "ok", "detail": "ok", "value": None}

        with _MultiPatch(_batch_patches(
            mock_window,
            mock_execute_side_effect=lambda *a, **kw: call_order.append("execute") or dummy_result,
        )):
            results = engine.execute_batch("notepad", [{"action": "wait", "ms": 0}])

        mock_window.Patterns.Window.Pattern.SetForeground.assert_called_once()
        self.assertLess(call_order.index("set_foreground"), call_order.index("execute"))
        self.assertEqual(results[0]["status"], "ok")

    def test_set_foreground_exception_does_not_abort_batch(self):
        mock_window = MagicMock(spec=False)
        mock_window.Patterns.Window.Pattern.SetForeground.side_effect = RuntimeError("focus denied")
        dummy_result = {"action": "wait", "target": None, "status": "ok", "detail": "ok", "value": None}

        with _MultiPatch(_batch_patches(mock_window, mock_execute_return=dummy_result)):
            results = engine.execute_batch("notepad", [{"action": "wait", "ms": 0}] * 2)

        self.assertEqual(len(results), 2)
        for r in results:
            self.assertEqual(r["status"], "ok")


# ── Preservation tests (Property 2) ──────────────────────────────────────────

class TestPreservationProperty2(unittest.TestCase):
    """Tasks 4.1–4.3 — Existing batch behaviors unchanged by focus/overlay additions."""

    def test_resolve_none_returns_error_results(self):
        with patch.object(engine._resolver, "resolve", return_value=None), \
             patch.object(flaui_module._overlay, "show"), \
             patch.object(flaui_module._overlay, "hide"), \
             patch("ctypes.windll.user32.LockSetForegroundWindow"), \
             patch.object(engine._executor, "execute") as mock_execute:
            results = engine.execute_batch("notepad", [
                {"action": "click", "target": {"name": "OK"}},
                {"action": "type",  "target": {"name": "input"}, "text": "hello"},
            ])
        mock_execute.assert_not_called()
        self.assertTrue(all(r["status"] == "error" for r in results))

    def test_close_app_skip_logic_preserved(self):
        mock_window = MagicMock(spec=False)
        close_r = {"action": "close_app", "target": None, "status": "ok", "detail": "closed", "value": None}
        ok_r    = {"action": "wait",      "target": None, "status": "ok", "detail": "ok",     "value": None}

        with _MultiPatch(_batch_patches(
            mock_window,
            mock_execute_side_effect=[close_r, ok_r, ok_r],
        )):
            results = engine.execute_batch("notepad", [
                {"action": "close_app"},
                {"action": "wait",  "ms": 100},
                {"action": "click", "target": {"name": "OK"}},
            ])

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["status"], "ok")
        self.assertEqual(results[1]["status"], "skipped")
        self.assertEqual(results[2]["status"], "skipped")

    def test_per_action_error_continuation(self):
        mock_window = MagicMock(spec=False)
        err_r = {"action": "click", "target": None, "status": "error", "detail": "failed", "value": None}
        ok_r  = {"action": "wait",  "target": None, "status": "ok",    "detail": "ok",     "value": None}

        with _MultiPatch(_batch_patches(
            mock_window,
            mock_execute_side_effect=[err_r, ok_r],
        )):
            results = engine.execute_batch("notepad", [
                {"action": "click", "target": {"name": "OK"}},
                {"action": "wait",  "ms": 0},
            ])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "error")
        self.assertEqual(results[1]["status"], "ok")


# ── LockSetForegroundWindow tests ─────────────────────────────────────────────

class TestLockSetForegroundWindow(unittest.TestCase):
    """Lock(1) before actions, Unlock(2) after — in both success and exception paths."""

    def test_lock_before_actions_unlock_after(self):
        mock_window = MagicMock(spec=False)
        call_order = []
        dummy_result = {"action": "wait", "target": None, "status": "ok", "detail": "ok", "value": None}

        with patch.object(engine._resolver, "resolve", return_value=mock_window), \
             patch.object(flaui_module._overlay, "show"), \
             patch.object(flaui_module._overlay, "hide"), \
             patch("ctypes.windll.user32.LockSetForegroundWindow",
                   side_effect=lambda f: call_order.append(f"lock_{f}")), \
             patch.object(engine._executor, "execute",
                          side_effect=lambda *a, **kw: call_order.append("execute") or dummy_result):
            engine.execute_batch("notepad", [{"action": "wait", "ms": 0}])

        self.assertIn("lock_1", call_order)
        self.assertIn("lock_2", call_order)
        self.assertLess(call_order.index("lock_1"), call_order.index("execute"))
        self.assertGreater(call_order.index("lock_2"), call_order.index("execute"))

    def test_unlock_called_on_exception(self):
        mock_window = MagicMock(spec=False)
        lock_calls = []

        with patch.object(engine._resolver, "resolve", return_value=mock_window), \
             patch.object(flaui_module._overlay, "show"), \
             patch.object(flaui_module._overlay, "hide"), \
             patch("ctypes.windll.user32.LockSetForegroundWindow",
                   side_effect=lambda f: lock_calls.append(f)), \
             patch.object(engine._finder, "find", side_effect=RuntimeError("boom")):
            engine.execute_batch("notepad", [{"action": "click", "target": {"name": "x"}}])

        self.assertIn(2, lock_calls)

    def test_lock_exception_does_not_abort_batch(self):
        mock_window = MagicMock(spec=False)
        dummy_result = {"action": "wait", "target": None, "status": "ok", "detail": "ok", "value": None}

        with patch.object(engine._resolver, "resolve", return_value=mock_window), \
             patch.object(flaui_module._overlay, "show"), \
             patch.object(flaui_module._overlay, "hide"), \
             patch("ctypes.windll.user32.LockSetForegroundWindow", side_effect=OSError("no windll")), \
             patch.object(engine._executor, "execute", return_value=dummy_result):
            results = engine.execute_batch("notepad", [{"action": "wait", "ms": 0}])

        self.assertEqual(results[0]["status"], "ok")


# ── Overlay tests ─────────────────────────────────────────────────────────────

class TestInputOverlay(unittest.TestCase):
    """Overlay show/hide called around the action loop; overlay hides on exception."""

    def test_overlay_shown_before_actions_hidden_after(self):
        mock_window = MagicMock(spec=False)
        call_order = []
        dummy_result = {"action": "wait", "target": None, "status": "ok", "detail": "ok", "value": None}

        with patch.object(engine._resolver, "resolve", return_value=mock_window), \
             patch.object(flaui_module._overlay, "show",
                          side_effect=lambda: call_order.append("show")), \
             patch.object(flaui_module._overlay, "hide",
                          side_effect=lambda: call_order.append("hide")), \
             patch("ctypes.windll.user32.LockSetForegroundWindow"), \
             patch.object(engine._executor, "execute",
                          side_effect=lambda *a, **kw: call_order.append("execute") or dummy_result):
            engine.execute_batch("notepad", [{"action": "wait", "ms": 0}])

        self.assertIn("show", call_order)
        self.assertIn("hide", call_order)
        self.assertIn("execute", call_order)
        self.assertLess(call_order.index("show"), call_order.index("execute"),
                        "Overlay must show before actions run")
        self.assertGreater(call_order.index("hide"), call_order.index("execute"),
                           "Overlay must hide after actions complete")

    def test_overlay_hidden_on_exception(self):
        mock_window = MagicMock(spec=False)
        hide_called = []

        with patch.object(engine._resolver, "resolve", return_value=mock_window), \
             patch.object(flaui_module._overlay, "show"), \
             patch.object(flaui_module._overlay, "hide",
                          side_effect=lambda: hide_called.append(True)), \
             patch("ctypes.windll.user32.LockSetForegroundWindow"), \
             patch.object(engine._finder, "find", side_effect=RuntimeError("boom")):
            engine.execute_batch("notepad", [{"action": "click", "target": {"name": "x"}}])

        self.assertTrue(hide_called, "Overlay hide must be called even when an exception occurs")

    def test_overlay_not_shown_when_window_not_found(self):
        with patch.object(engine._resolver, "resolve", return_value=None), \
             patch.object(flaui_module._overlay, "show") as mock_show, \
             patch.object(flaui_module._overlay, "hide"), \
             patch("ctypes.windll.user32.LockSetForegroundWindow"):
            engine.execute_batch("notepad", [{"action": "wait", "ms": 0}])

        mock_show.assert_not_called()


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestExecuteBatchFocusBugCondition,
        TestExecuteBatchResolveNone,
        TestFixCheckingProperty1,
        TestPreservationProperty2,
        TestLockSetForegroundWindow,
        TestInputOverlay,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
