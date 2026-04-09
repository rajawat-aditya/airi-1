# Implementation Plan: Airi Fluent Design Polish

## Overview

Migrate the Airi Electron + Next.js app to Microsoft Fluent 2 Design System. Tasks follow the design architecture: infrastructure first (package, fonts, theme hook, provider), then component-by-component migration, then RAI surfaces, then prose token wiring, then legacy cleanup, and finally property-based tests.

## Tasks

- [x] 1. Install @fluentui/react-components
  - Add `@fluentui/react-components` to `dependencies` in `package.json` via `npm install @fluentui/react-components`
  - Verify the package resolves `FluentProvider`, `webLightTheme`, `webDarkTheme`, `Spinner`, `Button`, `Dialog`, `TabList`, `Tab` from the same import
  - _Requirements: 1.1_

- [x] 2. Add custom fonts and declare @font-face
  - Place Cabinet Grotesk Extrabold, Satoshi Medium, and Zina font files under `public/fonts/`
  - Add `@font-face` blocks in `src/app/globals.css` for all three fonts with `font-display: swap` and `sans-serif` fallback
  - Expose `--font-heading`, `--font-body`, `--font-logo` CSS custom properties in `:root`
  - _Requirements: 2.1, 2.2, 2.3, 2.7_

- [x] 3. Create useFluentTheme hook
  - Create `ui-components/hooks/useFluentTheme.jsx`
  - Import `webLightTheme` and `webDarkTheme` from `@fluentui/react-components`
  - Call `useTheme()` from the existing `ThemeContext`; default to `"Night"` if context is missing
  - Merge the base theme with Windows Blue brand overrides: `colorBrandBackground: '#0078D4'`, `colorBrandBackgroundHover: '#106EBE'`, `colorBrandBackgroundPressed: '#005A9E'`
  - Export `useFluentTheme` and also export a standalone `buildCustomTheme(themeMode)` helper for testing
  - _Requirements: 1.3, 1.4, 1.5_

  - [ ]* 3.1 Write property test for Custom_Theme brand tokens (Property 1)
    - **Property 1: Custom_Theme always carries Windows Blue brand tokens**
    - Use `fast-check` `fc.constantFrom('Night', 'Day')` to drive `buildCustomTheme`
    - Assert `colorBrandBackground === '#0078D4'`, `colorBrandBackgroundHover === '#106EBE'`, `colorBrandBackgroundPressed === '#005A9E'` for both modes
    - **Validates: Requirements 1.5**

- [x] 4. Create FluentClientProvider component
  - Create `src/component/FluentClientProvider.jsx` with `"use client"` directive
  - Import `FluentProvider` from `@fluentui/react-components` and `useFluentTheme` from the hook
  - Render `<FluentProvider theme={fluentTheme}>{children}</FluentProvider>`
  - _Requirements: 1.2, 1.3, 1.4_

- [x] 5. Update layout.js to use FluentClientProvider
  - Import `FluentClientProvider` in `src/app/layout.js`
  - Wrap `{children}` with `<FluentClientProvider>` inside `<ThemeProvider>`
  - Replace `<link rel="icon" href="/logo.ico" />` with an inline SVG favicon `<link rel="icon" ...>` using the "A" mark in Windows Blue (`#0078D4`)
  - _Requirements: 1.2, 3.7_

- [x] 6. Update ui-components/index.css token bridge
  - In `ui-components/index.css`, replace the hardcoded hex values for all CSS custom properties with references to Fluent token CSS variables injected by `FluentProvider`
  - Map: `--bg-app` → `var(--colorNeutralBackground1)`, `--bg-modal` → `var(--colorNeutralBackground1)`, `--bg-card` → `var(--colorNeutralBackground2)`, `--bg-hover` → `var(--colorNeutralBackground3)`, `--text-primary` → `var(--colorNeutralForeground1)`, `--text-secondary` → `var(--colorNeutralForeground2)`, `--text-muted` → `var(--colorNeutralForeground3)`, `--border-default` → `var(--colorNeutralStroke1)`, `--border-active` → `var(--colorBrandStroke1)`, `--accent-blue` → `var(--colorBrandBackground)`, `--accent-red` → `var(--colorPaletteRedBackground3)`
  - Update scrollbar thumb to `var(--colorBrandBackground)` and track to `var(--colorNeutralBackground2)`
  - Keep all Tailwind `@theme` mappings and utility class names unchanged so no component class rewrites are needed
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [x] 7. Create LogoMark component
  - Create `src/component/LogoMark.jsx`
  - Accept `collapsed: boolean` prop
  - Render `"A"` when `collapsed=true`, `"Airi"` when `collapsed=false`
  - Apply `font-family: 'Zina', sans-serif`, `font-size: 20px`, `color: #0078D4`
  - Add CSS transition on `opacity` and `max-width` completing within 200 ms ease-in-out
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 7.1 Write property test for LogoMark color (Property 2)
    - **Property 2: LogoMark color is always Windows Blue**
    - Use `fast-check` `fc.boolean()` to drive the `collapsed` prop
    - Render with `@testing-library/react` and assert computed color equals `rgb(0, 120, 212)` (`#0078D4`)
    - **Validates: Requirements 3.4**

- [x] 8. Update appsidebar.jsx
  - Replace `<h1>Airi</h1>` with `<LogoMark collapsed={sidebarState === 'close'} />`; derive `sidebarState` from the sidebar's `data-state` attribute or local state
  - Replace sidebar toggle inline SVG with `PanelLeft24Regular` / `PanelLeftContract24Regular` from `@fluentui/react-icons`
  - Replace New Chat inline SVG with `Edit24Regular`
  - Replace Library inline SVG with `Library24Regular`
  - Replace Memory inline SVG with `BrainCircuit24Regular`
  - Replace Sign-in inline SVG with `Person24Regular`
  - Replace Apps24Regular import (already present) with the icons listed above; remove unused imports
  - _Requirements: 3.1, 3.2, 3.3, 4.1, 4.2, 4.3_

- [x] 9. Update AgentLoader.jsx
  - Replace the conic-gradient `<div>` spinner with Fluent `<Spinner size="small" />` from `@fluentui/react-components`
  - Replace `<img src="/logo.png" />` with a Zina "A" text mark: `<span style={{ fontFamily: "'Zina', sans-serif", fontSize: 20, color: '#0078D4' }}>A</span>`
  - Apply `var(--colorNeutralBackground2)` as the container background (replace `bg-bg-card`)
  - Apply `font-family: 'Satoshi-Medium', sans-serif` at 14 px to the tool label `<span>`
  - Export `TOOL_LABELS` so it can be imported by tests
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 3.8_

  - [ ]* 9.1 Write property test for AgentLoader tool label mapping (Property 4)
    - **Property 4: AgentLoader tool label maps all known tool names**
    - Use `fast-check` `fc.constantFrom(...Object.keys(TOOL_LABELS))` to drive `toolName`
    - Render `<AgentLoader toolName={toolName} />` and assert the rendered text matches `TOOL_LABELS[toolName]`
    - **Validates: Requirements 7.3**

- [x] 10. Update chatInput.jsx
  - Replace the attach-file native `<button>` with Fluent `<Button appearance="subtle" icon={<Attach24Regular />} />` from `@fluentui/react-components`
  - Replace the mic native `<button>` with Fluent `<Button appearance="subtle" icon={<MicSparkle24Regular />} />` / `<Button appearance="subtle" icon={<MicOff24Regular />} />`; apply `colorBrandBackground` token as background when mic is active
  - Replace the submit native `<button>` with Fluent `<Button appearance="primary" icon={<ArrowUp24Regular />} disabled={!hasContent} />`
  - Update drag overlay border to use `var(--colorBrandStroke1)` instead of `border-blue-500/70`
  - Update container border-radius to `var(--borderRadiusXLarge)`
  - Update focused border to `var(--colorBrandStroke1)`
  - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 10.1 Write property test for submit button disabled state (Property 3)
    - **Property 3: Submit button disabled state tracks input emptiness**
    - Use `fast-check` `fc.string()` and `fc.array(fc.record({ file: fc.constant(new File([], 'f.txt')) }))` to drive text and files
    - Assert button is disabled iff `!text.trim() && files.length === 0`
    - **Validates: Requirements 6.3**

- [x] 11. Update chatMain.jsx with RAI surfaces and Fluent icons
  - [x] 11.1 Add RAI_Label component and render above each assistant bubble
    - Create an inline `RAI_Label` component (or small file `src/component/RAI_Label.jsx`) rendering `<Sparkle24Regular />` + "AI-generated" text using `colorNeutralForeground3` at 11 px Satoshi Medium
    - When `streamingMessageId === msg.versions[0].id`, render `RAI_Label` with `streaming={true}` showing "AI is responding…"
    - When streaming is complete, render `RAI_Label` with default "AI-generated" text
    - Add `data-testid="rai-label"` to the element
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 11.2 Add Feedback_Control with thumbs-up / thumbs-down per message
    - Add `feedbackState` map in `chatMain.jsx`: `Map<messageId, 'none' | 'up' | 'down'>` via `useState`
    - Create an inline `Feedback_Control` component rendering Fluent `<Button appearance="subtle" icon={<ThumbLike24Regular />} />` and `<Button appearance="subtle" icon={<ThumbDislike24Regular />} />`
    - Apply `colorBrandBackground` token to the selected button's icon
    - Add `data-testid="feedback-control"` to the wrapper
    - Show only on completed (non-streaming) messages
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 11.3 Add Verify_Nudge below Feedback_Control
    - Create an inline `Verify_Nudge` component rendering "Always verify AI responses before acting on them." at 11 px Satoshi Medium using `colorNeutralForeground4`
    - Add `data-testid="verify-nudge"` to the element
    - Render only when `streamingMessageId !== msg.versions[0].id`
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

  - [x] 11.4 Add RAI_Disclaimer in greeting state
    - Below the greeting `<h2>` in `ChatInput`'s `showgreet` block (or in `chatMain.jsx` greeting area), render `<RAI_Disclaimer />` with `<Info24Regular />` + "Airi can make mistakes. Verify important information." at 12 px Satoshi Medium using `colorNeutralForeground3`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 11.5 Replace mobile sidebar toggle SVG with Fluent icon
    - Replace the inline SVG in the mobile sidebar toggle `<div>` with `<PanelLeft24Regular />` from `@fluentui/react-icons`
    - _Requirements: 4.1_

  - [ ]* 11.6 Write property tests for RAI surfaces (Properties 5, 6, 7)
    - **Property 5: Every completed AI response has a RAI_Label**
    - **Property 6: Every completed AI response has a Feedback_Control**
    - **Property 7: Verify_Nudge present on completed responses, absent during streaming**
    - Use `fast-check` `fc.string({ minLength: 1 })` and `fc.boolean()` to drive `content` and `isStreaming`
    - For non-streaming: assert `data-testid="rai-label"` present with "AI-generated", `data-testid="feedback-control"` present, `data-testid="verify-nudge"` present
    - For streaming: assert `data-testid="verify-nudge"` absent
    - **Validates: Requirements 9.1, 9.4, 11.1, 12.1, 12.5**

- [x] 12. Update SettingsModal to use Fluent Dialog and TabList
  - Open `ui-components/components/SettingModal.jsx`
  - Replace the outer wrapper div with Fluent `<Dialog>` / `<DialogSurface>` / `<DialogTitle>` / `<DialogBody>`
  - Replace the tab navigation with Fluent `<TabList>` + `<Tab>` components; active tab underline uses `colorBrandStroke1`
  - Replace the close button with Fluent `<Button appearance="subtle" icon={<Dismiss24Regular />} />`
  - Remove the backdrop `<div>` from `appsidebar.jsx` (Fluent Dialog handles its own overlay via `colorBackgroundOverlay`)
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 13. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Update globals.css prose styles with Fluent token vars
  - In `src/app/globals.css`, update `.prose.prose-invert` styles:
    - `p` color: replace `#e5ebfa` with `var(--colorNeutralForeground1)`
    - `pre code` background: replace `#1a1d2e` with `var(--colorNeutralBackground3)`; text color: replace `#e5ebfa` with `var(--colorNeutralForeground1)`
    - `h1`, `h2`, `h3` color: replace `#e5ebfa` with `var(--colorNeutralForeground1)`; add `font-family: var(--font-heading)`
    - `ul`, `ol`, `li` color: replace `#e5ebfa` with `var(--colorNeutralForeground1)`
    - `:not(pre) > code` background: replace `#ffffff12` with `var(--colorNeutralBackground3)`; text color: replace `#e5ebfa` with `var(--colorNeutralForeground1)`
  - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_

- [x] 15. Replace legacy logo references
  - Search `src/` and `ui-components/` for any remaining `<img src="/logo.png">`, `<img src="/slew-logo-s.png">`, and `href="/logo.ico"` references
  - Replace each with the Zina "A" text mark span or the SVG favicon link added in task 5
  - Confirm `AgentLoader.jsx` no longer contains any `<img>` tag (covered by task 9)
  - _Requirements: 3.6, 3.7, 3.8_

- [x] 16. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Property tests use `fast-check` and `@testing-library/react`; install with `npm install --save-dev fast-check @testing-library/react @testing-library/jest-dom`
- The Tailwind utility class names (`bg-bg-card`, `text-text-primary`, etc.) are intentionally preserved — only their backing CSS variable values change in task 6, so no component JSX rewrites are needed for theming
- `buildCustomTheme` exported from `useFluentTheme.jsx` is the pure function used by Property 1 test
- `TOOL_LABELS` exported from `AgentLoader.jsx` is used by Property 4 test
- Feedback state is local to `chatMain.jsx` and is not persisted (acceptable for this scope)
