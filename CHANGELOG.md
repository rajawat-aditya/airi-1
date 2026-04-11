# Changelog

All notable changes to Airi are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.1.0] — 2026-04-11

### Added
- Initial release of Airi — AI Desktop Assistant
- Natural language chat with Qwen3-VL-2B running locally via llama.cpp
- Windows app automation via FlaUI (UIA3) — launch, inspect, interact
- Browser automation via Playwright
- File system operations with path aliases (desktop, downloads, documents)
- Persistent local memory with mem0 + Qdrant
- Document and image RAG (PDF, DOCX, PPTX, images)
- SearXNG-powered local web search
- Auth0 authentication with onboarding flow
- MongoDB Atlas sync + local electron-store fallback
- Inno Setup installer for Windows (Microsoft Store EXE submission compatible)
- Settings panel — swap LLM provider, toggle thinking mode, change theme
- Fluent UI design system with dark/light themes
- Auto model download on first launch
- Bundled Python agent via PyInstaller
