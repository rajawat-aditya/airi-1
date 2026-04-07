"""
flaui.py — Windows UI automation engine built on FlaUI/UIA3.

Exports: WindowsAutomationEngine, AppResolver, ElementFinder, ActionExecutor
Module-level singletons: _automation (UIA3Automation), engine (WindowsAutomationEngine)
"""

import os
import sys
import shlex
import difflib
import pathlib
import subprocess
import time
import tempfile
import psutil

try:
    import PIL.ImageGrab
    _PIL_AVAILABLE = True
except Exception:
    _PIL_AVAILABLE = False

# ---------------------------------------------------------------------------
# DLL loading — must happen before any FlaUI namespace imports
# ---------------------------------------------------------------------------

_FLAUI_AVAILABLE = False
_FLAUI_ERROR = None

_deps_dir = str(pathlib.Path(__file__).parent.parent / "deps" / "flaui")

try:
    # Add the deps dir to sys.path so CLR can locate the assemblies
    if _deps_dir not in sys.path:
        sys.path.insert(0, _deps_dir)

    import clr  # pythonnet

    clr.AddReference("FlaUI.Core")
    clr.AddReference("Interop.UIAutomationClient")
    clr.AddReference("FlaUI.UIA3")

    # FlaUI namespace imports
    from FlaUI.UIA3 import UIA3Automation                          # noqa: E402
    from FlaUI.Core.AutomationElements import AutomationElement    # noqa: E402
    from FlaUI.Core.Definitions import ControlType                 # noqa: E402
    from FlaUI.Core.Conditions import ConditionFactory             # noqa: E402
    from FlaUI.Core.Input import Keyboard, Mouse                   # noqa: E402
    from FlaUI.UIA3 import UIA3PropertyLibrary                     # noqa: E402
    from FlaUI.Core.WindowsAPI import VirtualKeyShort              # noqa: E402

    _FLAUI_AVAILABLE = True

except Exception as exc:
    _FLAUI_ERROR = exc
    print(
        f"[flaui] WARNING: FlaUI not available — {exc}\n"
        "  Automation features will be disabled. "
        "This is expected on non-Windows systems or when deps/flaui/ is missing."
    )

# ---------------------------------------------------------------------------
# Module-level UIA3Automation singleton
# Created once; never disposed during the process lifetime.
# ---------------------------------------------------------------------------

_automation = None

if _FLAUI_AVAILABLE:
    try:
        _automation = UIA3Automation()
    except Exception as exc:
        _FLAUI_AVAILABLE = False
        _FLAUI_ERROR = exc
        print(f"[flaui] WARNING: Failed to create UIA3Automation singleton — {exc}")


# ---------------------------------------------------------------------------
# Stub classes (bodies filled in by subsequent tasks)
# ---------------------------------------------------------------------------

def _first_existing(paths: list) -> str:
    """Return the first path in the list that exists on disk, or the last as fallback."""
    for p in paths:
        if p and os.path.exists(p):
            return p
    return paths[-1] if paths else ""


class AppResolver:
    """Resolves a human-readable app name to a live FlaUI Window element."""

    # Fallback registry used only when installed_apps.json is missing or incomplete.
    _BUILTIN_FALLBACK = {
        "explorer":  {"exe": "explorer.exe",       "title_hint": ""},
        "cmd":       {"exe": "cmd.exe",             "title_hint": ""},
        "notepad":   {"exe": "notepad.exe",         "title_hint": "Notepad"},
        "settings":  {"exe": "SystemSettings.exe",  "title_hint": "Settings"},
        # Office — common install paths; first existing path wins
        "word":      {"exe": _first_existing([
                          r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
                          r"C:\Program Files (x86)\Microsoft Office\root\Office16\WINWORD.EXE",
                          r"C:\Program Files\Microsoft Office 15\root\Office15\WINWORD.EXE",
                      ]), "title_hint": "Word"},
        "excel":     {"exe": _first_existing([
                          r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
                          r"C:\Program Files (x86)\Microsoft Office\root\Office16\EXCEL.EXE",
                          r"C:\Program Files\Microsoft Office 15\root\Office15\EXCEL.EXE",
                      ]), "title_hint": "Excel"},
        "chrome":    {"exe": _first_existing([
                          r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                          r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                      ]), "title_hint": "Chrome"},
    }

    # Loaded once at class level from installed_apps.json
    KNOWN_APPS: dict = {}

    @classmethod
    def _load_installed_apps(cls):
        """Load installed_apps.json produced by Electron at startup.

        File format (array):
            [{"name": "Google Chrome", "exe": "C:\\...\\chrome.exe", "title_hint": "Chrome"}, ...]

        Builds KNOWN_APPS keyed by lowercase name and by lowercase exe stem so
        both "chrome" and "google chrome" resolve correctly.
        """
        json_path = pathlib.Path(__file__).parent / "installed_apps.json"
        loaded = {}
        if json_path.exists():
            try:
                import json as _json
                # utf-8-sig handles BOM written by PowerShell Out-File
                entries = _json.loads(json_path.read_text(encoding="utf-8-sig"))
                for entry in entries:
                    name = (entry.get("name") or "").strip()
                    exe  = (entry.get("exe")  or "").strip()
                    hint = (entry.get("title_hint") or "").strip()
                    if not name or not exe:
                        continue
                    record = {"exe": exe, "title_hint": hint}
                    # Key by full lowercase name
                    loaded[name.lower()] = record
                    # Also key by exe stem (e.g. "chrome" from "chrome.exe")
                    stem = pathlib.Path(exe).stem.lower()
                    if stem and stem not in loaded:
                        loaded[stem] = record
                print(f"[flaui] Loaded {len(entries)} apps from installed_apps.json → {len(loaded)} keys")
            except Exception as exc:
                print(f"[flaui] WARNING: Could not load installed_apps.json — {exc}")

        # Merge builtins for anything not covered
        for k, v in cls._BUILTIN_FALLBACK.items():
            if k not in loaded:
                loaded[k] = v

        cls.KNOWN_APPS = loaded

    def __init__(self, automation=None):
        self._automation = automation if automation is not None else _automation

    def _get_desktop_children(self):
        """Returns desktop.FindAllChildren() safely, or [] on error."""
        try:
            desktop = self._automation.GetDesktop()
            return desktop.FindAllChildren()
        except Exception:
            return []

    def resolve(self, app: str):
        """
        Resolve a human-readable app name to a live FlaUI Window element.
        Tries 4 strategies in order; returns None if all fail.
        """
        try:
            if not self._automation:
                return None

            desktop = self._automation.GetDesktop()
            cf = ConditionFactory(UIA3PropertyLibrary())
            app_lower = app.lower()
            known = self.KNOWN_APPS.get(app_lower, {})

            # Strategy 1: exact window title match (top-level children only)
            win = desktop.FindFirstChild(cf.ByName(app))
            if win is not None:
                return win

            # Strategy 2: title contains title_hint (known apps) or app name (unknown apps).
            # Use word-boundary matching to avoid false positives like "test_chrome.py"
            # matching "chrome".
            children = self._get_desktop_children()
            title_hint = known.get("title_hint", "")
            import re as _re
            for child in children:
                try:
                    child_name = child.Name or ""
                    child_name_lower = child_name.lower()
                    if title_hint:
                        # Known app: match on title_hint with word boundary
                        if _re.search(r'\b' + _re.escape(title_hint.lower()) + r'\b', child_name_lower):
                            return child
                    else:
                        # Unknown app or no hint: word-boundary match on app name
                        if _re.search(r'\b' + _re.escape(app_lower) + r'\b', child_name_lower):
                            return child
                except Exception:
                    continue

            # Strategy 3: process name match via psutil
            exe = known.get("exe") or (app + ".exe")
            for proc in psutil.process_iter(["name", "pid"]):
                try:
                    if (proc.info["name"] or "").lower() == exe.lower():
                        pid = proc.info["pid"]
                        for child in children:
                            try:
                                if child.Properties.ProcessId.Value == pid:
                                    return child
                            except Exception:
                                continue
                except Exception:
                    continue

            # Strategy 4: fuzzy title match
            best_ratio = 0.0
            best_win = None
            for child in children:
                try:
                    child_name = child.Name or ""
                    ratio = difflib.SequenceMatcher(
                        None, app_lower, child_name.lower()
                    ).ratio()
                    if ratio > 0.6 and ratio > best_ratio:
                        best_ratio = ratio
                        best_win = child
                except Exception:
                    continue
            if best_win is not None:
                return best_win

            return None

        except Exception:
            return None


# Load installed apps from JSON at import time (populated by Electron on startup)
AppResolver._load_installed_apps()


class ElementFinder:
    """Finds a UI element inside a window using a target descriptor dict."""

    def __init__(self):
        pass

    def find(self, root, target: dict):
        """
        Find a UI element inside root using the target descriptor.
        Tries 5 strategies in priority order; returns None if all fail.
        Never raises.
        """
        try:
            if not target:
                return None

            cf = ConditionFactory(UIA3PropertyLibrary())

            # Strategy 1: automation_id
            if target.get("automation_id"):
                el = root.FindFirstDescendant(cf.ByAutomationId(target["automation_id"]))
                if el is not None:
                    return el

            # Strategy 2: exact name match
            if target.get("name"):
                el = root.FindFirstDescendant(cf.ByName(target["name"]))
                if el is not None:
                    return el

            # Strategy 3: name contains (case-insensitive)
            if target.get("name"):
                needle = target["name"].lower()
                try:
                    all_els = root.FindAllDescendants()
                    for el in all_els:
                        try:
                            if needle in (el.Name or "").lower():
                                return el
                        except Exception:
                            continue
                except Exception:
                    pass

            # Strategy 4: control_type + index
            if target.get("control_type"):
                try:
                    ct = getattr(ControlType, target["control_type"], None)
                    if ct is not None:
                        matches = root.FindAllDescendants(cf.ByControlType(ct))
                        idx = target.get("index", 0)
                        if matches and idx < len(matches):
                            return matches[idx]
                except Exception:
                    pass

            # Strategy 5: text_contains — scan Edit and Document elements
            if target.get("text_contains"):
                needle = target["text_contains"]
                try:
                    candidates = []
                    try:
                        candidates += list(root.FindAllDescendants(cf.ByControlType(ControlType.Edit)))
                    except Exception:
                        pass
                    try:
                        candidates += list(root.FindAllDescendants(cf.ByControlType(ControlType.Document)))
                    except Exception:
                        pass
                    for el in candidates:
                        try:
                            try:
                                val = el.AsTextBox().Text
                            except Exception:
                                try:
                                    val = el.Patterns.Value.Pattern.Value
                                except Exception:
                                    val = el.Name or ""
                            if needle in (val or ""):
                                return el
                        except Exception:
                            continue
                except Exception:
                    pass

            return None

        except Exception:
            return None


class ActionExecutor:
    """Executes a single action dict against a resolved element or window."""

    # Map key name strings to VirtualKeyShort enum values (populated lazily)
    _KEY_MAP = None

    @classmethod
    def _get_key_map(cls):
        if cls._KEY_MAP is not None:
            return cls._KEY_MAP
        if not _FLAUI_AVAILABLE:
            cls._KEY_MAP = {}
            return cls._KEY_MAP
        cls._KEY_MAP = {
            "ctrl":      VirtualKeyShort.CONTROL,
            "control":   VirtualKeyShort.CONTROL,
            "alt":       VirtualKeyShort.ALT,
            "shift":     VirtualKeyShort.SHIFT,
            "win":       VirtualKeyShort.LWIN,
            "lwin":      VirtualKeyShort.LWIN,
            "enter":     VirtualKeyShort.RETURN,
            "return":    VirtualKeyShort.RETURN,
            "tab":       VirtualKeyShort.TAB,
            "esc":       VirtualKeyShort.ESCAPE,
            "escape":    VirtualKeyShort.ESCAPE,
            "delete":    VirtualKeyShort.DELETE,
            "del":       VirtualKeyShort.DELETE,
            "backspace": VirtualKeyShort.BACK,
            "back":      VirtualKeyShort.BACK,
            "space":     VirtualKeyShort.SPACE,
            "home":      VirtualKeyShort.HOME,
            "end":       VirtualKeyShort.END,
            "pageup":    VirtualKeyShort.PRIOR,
            "pagedown":  VirtualKeyShort.NEXT,
            "up":        VirtualKeyShort.UP,
            "down":      VirtualKeyShort.DOWN,
            "left":      VirtualKeyShort.LEFT,
            "right":     VirtualKeyShort.RIGHT,
            "f1":        VirtualKeyShort.F1,
            "f2":        VirtualKeyShort.F2,
            "f3":        VirtualKeyShort.F3,
            "f4":        VirtualKeyShort.F4,
            "f5":        VirtualKeyShort.F5,
            "f6":        VirtualKeyShort.F6,
            "f7":        VirtualKeyShort.F7,
            "f8":        VirtualKeyShort.F8,
            "f9":        VirtualKeyShort.F9,
            "f10":       VirtualKeyShort.F10,
            "f11":       VirtualKeyShort.F11,
            "f12":       VirtualKeyShort.F12,
            # Letter keys (A-Z) mapped to VirtualKeyShort for use in combos
            "a": VirtualKeyShort.KEY_A, "b": VirtualKeyShort.KEY_B,
            "c": VirtualKeyShort.KEY_C, "d": VirtualKeyShort.KEY_D,
            "e": VirtualKeyShort.KEY_E, "f": VirtualKeyShort.KEY_F,
            "g": VirtualKeyShort.KEY_G, "h": VirtualKeyShort.KEY_H,
            "i": VirtualKeyShort.KEY_I, "j": VirtualKeyShort.KEY_J,
            "k": VirtualKeyShort.KEY_K, "l": VirtualKeyShort.KEY_L,
            "m": VirtualKeyShort.KEY_M, "n": VirtualKeyShort.KEY_N,
            "o": VirtualKeyShort.KEY_O, "p": VirtualKeyShort.KEY_P,
            "q": VirtualKeyShort.KEY_Q, "r": VirtualKeyShort.KEY_R,
            "s": VirtualKeyShort.KEY_S, "t": VirtualKeyShort.KEY_T,
            "u": VirtualKeyShort.KEY_U, "v": VirtualKeyShort.KEY_V,
            "w": VirtualKeyShort.KEY_W, "x": VirtualKeyShort.KEY_X,
            "y": VirtualKeyShort.KEY_Y, "z": VirtualKeyShort.KEY_Z,
        }
        # Add digit keys 0-9 if the enum exposes them (VirtualKeyShort.KEY_0 etc.)
        for _d in "0123456789":
            _attr = f"KEY_{_d}"
            if hasattr(VirtualKeyShort, _attr):
                cls._KEY_MAP[_d] = getattr(VirtualKeyShort, _attr)
        return cls._KEY_MAP

    def __init__(self):
        pass

    @staticmethod
    def _make_result(action: dict, target_name, status: str, detail: str, value=None) -> dict:
        return {
            "action": action.get("action", ""),
            "target": target_name,
            "status": status,
            "detail": detail,
            "value": value,
        }

    def execute(self, action: dict, element, window, engine) -> dict:
        """Execute a single action. Returns an ActionResult dict."""
        action_type = action.get("action", "")
        target_name = (element.Name if element is not None else None) if _FLAUI_AVAILABLE else None

        try:
            # ------------------------------------------------------------------
            # click
            # ------------------------------------------------------------------
            if action_type == "click":
                if element is None:
                    return self._make_result(action, None, "error", "click requires a target element")
                element.Click()
                return self._make_result(action, target_name, "ok", "clicked")

            # ------------------------------------------------------------------
            # double_click
            # ------------------------------------------------------------------
            elif action_type == "double_click":
                if element is None:
                    return self._make_result(action, None, "error", "double_click requires a target element")
                element.DoubleClick()
                return self._make_result(action, target_name, "ok", "double-clicked")

            # ------------------------------------------------------------------
            # right_click
            # ------------------------------------------------------------------
            elif action_type == "right_click":
                if element is None:
                    return self._make_result(action, None, "error", "right_click requires a target element")
                element.RightClick()
                return self._make_result(action, target_name, "ok", "right-clicked")

            # ------------------------------------------------------------------
            # type
            # ------------------------------------------------------------------
            elif action_type == "type":
                if element is None:
                    return self._make_result(action, None, "error", "type requires a target element")
                text = action.get("text", "")
                append = action.get("append", False)

                element.Focus()

                if not append:
                    # Try to clear via AsTextBox, fall back to select-all + delete
                    try:
                        element.AsTextBox().Text = ""
                    except Exception:
                        try:
                            Keyboard.TypeSimultaneously(*[VirtualKeyShort.CONTROL, VirtualKeyShort.KEY_A])
                            Keyboard.Press(VirtualKeyShort.DELETE)
                            Keyboard.Release(VirtualKeyShort.DELETE)
                        except Exception:
                            pass

                # Type the text — try Enter() first (Edit), fall back to Keyboard.Type (Document)
                try:
                    element.AsTextBox().Enter(text)
                except Exception:
                    Keyboard.Type(text)

                return self._make_result(action, target_name, "ok", f"typed {len(text)} chars")

            # ------------------------------------------------------------------
            # key
            # ------------------------------------------------------------------
            elif action_type == "key":
                keys_str = action.get("keys", "")
                parts = [p.strip().lower() for p in keys_str.split("+")]
                key_map = self._get_key_map()

                _modifier_names = {"ctrl", "control", "alt", "shift", "win", "lwin"}
                modifiers = []
                main_keys = []

                for part in parts:
                    if part in _modifier_names and part in key_map:
                        modifiers.append(key_map[part])
                    elif part in key_map:
                        main_keys.append(key_map[part])
                    # Unknown / unmapped keys are silently skipped

                if modifiers and main_keys:
                    # Use TypeSimultaneously so modifier state is correctly applied
                    all_keys = modifiers + main_keys
                    Keyboard.TypeSimultaneously(*all_keys)
                elif modifiers:
                    for mod in modifiers:
                        Keyboard.Press(mod)
                        Keyboard.Release(mod)
                else:
                    for k in main_keys:
                        Keyboard.Press(k)
                        Keyboard.Release(k)

                return self._make_result(action, target_name, "ok", f"sent key: {keys_str}")

            # ------------------------------------------------------------------
            # scroll
            # ------------------------------------------------------------------
            elif action_type == "scroll":
                if element is None:
                    return self._make_result(action, None, "error", "scroll requires a target element")
                direction = action.get("direction", "down")
                amount = int(action.get("amount", 3))

                # Move mouse to element center first
                try:
                    rect = element.BoundingRectangle
                    cx = rect.X + rect.Width // 2
                    cy = rect.Y + rect.Height // 2
                    Mouse.MoveTo(cx, cy)
                except Exception:
                    pass

                if direction in ("left", "right"):
                    ticks = amount if direction == "right" else -amount
                    Mouse.HorizontalScroll(ticks)
                else:
                    # up = positive, down = negative
                    ticks = amount if direction == "up" else -amount
                    Mouse.Scroll(ticks)

                return self._make_result(action, target_name, "ok", f"scrolled {direction} {amount}")

            # ------------------------------------------------------------------
            # focus
            # ------------------------------------------------------------------
            elif action_type == "focus":
                if element is None:
                    return self._make_result(action, None, "error", "focus requires a target element")
                element.Focus()
                return self._make_result(action, target_name, "ok", "focused")

            # ------------------------------------------------------------------
            # read
            # ------------------------------------------------------------------
            elif action_type == "read":
                if element is None:
                    return self._make_result(action, None, "error", "read requires a target element")
                value = None
                try:
                    value = element.AsTextBox().Text
                except Exception:
                    pass
                if not value:
                    try:
                        value = element.Patterns.Value.Pattern.Value
                    except Exception:
                        pass
                if not value:
                    try:
                        # Document elements expose text via the Text pattern
                        value = element.Patterns.Text.Pattern.DocumentRange.GetText(-1)
                    except Exception:
                        pass
                if not value:
                    try:
                        value = element.Name
                    except Exception:
                        value = ""
                return self._make_result(action, target_name, "ok", "read value", value=str(value or ""))

            # ------------------------------------------------------------------
            # read_screen
            # ------------------------------------------------------------------
            elif action_type == "read_screen":
                lines = []
                seen = set()
                try:
                    descendants = window.FindAllDescendants()
                    for el in descendants:
                        try:
                            name = (el.Name or "").strip()
                            if name and name not in seen:
                                lines.append(name)
                                seen.add(name)
                        except Exception:
                            pass
                        try:
                            val = el.Patterns.Value.Pattern.Value
                            if val and val.strip() and val.strip() not in seen:
                                lines.append(val.strip())
                                seen.add(val.strip())
                        except Exception:
                            pass
                except Exception:
                    pass
                screen_text = "\n".join(lines)
                return self._make_result(action, None, "ok", f"read {len(lines)} elements", value=screen_text)

            # ------------------------------------------------------------------
            # wait
            # ------------------------------------------------------------------
            elif action_type == "wait":
                ms = action.get("ms", 1000)
                time.sleep(ms / 1000.0)
                return self._make_result(action, None, "ok", f"waited {ms}ms")

            # ------------------------------------------------------------------
            # screenshot
            # ------------------------------------------------------------------
            elif action_type == "screenshot":
                if not _PIL_AVAILABLE:
                    return self._make_result(action, None, "error", "PIL not available for screenshot")
                img = PIL.ImageGrab.grab()
                path = tempfile.mktemp(suffix=".png")
                img.save(path)
                return self._make_result(action, None, "ok", f"screenshot saved", value=path)

            # ------------------------------------------------------------------
            # close_app
            # ------------------------------------------------------------------
            elif action_type == "close_app":
                # AutomationElement doesn't expose .Close() directly —
                # use the Window pattern instead.
                try:
                    window.Patterns.Window.Pattern.Close()
                except Exception:
                    # Fallback: send Alt+F4 to the window
                    try:
                        window.Focus()
                    except Exception:
                        pass
                    Keyboard.TypeSimultaneously(VirtualKeyShort.ALT, VirtualKeyShort.F4)
                return self._make_result(action, None, "ok", "window closed")

            else:
                return self._make_result(action, target_name, "error", f"unknown action type: {action_type!r}")

        except Exception as exc:
            return self._make_result(action, target_name, "error", str(exc))


class WindowsAutomationEngine:
    """Central singleton that owns the UIA3Automation instance and coordinates all sub-components."""

    def __init__(self):
        self._automation = _automation
        self._resolver = AppResolver(automation=_automation)
        self._finder = ElementFinder()
        self._executor = ActionExecutor()

    def launch_app(self, app: str, args: str = "") -> dict:
        """Launch an application by name. Returns status dict."""
        try:
            # Check if already running
            window = self._resolver.resolve(app)
            if window is not None:
                return {
                    "status": "already_running",
                    "window_title": window.Name,
                    "detail": "already running",
                }

            # Determine executable
            app_lower = app.lower()
            known = AppResolver.KNOWN_APPS.get(app_lower, {})
            exe = known.get("exe") or app

            # Security: reject exe names with path separators unless it's a known app
            if not known and (os.sep in exe or '/' in exe):
                return {"status": "error", "window_title": "", "detail": f"Unknown app with path separators rejected: {exe!r}"}

            # Build command
            cmd = [exe]
            if args:
                try:
                    cmd += shlex.split(args)
                except ValueError:
                    cmd += args.split()

            subprocess.Popen(cmd)

            # Poll up to 5 seconds for window to appear
            deadline = time.time() + 5.0
            while time.time() < deadline:
                time.sleep(0.5)
                window = self._resolver.resolve(app)
                if window is not None:
                    return {
                        "status": "launched",
                        "window_title": window.Name,
                        "detail": "launched",
                    }

            return {"status": "error", "window_title": "", "detail": "window did not appear within 5s"}

        except Exception as exc:
            return {"status": "error", "window_title": "", "detail": str(exc)}

    def inspect_window(self, app: str, depth: int = 4, filter_types: str = "") -> list:
        """Return a compact element tree for a running application window."""
        try:
            window = self._resolver.resolve(app)
            if window is None:
                return [{"error": f"Window not found for: {app}"}]

            # Parse filter types
            allowed_types = set()
            if filter_types:
                allowed_types = {t.strip().lower() for t in filter_types.split(",") if t.strip()}

            from collections import deque
            queue = deque([(window, 0)])
            results = []

            while queue and len(results) < 200:
                el, d = queue.popleft()
                if d > depth:
                    continue

                # Get control type name (short form e.g. "Button", not full .NET type path)
                try:
                    ct_name = str(el.ControlType).split('.')[-1]
                except Exception:
                    ct_name = ""

                # Apply filter
                if allowed_types and ct_name.lower() not in allowed_types:
                    # Still enqueue children so we can find matching descendants
                    if d < depth:
                        try:
                            for child in el.FindAllChildren():
                                queue.append((child, d + 1))
                        except Exception:
                            pass
                    continue

                # Get element name
                try:
                    name = el.Name or ""
                except Exception:
                    name = ""

                # Get automation id
                try:
                    automation_id = el.AutomationId or ""
                except Exception:
                    automation_id = ""

                # Get value
                val = ""
                try:
                    val = el.AsTextBox().Text or ""
                except Exception:
                    try:
                        val = el.Patterns.Value.Pattern.Value or ""
                    except Exception:
                        pass

                # Get bounding rect
                try:
                    r = el.BoundingRectangle
                    rect = {"x": int(r.X), "y": int(r.Y), "w": int(r.Width), "h": int(r.Height)}
                except Exception:
                    rect = {"x": 0, "y": 0, "w": 0, "h": 0}

                results.append({
                    "name": name,
                    "automation_id": automation_id,
                    "control_type": ct_name,
                    "value": val,
                    "rect": rect,
                    "depth": d,
                })

                if d < depth:
                    try:
                        for child in el.FindAllChildren():
                            queue.append((child, d + 1))
                    except Exception:
                        pass

            # Sort by depth (shallowest first)
            results.sort(key=lambda e: e["depth"])
            return results

        except Exception as exc:
            return [{"error": str(exc)}]

    def execute_batch(self, app: str, actions: list) -> list:
        """Execute a batch of UI actions sequentially. Returns one result per action.

        On element-not-found or action errors, automatically runs inspect_window
        and attaches the result as 'inspect_fallback' so the agent can see what's
        actually on screen and recover.
        """
        def _inspect_fallback(window):
            """Return a compact inspect snapshot for the agent to reason about."""
            try:
                return self.inspect_window(app)
            except Exception:
                return []

        try:
            window = self._resolver.resolve(app)
            if window is None:
                return [
                    {
                        "action": a.get("action", ""),
                        "target": None,
                        "status": "error",
                        "detail": f"Window not found for: {app}. Use windows_launch first.",
                        "value": None,
                    }
                    for a in actions
                ]

            results = []
            for action in actions:
                try:
                    target_desc = action.get("target")
                    element = None

                    if target_desc:
                        element = self._finder.find(window, target_desc)
                        if element is None:
                            results.append({
                                "action": action.get("action", ""),
                                "target": None,
                                "status": "error",
                                "detail": f"Element not found: {target_desc}",
                                "value": None,
                                "inspect_fallback": _inspect_fallback(window),
                            })
                            continue

                    result = self._executor.execute(action, element, window, self)

                    # If the action itself failed, attach an inspect snapshot
                    if result.get("status") == "error":
                        result["inspect_fallback"] = _inspect_fallback(window)

                    results.append(result)

                    if action.get("action") == "close_app" and result.get("status") == "ok":
                        remaining = actions[len(results):]
                        for skipped in remaining:
                            results.append({
                                "action": skipped.get("action", ""),
                                "target": None,
                                "status": "skipped",
                                "detail": "skipped — window was closed by close_app",
                                "value": None,
                            })
                        break

                except Exception as exc:
                    results.append({
                        "action": action.get("action", ""),
                        "target": None,
                        "status": "error",
                        "detail": str(exc),
                        "value": None,
                        "inspect_fallback": _inspect_fallback(window),
                    })

            return results

        except Exception as exc:
            return [
                {
                    "action": a.get("action", ""),
                    "target": None,
                    "status": "error",
                    "detail": str(exc),
                    "value": None,
                }
                for a in actions
            ]

    def get_desktop_windows(self) -> list:
        """Return a list of all top-level windows with title and process name."""
        try:
            desktop = self._automation.GetDesktop()
            children = desktop.FindAllChildren()
            result = []
            for child in children:
                try:
                    title = child.Name or ""
                    try:
                        pid = child.Properties.ProcessId.Value
                        proc_name = psutil.Process(pid).name()
                    except Exception:
                        proc_name = ""
                    result.append({"title": title, "process_name": proc_name})
                except Exception:
                    continue
            return result
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Module-level engine singleton
# ---------------------------------------------------------------------------

engine = WindowsAutomationEngine()
