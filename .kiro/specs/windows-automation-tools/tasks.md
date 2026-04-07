# Tasks: Windows Automation Tools

## Task List

- [ ] 1. Rewrite flaui.py — automation engine core
  - [ ] 1.1 Load FlaUI DLLs and create UIA3Automation singleton at module level
  - [ ] 1.2 Implement AppResolver with KNOWN_APPS registry and 4-strategy resolution
  - [ ] 1.3 Implement ElementFinder with 5-strategy resolution (automation_id, exact name, contains name, control_type+index, text_contains)
  - [ ] 1.4 Implement ActionExecutor supporting all 12 action types (click, double_click, right_click, type, key, scroll, focus, read, read_screen, wait, screenshot, close_app)
  - [ ] 1.5 Implement WindowsAutomationEngine orchestrating the above components (launch_app, inspect_window, execute_batch, get_desktop_windows)

- [ ] 2. Clean up and update agent.py
  - [ ] 2.1 Remove browser_automation tool, ChromeBrowser class, and all browser-use/langchain imports
  - [ ] 2.2 Remove old FlaUI tools (search_win_app_by_name, start_app_session, inspect_ui_elements, list_element_names, get_element_details, stop_app_session), win import, and ACTIVE_SESSIONS
  - [ ] 2.3 Add windows_launch tool (register_tool, BaseTool, launch via engine)
  - [ ] 2.4 Add windows_inspect tool (register_tool, BaseTool, inspect via engine)
  - [ ] 2.5 Add windows_do tool (register_tool, BaseTool, batch execute via engine)

- [ ] 3. Write WindowsAutomator.md skill file
  - [ ] 3.1 Document when to use each tool and the full action type reference including read_screen
  - [ ] 3.2 Add example action batches for Chrome, Excel, Word, WhatsApp, CMD, Settings, File Explorer
  - [ ] 3.3 Explain read_screen as the preferred content-reading method, explicit close_app requirement, and windows_inspect usage guidance
