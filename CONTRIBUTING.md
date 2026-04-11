# Contributing to Airi

Thanks for taking the time to contribute! Here's everything you need to get started.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Making Changes](#making-changes)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)

---

## Code of Conduct

Be respectful. We follow the [Contributor Covenant](https://www.contributor-covenant.org/version/2/1/code_of_conduct/).

---

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/airi.git`
3. Add the upstream remote: `git remote add upstream https://github.com/varshney-ansh/airi.git`

---

## Development Setup

### Prerequisites

- Windows 10/11 x64
- Node.js v18+
- Python 3.10+
- Git

### Steps

```bash
# 1. Install JS dependencies
npm install

# 2. Set up Python environment
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 3. Copy env file and fill in credentials
cp .env.example .env.local

# 4. Start the LLM server (first run downloads the model ~2 GB)
deps\llama-cpp\llama-server.exe -hf Qwen/Qwen3-VL-2B-Instruct-GGUF:Q4_K_M --port 11434 --ctx-size 32768 --jinja

# 5. Run the app
.venv\Scripts\activate
npm run dev
```

---

## Project Structure

| Directory | Purpose |
|---|---|
| `agent-server/` | Python FastAPI agent + all LLM tools |
| `electron/` | Electron main process |
| `src/app/` | Next.js pages (App Router) |
| `src/component/` | App-specific React components |
| `ui-components/` | Reusable design system |
| `installer/` | Inno Setup installer script |
| `scripts/` | Build helpers |
| `deps/` | Bundled binaries (llama.cpp, FlaUI) |

---

## Making Changes

### Frontend (Next.js / React)

- Components live in `src/component/`
- Reusable UI pieces go in `ui-components/`
- Use Fluent UI tokens for colors/spacing where possible
- Tailwind CSS v4 for layout

### Agent / Tools (Python)

- All tools are in `agent-server/agent.py`
- Register new tools with `@register_tool('tool_name')` and extend `BaseTool`
- Keep tool descriptions concise — the LLM reads them
- Add retry logic with `@retry_on_failure` for flaky operations

### Electron

- Main process: `electron/main.js`
- IPC handlers follow the pattern: `ipcMain.handle('action-name', async (_event, data) => {})`
- Preload bridge: `electron/preload.js`

---

## Commit Convention

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add new tool for clipboard access
fix: resolve memory leak in chat context
docs: update setup instructions
chore: bump electron to 41
refactor: simplify agent message builder
style: fix linting warnings in chatMain
```

---

## Pull Request Process

1. Keep PRs focused — one feature or fix per PR
2. Update the README if you add new tools or change setup steps
3. Make sure `npm run dev` works end-to-end before submitting
4. Fill out the PR template
5. Request a review from a maintainer

---

## Reporting Bugs

Open an [issue](https://github.com/varshney-ansh/airi/issues/new?template=bug_report.md) and include:

- Windows version
- Steps to reproduce
- Expected vs actual behavior
- Logs from `%USERPROFILE%\airi-debug.log` (packaged) or terminal (dev)

---

## Requesting Features

Open an [issue](https://github.com/varshney-ansh/airi/issues/new?template=feature_request.md) with:

- What problem it solves
- Proposed solution or API
- Any relevant examples
