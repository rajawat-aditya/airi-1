# windows-do-focus-fix Tasks

## Tasks

- [x] 1. Write exploratory tests for the bug condition
  - [x] 1.1 In `agent-server/test_flaui.py`, add a test that mocks `AppResolver.resolve` to return a mock window object, calls `execute_batch`, and asserts that `window.Patterns.Window.Pattern.SetForeground` was called before any action — this test MUST fail on unfixed code
  - [x] 1.2 Add a test that verifies when `resolve()` returns `None`, the focus call is never reached and error results are returned for all actions (should pass on both unfixed and fixed code)

- [x] 2. Implement the fix in `execute_batch`
  - [x] 2.1 In `agent-server/flaui.py`, inside `WindowsAutomationEngine.execute_batch`, immediately after the `window = self._resolver.resolve(app)` non-None branch, add a try/except block that calls `window.Patterns.Window.Pattern.SetForeground()` followed by `time.sleep(0.1)`

- [x] 3. Write fix-checking tests (Property 1)
  - [x] 3.1 Add a unit test that mocks the window and verifies `SetForeground` is called before the first action executes on the fixed code
  - [x] 3.2 Add a unit test that verifies a `SetForeground` exception does not abort the batch — remaining actions still execute and return results

- [x] 4. Write preservation-checking tests (Property 2)
  - [x] 4.1 Add a test verifying that when `resolve()` returns `None`, the fixed `execute_batch` returns the same error results as before (unchanged behavior)
  - [x] 4.2 Add a test verifying that `close_app` skip logic is unaffected — actions after a successful `close_app` are still skipped
  - [x] 4.3 Add a test verifying that per-action error continuation is unaffected — a failing action does not abort subsequent actions in the batch
