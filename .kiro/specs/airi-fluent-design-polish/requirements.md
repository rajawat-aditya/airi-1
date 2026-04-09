# Requirements Document

## Introduction

This feature polishes the Airi desktop app (Electron + Next.js) with Microsoft Fluent 2 Design System.
The goal is to replace the current custom CSS variable theming, inline SVG icons, and Google Sans Flex
typography with a cohesive Fluent 2 experience: FluentProvider for light/dark theming, colorful
@fluentui/react-icons, Windows brand color (#0078D4) as the primary accent, custom typography
(Cabinet Grotesk Extrabold for headings, Satoshi Medium for body, Zina for the "Airi" logo mark),
and Responsible AI (RAI) surface patterns — transparency labels, disclaimers, feedback mechanisms,
and verify-output nudges — throughout the chat interface.

---

## Glossary

- **App**: The Airi Electron + Next.js desktop application.
- **FluentProvider**: The `@fluentui/react-components` context provider that supplies Fluent 2 design tokens to all child components.
- **Fluent_Token**: A design token value (color, spacing, typography, shadow) supplied by `@fluentui/react-components` theme objects (`webLightTheme` / `webDarkTheme`).
- **Custom_Theme**: A Fluent 2 theme object that extends `webLightTheme` / `webDarkTheme` with Windows brand color overrides (`colorBrandBackground: #0078D4`, etc.).
- **ThemeProvider**: The existing React context (`ui-components/hooks/useTheme.jsx`) that tracks the user's "Night" / "Day" preference and drives the FluentProvider theme selection.
- **Sidebar**: The collapsible left navigation panel (`src/component/appsidebar.jsx`), 256 px when expanded, 52 px when collapsed.
- **Logo_Mark**: The Zina-font text rendered in the Sidebar — "A" when collapsed, "Airi" when expanded.
- **Cabinet_Grotesk**: The Cabinet Grotesk Extrabold custom font applied to all heading elements (h1–h3) and prominent display text.
- **Satoshi**: The Satoshi Medium custom font applied to all body text, paragraphs, and UI labels.
- **Zina**: The Zina custom font applied exclusively to the Logo_Mark.
- **Windows_Blue**: The hex color `#0078D4`, used as the primary brand accent throughout the App.
- **AI_Response**: An assistant message bubble rendered in the chat area.
- **RAI_Label**: A visible "AI-generated" badge or label attached to every AI_Response.
- **RAI_Disclaimer**: A short explanatory text shown in the welcome/greeting state communicating the App's AI scope and limitations.
- **Feedback_Control**: A pair of thumbs-up / thumbs-down Fluent icon buttons attached to each completed AI_Response.
- **Verify_Nudge**: A short inline prompt encouraging the user to verify AI output, shown beneath each completed AI_Response.
- **AgentLoader**: The loading indicator component (`src/component/chatMain/AgentLoader.jsx`) shown while the AI is streaming.
- **ChatInput**: The chat input component (`src/component/chatInput/chatInput.jsx`).
- **SettingsModal**: The settings dialog component (`ui-components/components/SettingModal.jsx`).
- **Legacy_Logo**: The existing image-based logo files (`public/logo.ico`, `public/logo.png`, `public/slew-logo-s.png`) currently used in the app header and browser tab.

---

## Requirements

### Requirement 1: Install and Configure FluentProvider

**User Story:** As a developer, I want FluentProvider wrapping the entire App, so that all Fluent 2 components receive correct design tokens automatically.

#### Acceptance Criteria

1. THE App SHALL include `@fluentui/react-components` as a production dependency in `package.json`.
2. WHEN the App initialises, THE App SHALL render a `FluentProvider` component as the outermost wrapper inside `ThemeProvider` in `src/app/layout.js`.
3. WHILE the user's theme preference is "Night", THE FluentProvider SHALL receive the `Custom_Theme` derived from `webDarkTheme` with Windows_Blue brand color overrides.
4. WHILE the user's theme preference is "Day", THE FluentProvider SHALL receive the `Custom_Theme` derived from `webLightTheme` with Windows_Blue brand color overrides.
5. THE Custom_Theme SHALL set `colorBrandBackground` to `#0078D4`, `colorBrandBackgroundHover` to `#106EBE`, and `colorBrandBackgroundPressed` to `#005A9E`.
6. IF the user's system preference changes while the App is running, THEN THE ThemeProvider SHALL update the active theme and THE FluentProvider SHALL re-render with the new Custom_Theme within 100 ms.

---

### Requirement 2: Custom Typography Integration

**User Story:** As a designer, I want Cabinet Grotesk, Satoshi, and Zina fonts loaded and applied consistently, so that the App's visual identity matches the design specification.

#### Acceptance Criteria

1. THE App SHALL load Cabinet Grotesk Extrabold via `@font-face` declarations in the global CSS before any heading is rendered.
2. THE App SHALL load Satoshi Medium via `@font-face` declarations in the global CSS before any body text is rendered.
3. THE App SHALL load Zina via `@font-face` declarations in the global CSS before the Logo_Mark is rendered.
4. WHEN a heading element (h1, h2, h3) or display text is rendered, THE App SHALL apply `font-family: 'Cabinet Grotesk', sans-serif` and `font-weight: 800`.
5. WHEN a paragraph, label, or body text element is rendered, THE App SHALL apply `font-family: 'Satoshi', sans-serif` and `font-weight: 500`.
6. WHEN the Logo_Mark is rendered, THE App SHALL apply `font-family: 'Zina', sans-serif` exclusively to the Logo_Mark text.
7. IF a custom font file fails to load, THEN THE App SHALL fall back to the system sans-serif font stack without layout shift.

---

### Requirement 3: Sidebar Logo Mark and Logo Replacement

**User Story:** As a user, I want to see "A" when the sidebar is collapsed and "Airi" when it is expanded, and I want the Zina-font text to serve as the sole brand mark everywhere in the app, replacing all legacy image logos.

#### Acceptance Criteria

1. WHILE the Sidebar `data-state` attribute equals `"close"`, THE Sidebar SHALL render the Logo_Mark text `"A"` in the Zina font at 20 px font size.
2. WHILE the Sidebar `data-state` attribute equals `"open"`, THE Sidebar SHALL render the Logo_Mark text `"Airi"` in the Zina font at 20 px font size.
3. WHEN the Sidebar transitions between `"open"` and `"close"` states, THE Logo_Mark SHALL transition with a CSS opacity and width animation completing within 200 ms.
4. THE Logo_Mark SHALL use Windows_Blue (`#0078D4`) as its text color in both states.
5. THE Logo_Mark SHALL remain visible and not overflow the Sidebar boundary in either state.
6. THE App SHALL replace all usages of Legacy_Logo image files (`logo.ico`, `logo.png`, `slew-logo-s.png`) throughout the codebase with the Zina-font Logo_Mark text or an equivalent SVG text mark.
7. THE browser tab / window title bar icon SHALL be replaced with a generated favicon derived from the "A" Logo_Mark in Windows_Blue, or the legacy `.ico` file SHALL be updated to reflect the new brand mark.
8. WHEN the AgentLoader is visible, THE AgentLoader SHALL NOT render any legacy image logo; it SHALL use the Fluent Spinner alone (with optional Zina "A" text mark if space permits).

---

### Requirement 4: Fluent Colorful Icons

**User Story:** As a designer, I want all inline SVG icons replaced with @fluentui/react-icons colorful variants, so that the iconography is consistent with Fluent 2 and visually rich.

#### Acceptance Criteria

1. THE App SHALL replace every hand-crafted inline SVG icon in `appsidebar.jsx`, `chatMain.jsx`, `chatInput.jsx`, `chatItem.jsx`, and `AgentLoader.jsx` with a named component from `@fluentui/react-icons`.
2. WHEN a Fluent icon supports a colorful variant (suffixed `Color`), THE App SHALL use the colorful variant for navigation, action, and status icons.
3. THE App SHALL use `@fluentui/react-icons` icon components at a consistent size of 20 px (`fontSize={20}`) unless a specific size is required by layout.
4. WHEN the active theme is "Night", THE App SHALL render icons using Fluent token colors so that icon contrast meets the WCAG AA minimum contrast ratio of 4.5:1 against the background.
5. WHEN the active theme is "Day", THE App SHALL render icons using Fluent token colors so that icon contrast meets the WCAG AA minimum contrast ratio of 4.5:1 against the background.

---

### Requirement 5: Sidebar Collapse / Expand Behaviour

**User Story:** As a user, I want the sidebar to smoothly collapse to 52 px and expand to 256 px, so that I can maximise screen space for the chat area.

#### Acceptance Criteria

1. WHILE the Sidebar `data-state` is `"open"`, THE Sidebar SHALL have a rendered width of 256 px.
2. WHILE the Sidebar `data-state` is `"close"`, THE Sidebar SHALL have a rendered width of 52 px.
3. WHEN the toggle button is activated, THE Sidebar SHALL animate the width transition using a CSS ease-in-out curve completing within 300 ms.
4. WHILE the Sidebar `data-state` is `"close"`, THE Sidebar SHALL hide all text labels and show only icon buttons.
5. WHEN the viewport width is less than 768 px, THE Sidebar SHALL overlay the content area as a drawer rather than pushing the layout.
6. WHEN the Sidebar is in drawer mode and `data-state` is `"close"`, THE Sidebar SHALL translate fully off-screen to the left.

---

### Requirement 6: Fluent Component Migration — ChatInput

**User Story:** As a developer, I want ChatInput to use Fluent 2 Textarea and Button components, so that the input area is visually consistent with the rest of the Fluent design system.

#### Acceptance Criteria

1. THE ChatInput SHALL use the Fluent `Textarea` component from `@fluentui/react-components` for the message input field.
2. THE ChatInput SHALL use the Fluent `Button` component from `@fluentui/react-components` for the submit, attach-file, and microphone action buttons.
3. WHEN the ChatInput has no content and no attached files, THE submit Button SHALL be in the `disabled` state.
4. WHEN the user drags files over the ChatInput, THE ChatInput SHALL display a Fluent-styled drag-overlay with a dashed border using `colorBrandStroke1` token.
5. WHEN the microphone is active, THE microphone Button SHALL display the `MicSparkle24Regular` icon and apply the `colorBrandBackground` token as background.
6. THE ChatInput container SHALL use Fluent `tokens.borderRadiusXLarge` for its border radius.
7. WHEN the ChatInput is focused, THE ChatInput border SHALL transition to `colorBrandStroke1` (`#0078D4`).

---

### Requirement 7: Fluent Component Migration — AgentLoader

**User Story:** As a developer, I want AgentLoader to use a Fluent Spinner, so that the loading state is consistent with Fluent 2 design language.

#### Acceptance Criteria

1. THE AgentLoader SHALL use the Fluent `Spinner` component from `@fluentui/react-components` in place of the custom conic-gradient spinning ring.
2. THE AgentLoader SHALL display the Zina-font "A" text mark (20 px, Windows_Blue) centred within or adjacent to the Fluent Spinner, replacing any legacy logo image.
3. WHEN a tool name is active, THE AgentLoader SHALL display the human-readable tool label text using Satoshi Medium at 14 px.
4. THE AgentLoader container SHALL use Fluent surface tokens (`colorNeutralBackground2`) for its background color.

---

### Requirement 8: Fluent Component Migration — SettingsModal

**User Story:** As a developer, I want SettingsModal to use the Fluent Dialog component, so that the modal behaviour and styling are consistent with Fluent 2.

#### Acceptance Criteria

1. THE SettingsModal SHALL use the Fluent `Dialog`, `DialogSurface`, `DialogTitle`, and `DialogBody` components from `@fluentui/react-components`.
2. WHEN the SettingsModal is open, THE SettingsModal SHALL render with a backdrop overlay using Fluent `colorBackgroundOverlay` token.
3. THE SettingsModal tab navigation SHALL use the Fluent `TabList` and `Tab` components.
4. WHEN a tab is selected, THE active Tab SHALL display an underline indicator using `colorBrandStroke1` (`#0078D4`).
5. THE SettingsModal close button SHALL use the Fluent `Button` component with `appearance="subtle"` and the `Dismiss24Regular` icon.

---

### Requirement 9: Responsible AI — Transparency Labels

**User Story:** As a user, I want every AI response clearly labelled as AI-generated, so that I always know when I am reading machine-generated content.

#### Acceptance Criteria

1. WHEN an AI_Response is rendered in the chat area, THE App SHALL display a RAI_Label reading "AI-generated" adjacent to the response bubble.
2. THE RAI_Label SHALL use the `Bot24Regular` or `Sparkle24Regular` icon from `@fluentui/react-icons` alongside the label text.
3. THE RAI_Label text SHALL use Satoshi Medium at 11 px and the Fluent `colorNeutralForeground3` token for color.
4. THE RAI_Label SHALL remain visible for the full lifetime of the AI_Response in the viewport.
5. WHEN the AgentLoader is visible (streaming in progress), THE App SHALL display an "AI is responding…" status indicator using the same RAI_Label styling.

---

### Requirement 10: Responsible AI — Welcome Disclaimer

**User Story:** As a user, I want to see a clear disclaimer when I open a new chat, so that I understand the App's AI capabilities and limitations before I start.

#### Acceptance Criteria

1. WHEN the chat area contains zero messages (greeting state), THE App SHALL display a RAI_Disclaimer below the greeting text.
2. THE RAI_Disclaimer SHALL include the text "Airi can make mistakes. Verify important information." or equivalent scope-communicating copy.
3. THE RAI_Disclaimer SHALL use the `Info24Regular` icon from `@fluentui/react-icons` alongside the disclaimer text.
4. THE RAI_Disclaimer text SHALL use Satoshi Medium at 12 px and the Fluent `colorNeutralForeground3` token.
5. THE RAI_Disclaimer SHALL not obstruct the ChatInput or greeting heading.

---

### Requirement 11: Responsible AI — Feedback Controls

**User Story:** As a user, I want to give thumbs-up or thumbs-down feedback on AI responses, so that I can signal response quality and stay in control of the interaction.

#### Acceptance Criteria

1. WHEN a completed AI_Response is rendered (streaming has ended), THE App SHALL display a Feedback_Control row beneath the response bubble.
2. THE Feedback_Control SHALL contain a thumbs-up button using `ThumbLike24Regular` and a thumbs-down button using `ThumbDislike24Regular` from `@fluentui/react-icons`.
3. THE Feedback_Control buttons SHALL use the Fluent `Button` component with `appearance="subtle"`.
4. WHEN the user activates the thumbs-up button, THE App SHALL visually indicate the selected state by applying `colorBrandBackground` to the button icon.
5. WHEN the user activates the thumbs-down button, THE App SHALL visually indicate the selected state by applying `colorBrandBackground` to the button icon.
6. THE Feedback_Control SHALL be visible on hover of the AI_Response and always visible on touch/pointer-coarse devices.

---

### Requirement 12: Responsible AI — Verify Output Nudge

**User Story:** As a user, I want a gentle reminder to verify AI output, so that I do not over-rely on AI-generated information.

#### Acceptance Criteria

1. WHEN a completed AI_Response is rendered, THE App SHALL display a Verify_Nudge below the Feedback_Control.
2. THE Verify_Nudge SHALL read "Always verify AI responses before acting on them." or equivalent copy.
3. THE Verify_Nudge text SHALL use Satoshi Medium at 11 px and the Fluent `colorNeutralForeground4` token.
4. THE Verify_Nudge SHALL be visible on hover of the AI_Response and always visible on touch/pointer-coarse devices.
5. THE Verify_Nudge SHALL NOT appear while the AI_Response is still streaming.

---

### Requirement 13: Theme Token Migration

**User Story:** As a developer, I want all custom CSS variables replaced with Fluent 2 design tokens, so that the theming system is unified and maintainable.

#### Acceptance Criteria

1. THE App SHALL remove the custom CSS variable declarations (`--bg-app`, `--bg-card`, `--bg-modal`, `--bg-hover`, `--text-primary`, `--text-secondary`, `--text-muted`, `--border-default`, `--border-active`, `--accent-blue`, `--accent-red`) from `ui-components/index.css`.
2. THE App SHALL replace all Tailwind utility classes referencing custom CSS variables (e.g. `bg-bg-card`, `text-text-primary`) with inline Fluent token styles or a Fluent-token-backed CSS variable layer.
3. WHEN the active theme is "Night", THE App SHALL apply `webDarkTheme`-derived Custom_Theme tokens to all surfaces, text, and borders.
4. WHEN the active theme is "Day", THE App SHALL apply `webLightTheme`-derived Custom_Theme tokens to all surfaces, text, and borders.
5. THE scrollbar styling in `ui-components/index.css` SHALL reference Fluent token variables for thumb color (`colorBrandBackground`) and track color (`colorNeutralBackground2`).

---

### Requirement 14: Responsive Layout

**User Story:** As a user, I want the App layout to adapt to different window sizes, so that the interface remains usable whether the window is maximised or resized to a smaller footprint.

#### Acceptance Criteria

1. WHEN the viewport width is 768 px or greater, THE App SHALL display the Sidebar and chat area side-by-side in a horizontal flex layout.
2. WHEN the viewport width is less than 768 px, THE App SHALL display the Sidebar as an overlay drawer and the chat area SHALL occupy the full viewport width.
3. THE ChatInput SHALL have a maximum width of 736 px (`max-w-184` equivalent) and SHALL be horizontally centred within the chat area at all viewport widths.
4. WHEN the viewport width is less than 640 px, THE greeting heading font size SHALL reduce from 36 px to 28 px.
5. THE chat message list SHALL be scrollable vertically and SHALL not cause horizontal overflow at any viewport width above 320 px.

---

### Requirement 15: Prose / Markdown Rendering with Fluent Tokens

**User Story:** As a developer, I want AI response markdown styles to use Fluent tokens, so that code blocks, headings, and lists in AI responses are visually consistent with the Fluent theme.

#### Acceptance Criteria

1. THE App SHALL apply Cabinet_Grotesk to h1, h2, h3 elements within AI_Response prose content.
2. THE App SHALL apply Satoshi to paragraph and list elements within AI_Response prose content.
3. WHEN the active theme is "Night", THE App SHALL apply `colorNeutralBackground3` as the code block background within AI_Response prose.
4. WHEN the active theme is "Day", THE App SHALL apply `colorNeutralBackground2` as the code block background within AI_Response prose.
5. THE inline code style within AI_Response prose SHALL use `colorNeutralBackground3` as background and `colorNeutralForeground1` as text color.
