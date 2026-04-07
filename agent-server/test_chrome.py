"""
test_chrome.py — Smoke tests for Chrome automation via flaui.py engine.

Requires Chrome to be installed. The script launches Chrome, runs through
navigation, search, tab management, and read_screen, then closes it.

Usage:
    cd agent-server
    python test_chrome.py
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

def do(actions, label=""):
    """Run a batch and print raw results."""
    r = engine.execute_batch("chrome", actions)
    if label:
        print(f"     [{label}] {json.dumps(r, ensure_ascii=False)}")
    return r

# ── 0. FlaUI availability ────────────────────────────────────────────────────
print("\n[0] FlaUI availability")
check("FlaUI DLLs loaded", _FLAUI_AVAILABLE, str(_FLAUI_ERROR) if not _FLAUI_AVAILABLE else "ok")
check("engine singleton created", engine is not None)

if not _FLAUI_AVAILABLE:
    print("\nFlaUI not available — skipping all live tests.")
    sys.exit(1)

# ── 1. Launch Chrome ─────────────────────────────────────────────────────────
print("\n[1] Launch Chrome")
result = engine.launch_app("chrome")
print(f"     raw: {result}")
check("status is launched or already_running", result.get("status") in ("launched", "already_running"))
check("window_title is non-empty", bool(result.get("window_title")))
check("window_title is actually Chrome", "chrome" in result.get("window_title", "").lower() or result.get("status") == "launched")

# Give Chrome a moment to settle
time.sleep(1.5)

# ── 2. Inspect Chrome elements ───────────────────────────────────────────────
print("\n[2] Inspect Chrome — find address bar")
elements = engine.inspect_window("chrome", depth=5)
check("inspect returns a list", isinstance(elements, list))
check("at least 1 element found", len(elements) >= 1, f"{len(elements)} elements")

addr_names = {"address and search bar", "omnibox", "address", "search"}
found_addr = any(
    any(n in (e.get("name") or "").lower() for n in addr_names)
    for e in elements
    if "error" not in e
)
check("address bar element visible in inspect", found_addr,
      "names: " + str([(e.get("name"), e.get("control_type")) for e in elements if "error" not in e and any(n in (e.get("name") or "").lower() for n in addr_names)][:4]))

# ── 3. Navigate to google.com ────────────────────────────────────────────────
print("\n[3] Navigate to google.com")
r = do([
    {"action": "key",  "keys": "ctrl+l"},
    {"action": "wait", "ms": 300},
    {"action": "type", "target": {"name": "Address and search bar", "control_type": "Edit"}, "text": "https://www.google.com"},
    {"action": "key",  "keys": "Return"},
    {"action": "wait", "ms": 2500},
], "navigate")
check("all 5 actions returned", len(r) == 5)
check("ctrl+l ok",   r[0].get("status") == "ok", r[0].get("detail"))
check("type ok",     r[2].get("status") == "ok", r[2].get("detail"))
check("Return ok",   r[3].get("status") == "ok", r[3].get("detail"))

# ── 4. read_screen after navigation ─────────────────────────────────────────
print("\n[4] read_screen — Google homepage")
rs = do([{"action": "read_screen"}], "read_screen")
check("read_screen ok",            rs[0].get("status") == "ok")
check("read_screen value is str",  isinstance(rs[0].get("value"), str))
screen_text = rs[0].get("value") or ""
check("screen contains 'Google'",  "google" in screen_text.lower(), repr(screen_text[:120]))

# ── 5. Search on Google ──────────────────────────────────────────────────────
print("\n[5] Search Google for 'FlaUI windows automation'")
r = do([
    {"action": "key",  "keys": "ctrl+l"},
    {"action": "wait", "ms": 300},
    {"action": "type", "target": {"name": "Address and search bar", "control_type": "Edit"}, "text": "FlaUI windows automation"},
    {"action": "key",  "keys": "Return"},
    {"action": "wait", "ms": 2500},
    {"action": "read_screen"},
], "search")
check("all 6 actions returned", len(r) == 6)
check("type ok",        r[2].get("status") == "ok", r[2].get("detail"))
check("read_screen ok", r[5].get("status") == "ok")
search_text = r[5].get("value") or ""
check("results page has content", len(search_text) > 50, f"{len(search_text)} chars")

# ── 6. Navigate to YouTube ───────────────────────────────────────────────────
print("\n[6] Navigate to YouTube")
r = do([
    {"action": "key",  "keys": "ctrl+l"},
    {"action": "wait", "ms": 300},
    {"action": "type", "target": {"name": "Address and search bar", "control_type": "Edit"}, "text": "https://www.youtube.com"},
    {"action": "key",  "keys": "Return"},
    {"action": "wait", "ms": 3000},
    {"action": "read_screen"},
], "youtube")
check("all 6 actions returned", len(r) == 6)
check("read_screen ok", r[5].get("status") == "ok")
yt_text = r[5].get("value") or ""
check("YouTube page has content", len(yt_text) > 20, f"{len(yt_text)} chars")

# ── 7. Open a new tab ────────────────────────────────────────────────────────
print("\n[7] Open new tab (ctrl+t)")
r = do([
    {"action": "key",  "keys": "ctrl+t"},
    {"action": "wait", "ms": 800},
    {"action": "read_screen"},
], "new tab")
check("all 3 actions returned", len(r) == 3)
check("ctrl+t ok",      r[0].get("status") == "ok")
check("read_screen ok", r[2].get("status") == "ok")

# ── 8. Type in address bar of new tab ────────────────────────────────────────
print("\n[8] Type URL in new tab")
r = do([
    {"action": "type", "target": {"name": "Address and search bar", "control_type": "Edit"}, "text": "https://www.bing.com"},
    {"action": "key",  "keys": "Return"},
    {"action": "wait", "ms": 2000},
    {"action": "read_screen"},
], "bing")
check("all 4 actions returned", len(r) == 4)
check("type ok",        r[0].get("status") == "ok", r[0].get("detail"))
check("read_screen ok", r[3].get("status") == "ok")

# ── 9. Switch back to previous tab ───────────────────────────────────────────
print("\n[9] Switch to previous tab (ctrl+shift+tab)")
r = do([
    {"action": "key",  "keys": "ctrl+shift+tab"},
    {"action": "wait", "ms": 500},
    {"action": "read_screen"},
], "switch tab")
check("all 3 actions returned", len(r) == 3)
check("key ok",         r[0].get("status") == "ok")
check("read_screen ok", r[2].get("status") == "ok")

# ── 10. Close the extra tab ──────────────────────────────────────────────────
print("\n[10] Close extra tab (ctrl+w)")
r = do([
    {"action": "key",  "keys": "ctrl+Tab"},   # go to the bing tab
    {"action": "wait", "ms": 400},
    {"action": "key",  "keys": "ctrl+w"},     # close it
    {"action": "wait", "ms": 500},
], "close tab")
check("all 4 actions returned", len(r) == 4)
check("ctrl+w ok", r[2].get("status") == "ok")

# ── 11. Back / Forward navigation ────────────────────────────────────────────
print("\n[11] Back / Forward navigation")
r = do([
    {"action": "key",  "keys": "alt+left"},   # back
    {"action": "wait", "ms": 1500},
    {"action": "key",  "keys": "alt+right"},  # forward
    {"action": "wait", "ms": 1500},
], "back/forward")
check("all 4 actions returned", len(r) == 4)
check("back ok",    r[0].get("status") == "ok")
check("forward ok", r[2].get("status") == "ok")

# ── 12. Screenshot ───────────────────────────────────────────────────────────
print("\n[12] Screenshot")
r = do([{"action": "screenshot"}], "screenshot")
check("screenshot ok",          r[0].get("status") == "ok", r[0].get("detail"))
check("screenshot returns path", bool(r[0].get("value")),   r[0].get("value"))

# ── 13. Close Chrome ─────────────────────────────────────────────────────────
print("\n[13] Close Chrome")
r = do([{"action": "close_app"}], "close")
check("close_app ok", r[0].get("status") == "ok", r[0].get("detail"))

# ── Summary ──────────────────────────────────────────────────────────────────
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
print(f"\n{'='*50}")
print(f"  {passed} passed  |  {failed} failed  |  {len(results)} total")
print(f"{'='*50}\n")
sys.exit(0 if failed == 0 else 1)
