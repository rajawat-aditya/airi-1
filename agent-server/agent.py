import os
import sys
import json
import time
import asyncio
import logging
import concurrent.futures
from contextvars import ContextVar
from typing import Optional, List, Dict, Any, Callable
from functools import wraps
from threading import Lock

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
os.environ.setdefault("MEM0_TELEMETRY", "false")

# ── Qwen Agent Framework Imports ─────────────────────────────────────────────
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from qwen_agent.llm.schema import Message, ContentItem

# ── FastAPI Imports ──────────────────────────────────────────────────────────
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import shutil

# ── Memory Import ────────────────────────────────────────────────────────────
from mem0 import Memory

# ── FlaUI Engine ──────────────────────────────────────────────────────────────
from flaui import engine

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
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    os.makedirs(_MEM0_DB, exist_ok=True)
    client = QdrantClient(path=_MEM0_DB)

    existing = {c.name for c in client.get_collections().collections}

    if _COLLECTION in existing:
        info = client.get_collection(_COLLECTION)
        vectors_config = info.config.params.vectors
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
    """Convert plain OpenAI-style dicts into proper Qwen-Agent Message objects."""
    result = []
    for m in raw_messages:
        role        = m.get("role", "user")
        raw_content = m.get("content", "")

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
    version="2.1.0"
)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# ── Settings persistence ──────────────────────────────────────────────────────
_SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

def _load_settings() -> dict:
    defaults = {"model_server": "http://127.0.0.1:11434/v1", "model": "default", "api_key": "none", "thinking_enabled": True}
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH) as f:
                saved = json.load(f)
            defaults.update(saved)
            logger.info(f"[settings] Loaded from {_SETTINGS_PATH}")
        except Exception as e:
            logger.warning(f"[settings] Could not load settings.json: {e}")
    return defaults

def _save_settings(s: dict):
    try:
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(s, f, indent=2)
    except Exception as e:
        logger.warning(f"[settings] Could not save settings.json: {e}")

_settings = _load_settings()

# ── LLM Configuration ────────────────────────────────────────────────────────
llm_cfg = {
    "model":        _settings["model"],
    "model_server": _settings["model_server"],
    "api_key":      _settings.get("api_key", "none"),
    "generate_cfg": {
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 20,
        "presence_penalty": 0.5,
        "max_tokens": 2048,
        "repetition_penalty": 1.1,
        "extra_body": {"enable_thinking": _settings.get("thinking_enabled", True)},
    }
}

# ── Retry Decorator for Robust Tool Calls ─────────────────────────────────────
def retry_on_failure(max_retries=3, delay=1.0, backoff=2.0, exceptions=(Exception,)):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(f"[retry] {func.__name__} failed (attempt {attempt+1}/{max_retries}): {e}")
                        time.sleep(current_delay)
                        current_delay *= backoff
            logger.error(f"[retry] {func.__name__} failed after {max_retries} attempts: {last_error}")
            raise last_error
        return wrapper
    return decorator

# ── TOOL CALL VALIDATION ──────────────────────────────────────────────────────
def _validate_tool_call(tool_name: str, params: dict) -> tuple[bool, str]:
    """Validate tool parameters before execution."""
    if tool_name == 'windows_launch':
        if not params.get('app'):
            return False, "app is required for windows_launch"
    elif tool_name == 'windows_inspect':
        if not params.get('app'):
            return False, "app is required for windows_inspect"
    elif tool_name == 'windows_do':
        if not params.get('app'):
            return False, "app is required for windows_do"
        actions = params.get('actions', [])
        if not isinstance(actions, list) or len(actions) == 0:
            return False, "actions must be a non-empty list"
    elif tool_name == 'file_op':
        if not params.get('op'):
            return False, "op is required for file_op"
        if not params.get('path'):
            return False, "path is required for file_op"
    elif tool_name == 'add_memory':
        if not params.get('content'):
            return False, "content is required for add_memory"
    elif tool_name == 'search_memories':
        if not params.get('query'):
            return False, "query is required for search_memories"
    elif tool_name == 'get_memory':
        if not params.get('memory_id'):
            return False, "memory_id is required for get_memory"
    elif tool_name == 'update_memory':
        if not params.get('memory_id'):
            return False, "memory_id is required for update_memory"
        if not params.get('content'):
            return False, "content is required for update_memory"
    elif tool_name == 'delete_memory':
        if not params.get('memory_id'):
            return False, "memory_id is required for delete_memory"
    return True, ""

# ── CONTEXT WINDOW MANAGEMENT ─────────────────────────────────────────────────
class ContextManager:
    """Manages long conversation context with summarization."""
    
    def __init__(self, max_tokens=16000, summary_threshold=0.8):
        self.max_tokens = max_tokens
        self.summary_threshold = summary_threshold
        self._lock = Lock()
        self._message_history: List[Dict] = []
        self._summary: Optional[str] = None
    
    def add_message(self, message: Dict):
        with self._lock:
            self._message_history.append(message)
    
    def get_context(self) -> List[Dict]:
        with self._lock:
            if self._summary:
                return [{"role": "system", "content": f"Previous conversation summary: {self._summary}"}] + [
                    m for m in self._message_history[-50:]  # Keep last 50 messages
                ]
            return self._message_history[-100:]  # Keep last 100 messages without summary
    
    def should_summarize(self) -> bool:
        with self._lock:
            # Simple token estimation: ~4 chars per token
            total_chars = sum(len(str(m.get("content", ""))) for m in self._message_history)
            return total_chars > self.max_tokens * 4 * self.summary_threshold
    
    def summarize(self):
        """Create a summary of old messages to reduce context size."""
        with self._lock:
            if len(self._message_history) < 10:
                return
            
            # Keep recent messages, summarize older ones
            recent = self._message_history[-10:]
            old = self._message_history[:-10]
            
            # Build summary prompt
            summary_prompt = "Summarize this conversation history in 3-5 sentences:\n"
            for m in old:
                role = m.get("role", "unknown")
                content = m.get("content", "")
                summary_prompt += f"\n{role}: {content[:500]}..."
            
            self._summary = summary_prompt
            self._message_history = recent
            logger.info(f"[context] Summarized {len(old)} messages into summary")

_context_manager = ContextManager()

# ── TOOL REGISTRATION ─────────────────────────────────────────────────────────
@register_tool('windows_launch')
class WindowsLaunch(BaseTool):
    description = 'Launch a Windows app by name. Returns already_running if already open.'
    parameters = [
        {'name': 'app',  'type': 'string', 'required': True,  'description': 'App name e.g. "chrome", "excel", "cmd"'},
        {'name': 'args', 'type': 'string', 'required': False, 'description': 'Optional command-line arguments'},
    ]
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def call(self, params: str, **kwargs) -> str:
        p    = _parse(params)
        app  = p.get('app',  '') if isinstance(p, dict) else str(p)
        args = p.get('args', '') if isinstance(p, dict) else ''
        logger.info(f"[windows_launch] {app}")
        if not app:
            return json.dumps({"status": "error", "detail": "app is required"})
        try:
            result = engine.launch_app(app, args or '')
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[windows_launch] {e}")
            return json.dumps({"status": "error", "detail": str(e)})


@register_tool('windows_inspect')
class WindowsInspect(BaseTool):
    description = 'Return compact UI element tree for a running app. Use to discover element names/IDs before windows_do.'
    parameters = [
        {'name': 'app',          'type': 'string',  'required': True,  'description': 'App name e.g. "chrome", "excel"'},
        {'name': 'depth',        'type': 'integer', 'required': False, 'description': 'Tree depth (default 4)'},
        {'name': 'filter_types', 'type': 'string',  'required': False, 'description': 'Comma-separated control types e.g. "Button,Edit"'},
    ]
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def call(self, params: str, **kwargs) -> str:
        p            = _parse(params)
        app          = p.get('app',          '') if isinstance(p, dict) else str(p)
        depth        = int(p.get('depth') or 4)  if isinstance(p, dict) else 4
        filter_types = p.get('filter_types', '') if isinstance(p, dict) else ''
        logger.info(f"[windows_inspect] {app}")
        try:
            result = engine.inspect_window(app, depth=depth, filter_types=filter_types)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[windows_inspect] {e}")
            return json.dumps({"error": str(e)})


@register_tool('windows_do')
class WindowsDo(BaseTool):
    description = 'Execute a batch of UI actions on a Windows app. Primary interaction tool.'
    parameters = [
        {'name': 'app',     'type': 'string', 'required': True, 'description': 'Target app name'},
        {'name': 'actions', 'type': 'array',  'required': True, 'description': 'List of action dicts. Each has "action" key plus action-specific fields.'},
    ]
    
    @retry_on_failure(max_retries=3, delay=0.5)
    def call(self, params: str, **kwargs) -> str:
        p       = _parse(params)
        app     = p.get('app',     '') if isinstance(p, dict) else ''
        actions = p.get('actions', []) if isinstance(p, dict) else []
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except Exception:
                try:
                    import ast
                    actions = ast.literal_eval(actions)
                except Exception:
                    return json.dumps({"error": "actions must be a JSON array"})
        logger.info(f"[windows_do] {app} — {len(actions)} actions")
        if not app:
            return json.dumps({"error": "app is required"})
        try:
            result = engine.execute_batch(app, actions)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[windows_do] {e}")
            return json.dumps({"error": str(e)})


# ── Path alias resolver ───────────────────────────────────────────────────────
def _resolve_path(path: str) -> str:
    """Resolve special aliases to real Windows paths."""
    aliases = {
        "desktop":   os.path.join(os.path.expanduser("~"), "Desktop"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "pictures":  os.path.join(os.path.expanduser("~"), "Pictures"),
    }
    return aliases.get(path.lower().strip(), path)


@register_tool('file_op')
class FileOp(BaseTool):
    description = 'File system operations: list, open, copy, move, delete, create_folder, search. Supports desktop/downloads/documents/pictures aliases.'
    parameters = [
        {'name': 'op',      'type': 'string', 'required': True,  'description': 'Operation: list|open|copy|move|delete|create_folder|search'},
        {'name': 'path',    'type': 'string', 'required': True,  'description': 'File or folder path, or alias: desktop/downloads/documents/pictures'},
        {'name': 'dest',    'type': 'string', 'required': False, 'description': 'Destination path for copy/move'},
        {'name': 'pattern', 'type': 'string', 'required': False, 'description': 'Glob pattern or name fragment for search'},
    ]

    @retry_on_failure(max_retries=2, delay=0.3)
    def call(self, params: str, **kwargs) -> str:
        import glob as _glob, shutil as _shutil
        p       = _parse(params)
        op      = p.get('op',      '') if isinstance(p, dict) else str(p)
        path    = _resolve_path(p.get('path', '') if isinstance(p, dict) else '')
        dest    = _resolve_path(p.get('dest', '') if isinstance(p, dict) else '')
        pattern = p.get('pattern', '') if isinstance(p, dict) else ''
        logger.info(f"[file_op] {op} {path}")
        try:
            if op == 'list':
                if not os.path.exists(path):
                    return json.dumps({"error": f"Path not found: {path}"})
                items = []
                for name in sorted(os.listdir(path)):
                    full = os.path.join(path, name)
                    stat = os.stat(full)
                    items.append({
                        "name":     name,
                        "type":     "folder" if os.path.isdir(full) else "file",
                        "size":     stat.st_size if os.path.isfile(full) else None,
                        "modified": stat.st_mtime,
                        "ext":      os.path.splitext(name)[1].lstrip('.') if os.path.isfile(full) else None,
                    })
                return json.dumps(items)

            elif op == 'open':
                if not os.path.exists(path):
                    return json.dumps({"error": f"Path not found: {path}"})
                os.startfile(path)
                return json.dumps({"status": "opened", "path": path})

            elif op == 'copy':
                if not dest:
                    return json.dumps({"error": "dest is required for copy"})
                if os.path.isdir(path):
                    _shutil.copytree(path, dest)
                else:
                    _shutil.copy2(path, dest)
                return json.dumps({"status": "copied", "from": path, "to": dest})

            elif op == 'move':
                if not dest:
                    return json.dumps({"error": "dest is required for move"})
                _shutil.move(path, dest)
                return json.dumps({"status": "moved", "from": path, "to": dest})

            elif op == 'delete':
                if not os.path.exists(path):
                    return json.dumps({"error": f"Path not found: {path}"})
                if os.path.isdir(path):
                    _shutil.rmtree(path)
                else:
                    os.remove(path)
                return json.dumps({"status": "deleted", "path": path})

            elif op == 'create_folder':
                os.makedirs(path, exist_ok=True)
                return json.dumps({"status": "created", "path": path})

            elif op == 'search':
                base    = path if path else os.path.expanduser("~")
                pat     = pattern or '*'
                if '*' in pat or '?' in pat:
                    matches = _glob.glob(os.path.join(base, '**', pat), recursive=True)
                else:
                    matches = [
                        os.path.join(root, f)
                        for root, dirs, files in os.walk(base)
                        for f in files + dirs
                        if pat.lower() in f.lower()
                    ]
                return json.dumps(matches[:100])

            else:
                return json.dumps({"error": f"Unknown op: {op}. Use list|open|copy|move|delete|create_folder|search"})

        except Exception as e:
            logger.error(f"[file_op] {e}")
            return json.dumps({"error": str(e)})
@register_tool('list_installed_apps')
class ListInstalledApps(BaseTool):
    description = 'List installed Windows apps. Use to find app names before windows_launch.'
    parameters = []

    @retry_on_failure(max_retries=2, delay=0.5)
    def call(self, params: str, **kwargs) -> str:
        import subprocess
        logger.info("[list_installed_apps] Enumerating apps")
        try:
            result = subprocess.run(
                ['powershell', '-NoProfile', '-Command',
                 'Get-StartApps | Select-Object Name, AppID | ConvertTo-Json'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                raw = json.loads(result.stdout)
                if isinstance(raw, dict):
                    raw = [raw]
                apps = [{"name": a.get("Name", ""), "app_id": a.get("AppID", "")} for a in raw if a.get("Name")]
                logger.info(f"[list_installed_apps] Found {len(apps)} apps via PowerShell")
                return json.dumps(apps)
        except Exception as e:
            logger.warning(f"[list_installed_apps] PowerShell failed: {e}")

        try:
            import glob as _glob
            start_menu = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu")
            lnk_files  = _glob.glob(os.path.join(start_menu, "**", "*.lnk"), recursive=True)
            apps = [{"name": os.path.splitext(os.path.basename(f))[0], "app_id": f} for f in lnk_files]
            logger.info(f"[list_installed_apps] Found {len(apps)} apps via Start Menu scan")
            return json.dumps(apps)
        except Exception as e:
            logger.error(f"[list_installed_apps] fallback failed: {e}")
            return json.dumps({"error": str(e)})


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
- **Windows Apps**: Open, control, and automate any installed application via UI automation
- **File Management**: List, open, copy, move, delete files and folders
- **Documents & Images**: Analyze uploaded files automatically (PDF, Word, images, etc.)
- **Memory**: Remember user preferences and important details across sessions
- **Web Search**: Find current information when needed

## 📋 Golden Rules
1. **ONE tool at a time** — Call one tool, wait for result, then proceed.
2. **Launch before interacting** — Use `windows_launch` if the app isn't open yet.
3. **Inspect when unsure** — Use `windows_inspect` to discover element names before `windows_do`.
4. **Batch actions** — Use `windows_do` with multiple actions in one call to minimize round-trips.
5. **Read screen, not screenshots** — Use `read_screen` action in `windows_do` to read window content; it's faster than screenshots.
6. **Save important info** — When user shares preferences/facts, use `add_memory`.
7. **Check memory first** — At conversation start, use `search_memories` to retrieve relevant context.
8. **Files are automatic** — Uploaded documents/images are analyzed directly (no tool needed).
9. **Be honest about limits** — If something fails, explain clearly and suggest alternatives.

## 🔧 Available Tools
| Tool | When to Use |
|------|-------------|
| `windows_launch(app, args?)` | Open a Windows app by name |
| `windows_inspect(app, depth?, filter_types?)` | Discover UI elements in a running app |
| `windows_do(app, actions[])` | Execute UI actions (click, type, key, scroll, read, etc.) |
| `file_op(op, path, dest?, pattern?)` | File operations: list/open/copy/move/delete/create_folder/search |
| `list_installed_apps()` | List all installed apps to find the right name |
| `web_search(query)` | Find current info online |
| `add_memory(content)` | Save a fact about the user |
| `search_memories(query)` | Find relevant past memories |
| `get_memories()` | List all user memories |
| `get_memory(memory_id)` | Get a specific memory by ID |
| `update_memory(memory_id, content)` | Update an existing memory |
| `delete_memory(memory_id)` | Delete a specific memory |
| `delete_all_memories()` | Clear all user memories |

## 🔄 Typical Workflows

**For App Tasks:**
1. `windows_launch(app)` — open the app if not running
2. `windows_inspect(app)` — discover element names (only if needed)
3. `windows_do(app, actions[])` — perform all interactions in one batch

**For File Tasks:**
- List files: `file_op(op=list, path=desktop)`
- Open a file: `file_op(op=open, path=<full path>)`
- Search files: `file_op(op=search, path=documents, pattern=*.pdf)`

**For Memory:**
- Save new fact: `add_memory(content=<fact>)`
- Find relevant context: `search_memories(query=<topic>)`
- List all: `get_memories()`

## 🎮 windows_do Action Types
| action | key fields | notes |
|--------|-----------|-------|
| click | target | left-click element |
| double_click | target | double-click |
| right_click | target | open context menu |
| type | target, text | clear then type (append:true to keep existing) |
| key | keys | e.g. "ctrl+c", "alt+F4", "ctrl+shift+esc" |
| scroll | target, direction, amount | up/down/left/right |
| focus | target | set keyboard focus |
| read | target | return element's text/value |
| read_screen | — | return ALL visible text in window (preferred for reading content) |
| wait | ms | sleep N milliseconds |
| screenshot | — | capture screen to file (use sparingly) |
| close_app | — | close the window (must be explicit) |
"""

# ── Skill Files — loaded into memory, injected per-request based on keywords ──
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_skill(filename: str) -> str:
    path = os.path.join(_AGENT_DIR, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

# Each skill: (content, set-of-trigger-keywords)
_SKILLS: list[tuple[str, set]] = [
    (
        _load_skill("WindowsAutomator.md"),
        {"windows", "app", "launch", "click", "type", "key", "inspect", "automat",
         "excel", "word", "notepad", "cmd", "settings", "whatsapp", "vlc", "spotify",
         "open", "close", "read_screen", "screenshot", "batch", "action"},
    ),
    (
        _load_skill("ChromeNavigator.md"),
        {"chrome", "browser", "google", "youtube", "url", "navigate", "tab",
         "search", "website", "web page", "address bar", "bing", "link"},
    ),
    (
        _load_skill("FileManager.md"),
        {"file", "folder", "desktop", "downloads", "documents", "pictures",
         "copy", "move", "delete", "list", "search", "pdf", "explorer",
         "directory", "path", "create folder", "rename"},
    ),
]

_loaded_skills = sum(1 for content, _ in _SKILLS if content)
logger.info(f"[skills] Loaded {_loaded_skills}/3 skill files into memory")

def _build_system_prompt(user_text: str) -> str:
    """Return SYSTEM_PROMPT + any skill sections relevant to the user message."""
    if not user_text:
        return SYSTEM_PROMPT
    lower = user_text.lower()
    sections = []
    for content, keywords in _SKILLS:
        if content and any(kw in lower for kw in keywords):
            sections.append(content)
    if not sections:
        return SYSTEM_PROMPT
    skill_block = "\n\n---\n\n".join(sections)
    return f"{SYSTEM_PROMPT}\n\n---\n\n## 📖 Skill Reference\n\n{skill_block}"
# ── Agent Initialization ─────────────────────────────────────────────────────
airi = Assistant(
    llm=llm_cfg,
    system_message=SYSTEM_PROMPT,
    function_list=[
        'windows_launch', 'windows_inspect', 'windows_do',
        'file_op', 'list_installed_apps',
        'add_memory', 'search_memories', 'get_memories', 'get_memory',
        'update_memory', 'delete_memory', 'delete_all_memories',
    ],
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

    # Extract last user text for skill keyword matching
    _last_user_text = ""
    for m in reversed(raw_messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            _last_user_text = c if isinstance(c, str) else " ".join(
                p.get("text", "") for p in c if isinstance(p, dict)
            )
            break

    def stream_gen():
        import re as _re
        _current_user_id.set(user_id)
        _current_session_id.set(session_id)

        # Build per-request system prompt with relevant skill sections injected
        _sys = _build_system_prompt(_last_user_text)
        _run_messages = [Message("system", _sys)] + [
            m for m in messages if m.get("role") != "system"
        ]

        prev_content  = ""
        chunk_id      = f"chatcmpl-{int(time.time())}"
        seen_tool_ids = set()

        def _tool_event(tool_name: str, detail: str = "") -> str:
            """Emit a custom SSE event so the frontend can show the AgentLoader status."""
            payload = json.dumps({"tool": tool_name, "detail": detail}, ensure_ascii=False)
            return f"event: tool_call\ndata: {payload}\n\n"

        try:
            for response in airi.run(_run_messages):
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
        cached = try_to_load_from_cache("Systran/faster-whisper-tiny", "model.bin")
        is_cached = cached is not None and not isinstance(cached, type(None))
        if is_cached:
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
    SAMPLE_WIDTH  = 2
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
                if len(buf) >= CHUNK_SAMPLES * SAMPLE_WIDTH:
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
                            result_queue.put({"type": "interim", "text": text})
                    except Exception as e:
                        logger.error(f"[ws_transcribe] transcribe error: {e}")
            except queue.Empty:
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
