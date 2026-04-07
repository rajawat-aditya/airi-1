import os
import sys
import json
import time
import asyncio
import logging
import concurrent.futures
from contextvars import ContextVar
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ── Force UTF-8 output (Windows emoji fix) ────────────────────────────────────
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Set env vars before mem0 import ──────────────────────────────────────────
os.environ.setdefault("OPENAI_API_KEY", "none")
# Disable mem0 telemetry — prevents a second qdrant instance fighting over ~/.mem0 lock
os.environ.setdefault("MEM0_TELEMETRY", "false")

# ── Qwen Agent Framework Imports ─────────────────────────────────────────────
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from qwen_agent.llm.schema import Message, ContentItem

# ── FastAPI Imports ──────────────────────────────────────────────────────────
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse
import shutil

# ── Browser & LLM Imports ────────────────────────────────────────────────────
from browser_use import Agent as BrowserAgent
from browser_use.browser.service import Browser
from langchain_openai import ChatOpenAI

# ── Memory Import ────────────────────────────────────────────────────────────
from mem0 import Memory

# ── Local Windows Module ─────────────────────────────────────────────────────
import win

# ── Model Configuration ──────────────────────────────────────────────────────
modelName = "Qwen/Qwen3-VL-2B-Instruct-GGUF"

# ── Mem0 DB dim-mismatch guard ────────────────────────────────────────────────
_MEM0_DB        = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mem0_db")
_EMBED_DIMS     = 768
_COLLECTION     = "airi_memory"
_EMBED_MODEL    = "unsloth/embeddinggemma-300m-GGUF:Q4_0"
_EMBED_BASE_URL = "http://127.0.0.1:11445/v1"

# ── Wait for embedding server ─────────────────────────────────────────────────
def _wait_for_embedding_server(max_retries=40, delay=0.5):
    import time, requests
    for i in range(max_retries):
        try:
            if requests.get("http://127.0.0.1:11445/health", timeout=1).status_code == 200:
                logger.info("[mem0] Embedding server ready")
                return True
        except Exception:
            pass
        if i == 0:
            logger.info("[mem0] Waiting for embedding server...")
        time.sleep(delay)
    logger.warning("[mem0] Embedding server not ready after timeout")
    return False

def _probe_embedding_dims():
    import requests
    try:
        data = requests.post(
            f"{_EMBED_BASE_URL}/embeddings",
            json={"model": _EMBED_MODEL, "input": "test"},
            timeout=5,
        ).json()
        dims = len(data["data"][0]["embedding"])
        logger.info(f"[mem0] Embedder returns {dims} dims")
        return dims
    except Exception as e:
        logger.warning(f"[mem0] Could not probe dims: {e}")
        return _EMBED_DIMS

def _ensure_qdrant_collection(dims: int):
    """
    Pre-create the qdrant collection with the correct dims BEFORE mem0 touches it.
    If the collection exists with wrong dims, delete and recreate it.
    This prevents mem0 from ever creating a 1536-dim collection.
    """
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    os.makedirs(_MEM0_DB, exist_ok=True)
    client = QdrantClient(path=_MEM0_DB)

    existing = {c.name for c in client.get_collections().collections}

    if _COLLECTION in existing:
        info = client.get_collection(_COLLECTION)
        vectors_config = info.config.params.vectors
        # vectors_config can be a dict (named vectors) or a VectorParams object
        if isinstance(vectors_config, dict):
            current_dims = next(iter(vectors_config.values())).size
        else:
            current_dims = vectors_config.size
        if current_dims != dims:
            logger.warning(f"[mem0] Collection has {current_dims} dims, need {dims}. Recreating.")
            client.delete_collection(_COLLECTION)
            client.create_collection(
                _COLLECTION,
                vectors_config=VectorParams(size=dims, distance=Distance.COSINE),
            )
            logger.info(f"[mem0] Collection recreated with {dims} dims")
        else:
            logger.info(f"[mem0] Collection OK ({dims} dims)")
    else:
        client.create_collection(
            _COLLECTION,
            vectors_config=VectorParams(size=dims, distance=Distance.COSINE),
        )
        logger.info(f"[mem0] Collection created with {dims} dims")

    client.close()

# ── Init sequence ─────────────────────────────────────────────────────────────
_wait_for_embedding_server()
_EMBED_DIMS = _probe_embedding_dims()
_ensure_qdrant_collection(_EMBED_DIMS)

# ── Mem0 Configuration ────────────────────────────────────────────────────────
mem0_config = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": _MEM0_DB,
            "collection_name": _COLLECTION,
            "on_disk": True,
        }
    },
    "llm": {
        "provider": "openai",
        "config": {
            "model": "default",
            "openai_base_url": "http://127.0.0.1:11434/v1",
            "api_key": "none",
            "temperature": 0.1,
            "max_tokens": 2000,
        }
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "model": _EMBED_MODEL,
            "openai_base_url": _EMBED_BASE_URL,
            "api_key": "none",
            "embedding_dims": _EMBED_DIMS,
        }
    }
}

mem_client = Memory.from_config(mem0_config)
logger.info(f"[mem0] Ready — collection '{_COLLECTION}' @ {_EMBED_DIMS} dims")

# ── Request-Scoped Context Variables ─────────────────────────────────────────
_current_user_id:    ContextVar[str] = ContextVar('user_id',    default='default_user')
_current_session_id: ContextVar[str] = ContextVar('session_id', default='default_session')

# ── File Extension Sets ──────────────────────────────────────────────────────
_RAG_EXTS = {'.pdf', '.docx', '.pptx', '.txt', '.csv', '.tsv', '.xlsx', '.xls', '.html'}
_IMG_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# ── Active Sessions Tracker ──────────────────────────────────────────────────
ACTIVE_SESSIONS: Dict[str, Any] = {}

# ── Helper Functions ─────────────────────────────────────────────────────────
def _parse(params):
    """Safely parse params: dict, JSON string, Python repr, or raw primitive."""
    if isinstance(params, (dict, list)):
        return params
    if params is None:
        return {}
    try:
        return json.loads(params)
    except (json.JSONDecodeError, TypeError):
        try:
            import ast
            return ast.literal_eval(params)
        except Exception:
            return params

def _get(params, key, default=None):
    """Safely get a value from parsed params."""
    parsed = _parse(params)
    if isinstance(parsed, dict):
        return parsed.get(key, default)
    return default

def _build_messages(raw_messages: list) -> list[Message]:
    """Convert plain OpenAI-style dicts into proper Qwen-Agent Message objects.

    - image extensions  → ContentItem(image=path)
    - doc extensions    → ContentItem(file=path)  — triggers built-in RAG
    - plain text        → ContentItem(text=text)
    - parses "Attached files: ..." suffix appended by agent-api.js
    """
    result = []
    for m in raw_messages:
        role        = m.get("role", "user")
        raw_content = m.get("content", "")

        # ── List content (already multimodal) ────────────────────────────────
        if isinstance(raw_content, list):
            items = []
            for c in raw_content:
                if not isinstance(c, dict):
                    continue
                if c.get("text"):
                    items.append(ContentItem(text=c["text"]))
                elif c.get("image"):
                    items.append(ContentItem(image=c["image"]))
                elif c.get("file"):
                    items.append(ContentItem(file=c["file"]))
                elif c.get("type") == "text":
                    items.append(ContentItem(text=c.get("text", "")))
                elif c.get("type") == "image_url":
                    img_url = c.get("image_url", {})
                    url = img_url.get("url", "") if isinstance(img_url, dict) else str(img_url)
                    items.append(ContentItem(image=url))
            result.append(Message(role=role, content=items if items else ""))
            continue

        # ── String content ────────────────────────────────────────────────────
        text_part  = str(raw_content) if raw_content else ""
        file_items: list[ContentItem] = []

        if "\nAttached files: " in text_part:
            idx       = text_part.index("\nAttached files: ")
            paths_str = text_part[idx + len("\nAttached files: "):]
            text_part = text_part[:idx].strip()
            for path in [p.strip() for p in paths_str.split(",") if p.strip()]:
                ext = os.path.splitext(path)[1].lower()
                if ext in _IMG_EXTS:
                    file_items.append(ContentItem(image=path))
                else:
                    file_items.append(ContentItem(file=path))

        if file_items:
            items = ([ContentItem(text=text_part)] if text_part else []) + file_items
            result.append(Message(role=role, content=items))
        else:
            result.append(Message(role=role, content=text_part))

    return result

# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Airi Agent API",
    description="Friendly Windows Desktop AI Assistant powered by Qwen3-VL-2B",
    version="2.0.0"
)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── LLM Configuration ────────────────────────────────────────────────────────
llm_cfg = {
    "model": "default",
    "model_server": "http://127.0.0.1:11434/v1",
    "generate_cfg": {
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 20,            # auto-moved to extra_body by qwen-agent
        "presence_penalty": 0.5,
        "max_tokens": 2048,
        "repetition_penalty": 1.1,  # auto-moved to extra_body by qwen-agent
        # enable_thinking must go in extra_body — the OpenAI client rejects it as a top-level kwarg
        "extra_body": {"enable_thinking": True},
    }
}

# ── Chrome Browser Configuration ─────────────────────────────────────────────
CHROME_PATH      = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_USER_DATA = r"C:\Users\anshv\AppData\Local\Google\Chrome\User Data Airi"

class ChromeBrowser(Browser):
    """Launches system Chrome with real user profile + stealth mode."""

    async def _initialize_session(self):
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async

        playwright = await async_playwright().start()
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA,
            executable_path=CHROME_PATH,
            headless=False,
            ignore_default_args=['--enable-automation'],
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1280,1024',
            ],
            viewport={'width': 1280, 'height': 1024},
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
        )

        async def apply_stealth(page):
            await stealth_async(page)

        for page in context.pages:
            await apply_stealth(page)
        context.on("page", lambda page: asyncio.ensure_future(apply_stealth(page)))

        page = context.pages[0] if context.pages else await context.new_page()

        from browser_use.browser.views import BrowserState
        from browser_use.browser.service import BrowserSession
        self.session = BrowserSession(
            playwright=playwright,
            browser=context,
            context=context,
            current_page=page,
            cached_state=BrowserState(
                items=[], selector_map={},
                url=page.url, title=await page.title(),
                screenshot=None, tabs=[],
            ),
        )
        return self.session

# ── TOOLS ────────────────────────────────────────────────────────────────────

@register_tool('browser_automation')
class BrowserAutomationTool(BaseTool):
    description = 'Perform complex browser tasks: navigate websites, fill forms, click buttons, extract info.'
    parameters = [{'name': 'task', 'type': 'string', 'required': True,
                   'description': "Clear description of what to do (e.g., 'Go to google.com and search for python tutorials')"}]

    def call(self, params: str, **kwargs) -> str:
        from browser_use.controller.service import Controller
        p    = _parse(params)
        task = p['task'] if isinstance(p, dict) else str(p)
        logger.info(f"[browser_automation] Starting: {task[:100]}")
        try:
            browser    = ChromeBrowser()
            controller = Controller()
            controller.browser = browser
            llm   = ChatOpenAI(base_url="http://127.0.0.1:11434/v1", model="default", temperature=0.3)
            agent = BrowserAgent(task=task, llm=llm, controller=controller, use_vision=False)
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                result = pool.submit(asyncio.run, agent.run()).result(timeout=300)
            return str(result)
        except concurrent.futures.TimeoutError:
            return json.dumps({"error": "Task timed out after 300 seconds."})
        except Exception as e:
            logger.error(f"[browser_automation] {e}")
            return json.dumps({"error": str(e)})


@register_tool('search_win_app_by_name')
class SearchWinAppByName(BaseTool):
    description = "Step 1: Find AppId for any Windows app by name. Always call before start_app_session."
    parameters = [{'name': 'name', 'type': 'string', 'required': True,
                   'description': "App name (e.g., 'calc', 'notepad', 'spotify')"}]

    def call(self, params: str, **kwargs) -> str:
        p    = _parse(params)
        name = p.get('name', '') if isinstance(p, dict) else str(p)
        logger.info(f"[search_win_app_by_name] Searching: {name}")
        script_dir = os.path.dirname(os.path.abspath(__file__))
        db_path    = os.path.join(script_dir, "context", "installed_apps.json")
        if not os.path.exists(db_path):
            win.get_all_windows_apps_installed_AppIds()
        results = win.find_appId_by_name(name)
        if isinstance(results, str) and "No Apps found" in results:
            win.get_all_windows_apps_installed_AppIds()
            results = win.find_appId_by_name(name)
        if isinstance(results, list):
            return json.dumps(results[:3], ensure_ascii=False)
        return str(results)


@register_tool('start_app_session')
class StartAppSession(BaseTool):
    description = "Step 2: Launch a Windows app using its AppId from search_win_app_by_name."
    parameters = [{'name': 'app_id', 'type': 'string', 'required': True,
                   'description': 'Full AppId (e.g., "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App")'}]

    def call(self, params: str, **kwargs) -> str:
        app_id = _get(params, 'app_id')
        logger.info(f"[start_app_session] Starting: {app_id}")
        driver, message = win.open_win_app_and_start_session(app_id)
        if driver:
            ACTIVE_SESSIONS[app_id] = driver
            return json.dumps({"app_id": app_id, "status": "started", "message": message})
        return json.dumps({"app_id": app_id, "status": "failed", "message": message})


@register_tool('inspect_ui_elements')
class InspectUIElements(BaseTool):
    description = "Step 3: Capture the app's UI element tree. Run AFTER start_app_session."
    parameters = [{'name': 'app_id', 'type': 'string', 'required': True}]

    def call(self, params: str, **kwargs) -> str:
        app_id = _get(params, 'app_id')
        driver = ACTIVE_SESSIONS.get(app_id)
        if not driver:
            return json.dumps({"error": f"No active session for {app_id}. Call start_app_session first."})
        win.get_all_elements_in_current_window(app_id, driver)
        return json.dumps({"app_id": app_id, "status": "inspected", "elements_saved": True})


@register_tool('list_element_names')
class ListElementNames(BaseTool):
    description = "Step 4: Get all clickable element names from the inspected UI."
    parameters = [{'name': 'app_id', 'type': 'string', 'required': True}]

    def call(self, params: str, **kwargs) -> str:
        app_id = _get(params, 'app_id')
        driver = ACTIVE_SESSIONS.get(app_id)
        if not driver:
            return json.dumps({"error": f"No active session for {app_id}"})
        names = win.quickly_lookup_all_element_names_in_current_window(app_id, driver)
        return json.dumps({"app_id": app_id, "element_names": names,
                           "count": len(names) if isinstance(names, list) else 0})


@register_tool('get_element_details')
class GetElementDetails(BaseTool):
    description = "Step 5: Get exact coordinates and ID for a specific element by name."
    parameters = [
        {'name': 'app_id',       'type': 'string', 'required': True},
        {'name': 'element_name', 'type': 'string', 'required': True,
         'description': 'Exact element name from list_element_names'},
    ]

    def call(self, params: str, **kwargs) -> str:
        p = _parse(params)
        if not isinstance(p, dict):
            return json.dumps({"error": "Invalid parameters"})
        app_id       = p.get('app_id', '')
        element_name = p.get('element_name', '')
        driver       = ACTIVE_SESSIONS.get(app_id)
        if not driver:
            return json.dumps({"error": f"No active session for {app_id}"})
        details = win.get_element_by_name(app_id, driver, element_name)
        if details:
            return json.dumps(details)
        return json.dumps({"error": f"Element '{element_name}' not found. Try list_element_names."})


@register_tool('stop_app_session')
class StopAppSession(BaseTool):
    description = "Step 6: Close the app and clean up the session. Always call when done."
    parameters = [{'name': 'app_id', 'type': 'string', 'required': True}]

    def call(self, params: str, **kwargs) -> str:
        app_id = _get(params, 'app_id')
        driver = ACTIVE_SESSIONS.get(app_id)
        if not driver:
            return json.dumps({"status": "no_session", "app_id": app_id})
        success, message = win.close_app_session(driver)
        if success:
            del ACTIVE_SESSIONS[app_id]
        return json.dumps({"app_id": app_id, "status": "closed" if success else "failed", "message": message})


@register_tool('add_memory')
class AddMemory(BaseTool):
    description = "Save a fact or preference about the user to long-term memory. Use whenever the user shares personal info, preferences, or important facts."
    parameters = [
        {'name': 'content', 'type': 'string', 'required': True,
         'description': "The fact or preference to remember (e.g. 'User prefers dark mode', 'User name is Ansh')"},
    ]
    def call(self, params: str, **kwargs) -> str:
        p       = _parse(params)
        content = p.get('content', '') if isinstance(p, dict) else str(p)
        user_id = _current_user_id.get()
        if not content:
            return json.dumps({"error": "content is required"})
        try:
            result = mem_client.add(
                [{"role": "user", "content": content}],
                user_id=user_id,
                infer=False,
            )
            ids = [r.get("id") for r in result.get("results", [])]
            logger.info(f"[add_memory] saved {len(ids)} memories for {user_id}")
            return json.dumps({"saved": True, "ids": ids})
        except Exception as e:
            logger.error(f"[add_memory] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('search_memories')
class SearchMemories(BaseTool):
    description = "Search user's long-term memories for relevant facts. Use at conversation start or when user asks about past preferences."
    parameters = [
        {'name': 'query', 'type': 'string', 'required': True,
         'description': "What to search for (e.g. 'user preferences', 'name', 'work')"},
        {'name': 'limit', 'type': 'integer',
         'description': "Max results to return (default 8)"},
    ]
    def call(self, params: str, **kwargs) -> str:
        p       = _parse(params)
        query   = p.get('query', '') if isinstance(p, dict) else str(p)
        limit   = int(p.get('limit', 8)) if isinstance(p, dict) else 8
        user_id = _current_user_id.get()
        if not query:
            return json.dumps({"error": "query is required"})
        try:
            raw      = mem_client.search(query, user_id=user_id, limit=limit, threshold=0.15)
            items    = raw.get("results", []) if isinstance(raw, dict) else []
            memories = [{"id": r["id"], "memory": r["memory"]} for r in items if r.get("memory")]
            logger.info(f"[search_memories] found {len(memories)} for '{query}'")
            return json.dumps(memories) if memories else json.dumps([])
        except Exception as e:
            logger.error(f"[search_memories] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('get_memories')
class GetMemories(BaseTool):
    description = "Get all stored memories for the current user."
    parameters = [
        {'name': 'limit', 'type': 'integer',
         'description': "Max memories to return (default 50)"},
    ]
    def call(self, params: str, **kwargs) -> str:
        p       = _parse(params)
        limit   = int(p.get('limit', 50)) if isinstance(p, dict) else 50
        user_id = _current_user_id.get()
        try:
            raw      = mem_client.get_all(user_id=user_id, limit=limit)
            items    = raw.get("results", []) if isinstance(raw, dict) else raw
            memories = [{"id": r["id"], "memory": r["memory"]} for r in items if r.get("memory")]
            logger.info(f"[get_memories] {len(memories)} memories for {user_id}")
            return json.dumps(memories)
        except Exception as e:
            logger.error(f"[get_memories] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('get_memory')
class GetMemory(BaseTool):
    description = "Get a single memory by its ID."
    parameters = [
        {'name': 'memory_id', 'type': 'string', 'required': True,
         'description': "The memory ID to retrieve"},
    ]
    def call(self, params: str, **kwargs) -> str:
        p         = _parse(params)
        memory_id = p.get('memory_id', '') if isinstance(p, dict) else str(p)
        if not memory_id:
            return json.dumps({"error": "memory_id is required"})
        try:
            result = mem_client.get(memory_id)
            return json.dumps(result) if result else json.dumps({"error": "Memory not found"})
        except Exception as e:
            logger.error(f"[get_memory] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('update_memory')
class UpdateMemory(BaseTool):
    description = "Update an existing memory by ID with new content."
    parameters = [
        {'name': 'memory_id', 'type': 'string', 'required': True,
         'description': "The memory ID to update"},
        {'name': 'content',   'type': 'string', 'required': True,
         'description': "New content to replace the memory with"},
    ]
    def call(self, params: str, **kwargs) -> str:
        p         = _parse(params)
        memory_id = p.get('memory_id', '') if isinstance(p, dict) else ''
        content   = p.get('content',   '') if isinstance(p, dict) else ''
        if not memory_id or not content:
            return json.dumps({"error": "memory_id and content are required"})
        try:
            mem_client.update(memory_id, content)
            logger.info(f"[update_memory] updated {memory_id}")
            return json.dumps({"updated": True, "memory_id": memory_id})
        except Exception as e:
            logger.error(f"[update_memory] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('delete_memory')
class DeleteMemory(BaseTool):
    description = "Delete a specific memory by ID."
    parameters = [
        {'name': 'memory_id', 'type': 'string', 'required': True,
         'description': "The memory ID to delete"},
    ]
    def call(self, params: str, **kwargs) -> str:
        p         = _parse(params)
        memory_id = p.get('memory_id', '') if isinstance(p, dict) else str(p)
        if not memory_id:
            return json.dumps({"error": "memory_id is required"})
        try:
            mem_client.delete(memory_id)
            logger.info(f"[delete_memory] deleted {memory_id}")
            return json.dumps({"deleted": True, "memory_id": memory_id})
        except Exception as e:
            logger.error(f"[delete_memory] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('delete_all_memories')
class DeleteAllMemories(BaseTool):
    description = "Delete ALL memories for the current user. Use only when user explicitly asks to forget everything."
    parameters = []
    def call(self, params: str, **kwargs) -> str:
        user_id = _current_user_id.get()
        try:
            mem_client.delete_all(user_id=user_id)
            logger.info(f"[delete_all_memories] cleared all for {user_id}")
            return json.dumps({"deleted": True, "user_id": user_id})
        except Exception as e:
            logger.error(f"[delete_all_memories] error: {e}")
            return json.dumps({"error": str(e)})


# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """# 🌸 You are Airi — A Friendly Windows Desktop Assistant

You are Airi, a warm, helpful, and efficient AI companion for Windows users.
Your goal is to make every task feel easy and enjoyable. ✨

## 🎯 Your Personality
- **Friendly & Warm**: Speak naturally, like a helpful friend. Use emojis sparingly (🌸✨✅) to add warmth.
- **Clear & Simple**: Explain steps in plain language. Avoid technical jargon unless asked.
- **Proactive & Thorough**: Anticipate follow-up needs. Confirm before destructive actions.
- **Patient & Encouraging**: Never make users feel silly for asking. Celebrate small wins!

## 🛠️ Your Capabilities
- **Windows Apps**: Open, control, and automate any installed application
- **Web Browsing**: Navigate websites, fill forms, extract information
- **Documents & Images**: Analyze uploaded files automatically (PDF, Word, images, etc.)
- **Memory**: Remember user preferences and important details across sessions
- **Web Search**: Find current information when needed

## 📋 Golden Rules
1. **ONE tool at a time** — Call one tool, wait for result, then proceed.
2. **Always search before launching** — Use `search_win_app_by_name` before `start_app_session`.
3. **Always inspect before interacting** — Use `inspect_ui_elements` before clicking/typing in apps.
4. **Save important info** — When user shares preferences/facts, use `add_memory`.
5. **Check memory first** — At conversation start, use `search_memories` to retrieve relevant context.
6. **Files are automatic** — Uploaded documents/images are analyzed directly (no tool needed).
7. **Clean up sessions** — Call `stop_app_session` when app tasks are complete.
8. **Be honest about limits** — If something fails, explain clearly and suggest alternatives.

## 🔧 Available Tools
| Tool | When to Use |
|------|-------------|
| `search_win_app_by_name(name)` | First step to find any app |
| `start_app_session(app_id)` | Launch app after getting AppId |
| `inspect_ui_elements(app_id)` | See what's clickable in the app |
| `list_element_names(app_id)` | Get list of element names |
| `get_element_details(app_id, element_name)` | Find exact position of element |
| `stop_app_session(app_id)` | Close app when done |
| `browser_automation(task)` | Web tasks (search, forms, navigation) |
| `web_search(query)` | Find current info online |
| `add_memory(content)` | Save a fact about the user |
| `search_memories(query)` | Find relevant past memories |
| `get_memories()` | List all user memories |
| `get_memory(memory_id)` | Get a specific memory by ID |
| `update_memory(memory_id, content)` | Update an existing memory |
| `delete_memory(memory_id)` | Delete a specific memory |
| `delete_all_memories()` | Clear all user memories |

## 🔄 Typical Workflow
**For App Tasks:**
1. `search_win_app_by_name` → 2. `start_app_session` → 3. `inspect_ui_elements` → 4. `list_element_names` → 5. `get_element_details` → 6. Interact → 7. `stop_app_session`

**For Web Tasks:**
`browser_automation(task)` handles the full flow internally.

**For Memory:**
- Save new fact: `add_memory(content=<fact>)`
- Find relevant context: `search_memories(query=<topic>)`
- List all: `get_memories()`
- Update: `update_memory(memory_id=<id>, content=<new text>)`
- Delete one: `delete_memory(memory_id=<id>)`
"""

# ── Agent Initialization ─────────────────────────────────────────────────────
airi = Assistant(
    llm=llm_cfg,
    system_message=SYSTEM_PROMPT,
    function_list=[
        'browser_automation',
        'search_win_app_by_name', 'start_app_session',
        'inspect_ui_elements', 'list_element_names', 'get_element_details',
        'stop_app_session', 'web_search',
        'add_memory', 'search_memories', 'get_memories', 'get_memory',
        'update_memory', 'delete_memory', 'delete_all_memories',
    ]
)

# ── FastAPI Endpoints ────────────────────────────────────────────────────────

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    data        = await request.json()
    raw_messages = data.get("messages", [])
    user_id     = data.get("user_id",    "default_user")
    session_id  = data.get("session_id", "default_session")

    _current_user_id.set(user_id)
    _current_session_id.set(session_id)

    messages = _build_messages(raw_messages)

    def stream_gen():
        import re as _re
        _current_user_id.set(user_id)
        _current_session_id.set(session_id)

        prev_content  = ""
        chunk_id      = f"chatcmpl-{int(time.time())}"
        seen_tool_ids = set()

        def _tool_event(tool_name: str, detail: str = "") -> str:
            """Emit a custom SSE event so the frontend can show the AgentLoader status."""
            payload = json.dumps({"tool": tool_name, "detail": detail}, ensure_ascii=False)
            return f"event: tool_call\ndata: {payload}\n\n"

        try:
            for response in airi.run(messages):
                if not response:
                    continue

                # ── Detect tool calls / tool results in this response snapshot ──
                for m in response:
                    role = m.get("role", "")

                    # assistant message that contains a function_call
                    if role == "assistant":
                        content = m.get("content") or ""
                        # Qwen-agent stores tool calls as list items with type "function"
                        if isinstance(content, list):
                            for item in content:
                                if not isinstance(item, dict):
                                    continue
                                fn = item.get("function") or item.get("name") or ""
                                call_id = item.get("id") or item.get("call_id") or fn
                                if fn and call_id not in seen_tool_ids:
                                    seen_tool_ids.add(call_id)
                                    yield _tool_event(fn)

                    # tool result message — the tool already ran
                    elif role == "tool":
                        tool_name = m.get("name") or m.get("tool_call_id") or "tool"
                        call_id   = m.get("tool_call_id") or tool_name
                        result_id = f"result_{call_id}"
                        if result_id not in seen_tool_ids:
                            seen_tool_ids.add(result_id)
                            yield _tool_event(tool_name, "done")

                # ── Stream assistant text delta ────────────────────────────────
                assistant_msgs = [m for m in response if m.get("role") == "assistant"]
                if not assistant_msgs:
                    continue
                last = assistant_msgs[-1]

                raw = last.get("content") or ""
                if isinstance(raw, list):
                    full_content = " ".join(
                        c.get("text", "") for c in raw
                        if isinstance(c, dict) and c.get("text")
                    )
                else:
                    full_content = str(raw)

                # Strip <think>...</think> blocks
                if "<think>" in full_content:
                    full_content = _re.sub(r"<think>.*?</think>", "", full_content, flags=_re.DOTALL).strip()

                delta = full_content[len(prev_content):]
                prev_content = full_content
                if not delta:
                    continue

                chunk = {
                    "id": chunk_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": modelName,
                    "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

            # Final chunk
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': int(time.time()), 'model': modelName, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[chat_completions] stream error: {e}")
            err = {"id": chunk_id, "object": "chat.completion.chunk", "created": int(time.time()),
                   "model": modelName,
                   "choices": [{"index": 0, "delta": {"content": f"\n\n⚠️ Error: {e}"}, "finish_reason": "error"}]}
            yield f"data: {json.dumps(err)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_gen(), media_type="text/event-stream")


USER_STUFF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_stuff")
os.makedirs(USER_STUFF_DIR, exist_ok=True)

@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    saved = []
    for f in files:
        dest = os.path.join(USER_STUFF_DIR, f.filename)
        base, ext = os.path.splitext(f.filename)
        counter = 1
        while os.path.exists(dest):
            dest = os.path.join(USER_STUFF_DIR, f"{base}_{counter}{ext}")
            counter += 1
        with open(dest, "wb") as out:
            shutil.copyfileobj(f.file, out)
        saved.append(dest)
        logger.info(f"[upload] Saved: {dest}")
    return {"paths": saved, "count": len(saved)}


_whisper_model = None

def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        from huggingface_hub import try_to_load_from_cache
        # Check if model is already in local cache
        cached = try_to_load_from_cache("Systran/faster-whisper-tiny", "model.bin")
        is_cached = cached is not None and not isinstance(cached, type(None))
        if is_cached:
            # Fully offline — no network calls at all
            os.environ["HF_HUB_OFFLINE"] = "1"
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8", local_files_only=True)
            logger.info("[whisper] Loaded from local cache (offline)")
        else:
            logger.info("[whisper] First run — downloading tiny model (~75MB)...")
            _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
            logger.info("[whisper] Model downloaded and cached")
    return _whisper_model

def _prewarm_whisper():
    """Load whisper in background at startup so first transcribe call is instant."""
    import threading
    def _load():
        try:
            _get_whisper()
        except Exception as e:
            logger.warning(f"[whisper] Pre-warm failed: {e}")
    threading.Thread(target=_load, daemon=True).start()

_prewarm_whisper()

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe a single audio blob (fallback for non-streaming use)."""
    import tempfile
    try:
        suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        model = _get_whisper()
        segments, _ = model.transcribe(tmp_path, language="en", beam_size=1, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        os.unlink(tmp_path)
        return {"text": text}
    except Exception as e:
        logger.error(f"[transcribe] {e}")
        return {"text": "", "error": str(e)}


from fastapi import WebSocket, WebSocketDisconnect
import wave, struct, io, threading, queue

@app.websocket("/ws/transcribe")
async def ws_transcribe(websocket: WebSocket):
    """
    Real-time transcription over WebSocket.
    Client sends raw PCM16 mono 16kHz audio chunks as binary frames.
    Server responds with JSON: {"type": "interim"|"final", "text": "..."}
    Client sends text frame "stop" to end the session.
    """
    await websocket.accept()
    logger.info("[ws_transcribe] Client connected")

    model = _get_whisper()
    audio_queue: queue.Queue = queue.Queue()
    result_queue: queue.Queue = queue.Queue()
    running = True

    SAMPLE_RATE   = 16000
    CHANNELS      = 1
    SAMPLE_WIDTH  = 2          # int16
    # Accumulate ~1.2s of audio before transcribing (balance latency vs accuracy)
    CHUNK_SAMPLES = int(SAMPLE_RATE * 1.2)

    def transcribe_worker():
        """Background thread: drains audio_queue, transcribes, pushes results."""
        buf = b""
        while running:
            try:
                chunk = audio_queue.get(timeout=0.3)
                if chunk is None:
                    break
                buf += chunk
                # Transcribe when we have enough samples
                if len(buf) >= CHUNK_SAMPLES * SAMPLE_WIDTH:
                    pcm = buf
                    buf = b""
                    try:
                        # Wrap PCM in a WAV container so faster-whisper can read it
                        wav_io = io.BytesIO()
                        with wave.open(wav_io, "wb") as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(SAMPLE_WIDTH)
                            wf.setframerate(SAMPLE_RATE)
                            wf.writeframes(pcm)
                        wav_io.seek(0)
                        segments, _ = model.transcribe(
                            wav_io, language="en", beam_size=1,
                            vad_filter=True, vad_parameters={"min_silence_duration_ms": 300}
                        )
                        text = " ".join(s.text.strip() for s in segments).strip()
                        if text:
                            result_queue.put({"type": "interim", "text": text})
                    except Exception as e:
                        logger.error(f"[ws_transcribe] transcribe error: {e}")
            except queue.Empty:
                # Flush remaining buffer if it has meaningful audio
                if len(buf) > SAMPLE_RATE * SAMPLE_WIDTH * 0.3:
                    pcm = buf
                    buf = b""
                    try:
                        wav_io = io.BytesIO()
                        with wave.open(wav_io, "wb") as wf:
                            wf.setnchannels(CHANNELS)
                            wf.setsampwidth(SAMPLE_WIDTH)
                            wf.setframerate(SAMPLE_RATE)
                            wf.writeframes(pcm)
                        wav_io.seek(0)
                        segments, _ = model.transcribe(
                            wav_io, language="en", beam_size=1,
                            vad_filter=True, vad_parameters={"min_silence_duration_ms": 300}
                        )
                        text = " ".join(s.text.strip() for s in segments).strip()
                        if text:
                            result_queue.put({"type": "final", "text": text})
                    except Exception as e:
                        logger.error(f"[ws_transcribe] flush error: {e}")

    worker = threading.Thread(target=transcribe_worker, daemon=True)
    worker.start()

    async def send_results():
        while True:
            await asyncio.sleep(0.05)
            while not result_queue.empty():
                msg = result_queue.get_nowait()
                try:
                    await websocket.send_json(msg)
                except Exception:
                    return

    send_task = asyncio.create_task(send_results())

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if "bytes" in msg and msg["bytes"]:
                audio_queue.put(msg["bytes"])
            elif "text" in msg and msg["text"] == "stop":
                break
    except WebSocketDisconnect:
        pass
    finally:
        running = False
        audio_queue.put(None)
        send_task.cancel()
        worker.join(timeout=2)
        logger.info("[ws_transcribe] Client disconnected")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": modelName,
        "agent": "Airi",
        "version": "2.0.0",
        "thinking_enabled": llm_cfg["generate_cfg"].get("extra_body", {}).get("enable_thinking", False),
        "active_sessions": len(ACTIVE_SESSIONS),
        "timestamp": time.time(),
    }


_IMG_EXTS_SET = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.svg'}
_DOC_EXTS_SET = {'.pdf', '.doc', '.docx', '.txt', '.csv', '.xlsx', '.xls', '.json', '.pptx', '.html', '.md'}

@app.get("/library")
async def list_library():
    """List all files in user_stuff, split into documents and media."""
    docs, media = [], []
    if not os.path.exists(USER_STUFF_DIR):
        return {"documents": [], "media": []}
    for fname in sorted(os.listdir(USER_STUFF_DIR)):
        fpath = os.path.join(USER_STUFF_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        ext  = os.path.splitext(fname)[1].lower()
        stat = os.stat(fpath)
        info = {
            "name": fname,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "ext": ext.lstrip("."),
        }
        if ext in _IMG_EXTS_SET:
            media.append(info)
        elif ext in _DOC_EXTS_SET:
            docs.append(info)
        else:
            docs.append(info)
    return {"documents": docs, "media": media}


@app.delete("/library/{filename}")
async def delete_library_file(filename: str):
    """Delete a file from user_stuff by name."""
    # Sanitize — no path traversal
    safe_name = os.path.basename(filename)
    fpath = os.path.join(USER_STUFF_DIR, safe_name)
    if not os.path.exists(fpath):
        return {"success": False, "error": "File not found"}
    try:
        os.remove(fpath)
        logger.info(f"[library] Deleted: {safe_name}")
        return {"success": True}
    except Exception as e:
        logger.error(f"[library] Delete error: {e}")
        return {"success": False, "error": str(e)}


from fastapi.responses import FileResponse
from pydantic import BaseModel

@app.get("/library/file/{filename}")
async def serve_library_file(filename: str):
    """Serve a file from user_stuff for inline preview."""
    safe_name = os.path.basename(filename)
    fpath = os.path.join(USER_STUFF_DIR, safe_name)
    if not os.path.exists(fpath):
        return {"error": "File not found"}
    return FileResponse(fpath)


# ── Memory endpoints ──────────────────────────────────────────────────────────

@app.get("/memories")
async def get_memories(user_id: str = "default_user"):
    try:
        raw = mem_client.get_all(user_id=user_id, limit=200)
        results = raw.get("results", []) if isinstance(raw, dict) else raw
        return {"memories": results}
    except Exception as e:
        logger.error(f"[memories] get error: {e}")
        return {"memories": [], "error": str(e)}


@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    try:
        mem_client.delete(memory_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"[memories] delete error: {e}")
        return {"success": False, "error": str(e)}


class MemoryUpdateBody(BaseModel):
    data: str

@app.put("/memories/{memory_id}")
async def update_memory(memory_id: str, body: MemoryUpdateBody):
    try:
        mem_client.update(memory_id, body.data)
        return {"success": True}
    except Exception as e:
        logger.error(f"[memories] update error: {e}")
        return {"success": False, "error": str(e)}


@app.on_event("shutdown")
async def cleanup_sessions():
    logger.info("[shutdown] Cleaning up active sessions...")
    for app_id, driver in list(ACTIVE_SESSIONS.items()):
        try:
            win.close_app_session(driver)
        except Exception as e:
            logger.error(f"[shutdown] Error closing {app_id}: {e}")
    ACTIVE_SESSIONS.clear()


if __name__ == "__main__":
    import uvicorn
    print("""
╔═══════════════════════════════════════════════════════════╗
║                    🌸 Airi Agent v2.0                     ║
║          Friendly Windows Desktop AI Assistant            ║
║                                                           ║
║  Model  : Qwen3-VL-2B-Instruct-GGUF                       ║
║  Thinking: Enabled                                        ║
║  Endpoint: http://127.0.0.1:11435                         ║
╚═══════════════════════════════════════════════════════════╝
""")
    uvicorn.run(app, host="127.0.0.1", port=11435, log_level="info", access_log=True)
