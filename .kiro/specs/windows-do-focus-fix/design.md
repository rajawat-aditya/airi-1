# windows-do-focus-fix Bugfix Design

## Overview

`WindowsAutomationEngine.execute_batch` in `agent-server/flaui.py` resolves the target
window via `AppResolver.resolve()` but never brings it to the foreground before
dispatching actions. As a result, keyboard input, clicks, and other interactions land on
whichever window currently has OS focus — silently affecting the wrong application.

The fix is minimal: immediately after a successful `resolve()` call inside
`execute_batch`, call the FlaUI/Win32 focus API on the resolved window so that all
subsequent actions are directed to the correct window.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — `execute_batch` is called
  with a valid `app` name and the resolved window is not the current foreground window.
- **Property (P)**: The desired behavior — the resolved window is brought to the
  foreground before any action in the batch is executed.
- **Preservation**: All existing behavior of `execute_batch` that must remain unchanged:
  error handling for unresolvable apps, `close_app` skip logic, per-action error
  continuation, and correct behavior when the window is already focused.
- **execute_batch**: The method in `WindowsAutomationEngine` (`agent-server/flaui.py`)
  that resolves a window and dispatches a list of UI actions against it.
- **resolve**: `AppResolver.resolve(app)` — returns a live FlaUI `AutomationElement`
  representing the target window, or `None` if not found.
- **foreground window**: The OS-level window that currently receives keyboard and mouse
  input; set via `SetForegroundWindow` (Win32) or `window.Focus()` / `window.SetForeground()` (FlaUI).

## Bug Details

### Bug Condition

The bug manifests when `execute_batch` is called and the resolved target window is not
the current foreground window. The method resolves the window correctly but dispatches
all actions without first calling any focus or bring-to-foreground API, so the OS
delivers input to whatever window happens to be active.

**Formal Specification:**
```
FUNCTION isBugCondition(batch_call)
  INPUT: batch_call = { app: str, actions: list }
  OUTPUT: boolean

  window := AppResolver.resolve(batch_call.app)
  RETURN window IS NOT None
         AND window != getCurrentForegroundWindow()
         AND focusAPICalledOnWindow(window) == False
END FUNCTION
```

### Examples

- **Typical case**: Agent calls `windows_do("notepad", [{"action": "type", "text": "hello"}])`.
  Notepad is open but the user's browser is in the foreground. Without the fix, "hello"
  is typed into the browser. With the fix, Notepad is focused first.
- **Multi-action batch**: Agent calls `windows_do("excel", [click, type, key])`. All
  three actions land on the wrong window if Excel is not foreground.
- **Already focused (edge case)**: Target window is already foreground. Calling focus is
  a no-op; all actions continue to work correctly.
- **Unresolvable app**: `resolve()` returns `None`. Error path is unchanged — focus call
  is never reached.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- When `resolve()` returns `None`, `execute_batch` SHALL continue to return error results
  for every action without crashing.
- When a `close_app` action succeeds, `execute_batch` SHALL continue to skip all
  remaining actions in the batch.
- When an individual action fails, `execute_batch` SHALL continue to proceed with
  subsequent actions rather than aborting the batch.
- When the target window is already the foreground window, `execute_batch` SHALL continue
  to execute all actions correctly without error.

**Scope:**
All inputs that do NOT involve a resolved window that is not the foreground window are
completely unaffected by this fix. This includes:
- Batches where `resolve()` returns `None`
- Batches where the target window is already focused
- All individual action types (click, type, key, scroll, read, screenshot, etc.)

## Hypothesized Root Cause

Based on code inspection of `execute_batch` (lines ~830–900 of `flaui.py`):

1. **Missing focus call after resolve**: After `window = self._resolver.resolve(app)`
   succeeds, the code immediately enters the action loop with no call to
   `window.Focus()`, `window.SetForeground()`, or any Win32 `SetForegroundWindow` API.
   This is the direct cause.

2. **FlaUI window element exposes focus APIs**: `AutomationElement` exposes `.Focus()`
   and the `Window` pattern exposes `.SetForeground()`. Either can be used; the Window
   pattern's `SetForeground()` is the more semantically correct choice for bringing a
   top-level window to the foreground.

3. **No fallback for focus failure**: If the focus call fails (e.g., another process has
   a modal dialog), the batch should still proceed rather than abort — so the call must
   be wrapped in a try/except.

4. **No timing guard**: After calling focus, a brief sleep or retry may be needed on
   some systems before the window is ready to receive input. A small `time.sleep(0.1)`
   after the focus call is a safe guard.

## Correctness Properties

Property 1: Bug Condition - Focus Before Actions

_For any_ batch call where `isBugCondition` holds (valid app resolves to a window that is
not the current foreground window), the fixed `execute_batch` SHALL call the FlaUI/Win32
focus API on the resolved window before executing the first action, ensuring all
subsequent keyboard and mouse actions are directed to the correct window.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - Unchanged Batch Behavior

_For any_ batch call where `isBugCondition` does NOT hold (app cannot be resolved, or
window is already foreground), the fixed `execute_batch` SHALL produce the same results
as the original `execute_batch`, preserving error handling, `close_app` skip logic,
per-action error continuation, and correct execution when already focused.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

**File**: `agent-server/flaui.py`

**Method**: `WindowsAutomationEngine.execute_batch`

**Specific Changes**:

1. **Add focus call after successful resolve**: Immediately after
   `window = self._resolver.resolve(app)` returns a non-`None` value, call the
   Window pattern's `SetForeground()` to bring the window to the foreground.

2. **Wrap in try/except**: The focus call must not abort the batch if it fails (e.g.,
   UAC dialog, another process holds foreground lock). Catch all exceptions and log a
   warning but continue.

3. **Add brief sleep after focus**: Insert `time.sleep(0.1)` after the focus call to
   give the OS time to complete the window activation before the first action fires.

**Pseudocode for the change:**
```
window = self._resolver.resolve(app)
if window is None:
    # existing error path — unchanged
    ...

# NEW: bring window to foreground before dispatching actions
try:
    window.Patterns.Window.Pattern.SetForeground()
    time.sleep(0.1)
except Exception:
    pass  # best-effort; proceed even if focus fails

# existing action loop — unchanged
for action in actions:
    ...
```

## Testing Strategy

### Validation Approach

Two-phase approach: first surface counterexamples on unfixed code to confirm the root
cause, then verify the fix works and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Demonstrate the bug on unfixed code — confirm that `execute_batch` never calls
a focus API on the resolved window.

**Test Plan**: Mock `AppResolver.resolve` to return a mock window object. Call
`execute_batch` with a simple action. Assert that `window.Patterns.Window.Pattern.SetForeground`
(or equivalent) was called. On unfixed code this assertion will fail.

**Test Cases**:
1. **Focus not called on unfixed code**: Mock window, call `execute_batch(app, [click])`,
   assert `SetForeground` was called — will fail on unfixed code.
2. **Actions land on wrong window**: Integration test with two open windows; verify
   action targets the resolved window, not the foreground one — will fail on unfixed code.
3. **Multi-action batch**: Same as above with 3 actions — all land on wrong window on
   unfixed code.
4. **Edge case — no window**: `resolve()` returns `None`; focus call is never reached —
   should pass on both unfixed and fixed code.

**Expected Counterexamples**:
- `SetForeground` / `Focus` is never invoked on the window object before actions execute.
- Possible causes: missing focus call, wrong location in code, exception swallowed silently.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function
brings the window to the foreground before executing actions.

**Pseudocode:**
```
FOR ALL batch_call WHERE isBugCondition(batch_call) DO
  result := execute_batch_fixed(batch_call.app, batch_call.actions)
  ASSERT focusAPICalledOnWindow(resolvedWindow) BEFORE firstActionExecuted
  ASSERT result contains one entry per action
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed
`execute_batch` produces the same results as the original.

**Pseudocode:**
```
FOR ALL batch_call WHERE NOT isBugCondition(batch_call) DO
  ASSERT execute_batch_original(batch_call) == execute_batch_fixed(batch_call)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking
because it generates many combinations of action types, target descriptors, and app
names automatically, catching edge cases that manual tests miss.

**Test Cases**:
1. **Unresolvable app preservation**: `resolve()` returns `None`; verify error results
   are identical before and after fix.
2. **close_app skip preservation**: Batch with `close_app` followed by more actions;
   verify remaining actions are still skipped after fix.
3. **Per-action error continuation**: Batch where one action fails; verify subsequent
   actions still execute after fix.
4. **Already-focused window**: Window is already foreground; verify all actions still
   succeed and focus call is a no-op.

### Unit Tests

- Test that `execute_batch` calls `SetForeground` on the resolved window before the
  first action (mock window, spy on focus call).
- Test that a focus failure (exception from `SetForeground`) does not abort the batch.
- Test that `execute_batch` still returns error results for all actions when `resolve()`
  returns `None` (unchanged behavior).
- Test `close_app` skip logic is unaffected by the focus call.

### Property-Based Tests

- Generate random lists of action dicts; verify that for any valid app, the focus API
  is always called exactly once before the action loop.
- Generate random app names that don't resolve; verify the error path is always taken
  and focus is never called.
- Generate random batches containing `close_app` at various positions; verify skip
  behavior is preserved.

### Integration Tests

- Open two real windows; call `execute_batch` targeting the background window; verify
  the correct window receives the actions after the fix.
- Verify that a `type` action types into the correct window even when another window
  is in the foreground at call time.
- Verify that switching between apps in successive `execute_batch` calls works correctly
  (each call focuses its own target window).
