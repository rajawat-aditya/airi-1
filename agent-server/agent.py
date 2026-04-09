import os
import sys
import json
import time
import asyncio
import logging
import threading
from contextvars import ContextVar
from typing import Optional, List, Dict, Any
from functools import wraps
from threading import Lock

# ── Force UTF-8 output (Windows emoji fix) ────────────────────────────────────
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ── Set env vars before mem0 import ──────────────────────────────────────────
os.environ.setdefault("OPENAI_API_KEY", "none")
os.environ.setdefault("MEM0_TELEMETRY", "false")

# ── Qwen Agent Framework Imports ─────────────────────────────────────────────
try:
    from qwen_agent.agents import Assistant
    from qwen_agent.tools.base import BaseTool, register_tool
    from qwen_agent.llm.schema import Message, ContentItem
    logger.info("[startup] Qwen Agent framework loaded")
except ImportError as e:
    logger.critical(f"[startup] FATAL: qwen_agent not installed: {e}")
    sys.exit(1)

# ── FastAPI Imports ──────────────────────────────────────────────────────────
from fastapi import FastAPI, Request, UploadFile, File, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil

# ── Memory Import ────────────────────────────────────────────────────────────
try:
    from mem0 import Memory
    logger.info("[startup] mem0 loaded")
except ImportError as e:
    logger.critical(f"[startup] FATAL: mem0 not installed: {e}")
    sys.exit(1)

# ── FlaUI Engine ──────────────────────────────────────────────────────────────
try:
    from flaui import engine
    logger.info("[startup] FlaUI engine loaded")
except ImportError as e:
    logger.critical(f"[startup] FATAL: flaui module not found: {e}")
    sys.exit(1)

# ── Model Configuration ──────────────────────────────────────────────────────
modelName = "Qwen/Qwen3-VL-2B-Instruct-GGUF"

# ── Mem0 DB Configuration ─────────────────────────────────────────────────────
_MEM0_DB        = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mem0_db")
_EMBED_DIMS     = 768
_COLLECTION     = "airi_memory"
_EMBED_MODEL    = "unsloth/embeddinggemma-300m-GGUF:Q4_0"
_EMBED_BASE_URL = "http://127.0.0.1:11445/v1"

# ── Wait for embedding server ─────────────────────────────────────────────────
def _wait_for_embedding_server(max_retries: int = 40, delay: float = 0.5) -> bool:
    import requests
    for i in range(max_retries):
        try:
            r = requests.get("http://127.0.0.1:11445/health", timeout=1)
            if r.status_code == 200:
                logger.info("[mem0] Embedding server ready")
                return True
        except Exception:
            pass
        if i == 0:
            logger.info("[mem0] Waiting for embedding server...")
        time.sleep(delay)
    logger.warning("[mem0] Embedding server not ready after timeout — continuing without it")
    return False


def _probe_embedding_dims() -> int:
    import requests
    try:
        resp = requests.post(
            f"{_EMBED_BASE_URL}/embeddings",
            json={"model": _EMBED_MODEL, "input": "test"},
            timeout=5,
        )
        resp.raise_for_status()
        dims = len(resp.json()["data"][0]["embedding"])
        logger.info(f"[mem0] Embedder returns {dims} dims")
        return dims
    except Exception as e:
        logger.warning(f"[mem0] Could not probe dims ({e}), using default {_EMBED_DIMS}")
        return _EMBED_DIMS


def _ensure_qdrant_collection(dims: int):
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        os.makedirs(_MEM0_DB, exist_ok=True)
        client = QdrantClient(path=_MEM0_DB)
        existing = {c.name for c in client.get_collections().collections}

        if _COLLECTION in existing:
            info = client.get_collection(_COLLECTION)
            vectors_config = info.config.params.vectors
            current_dims = (
                next(iter(vectors_config.values())).size
                if isinstance(vectors_config, dict)
                else vectors_config.size
            )
            if current_dims != dims:
                logger.warning(f"[mem0] Dim mismatch ({current_dims} vs {dims}). Recreating collection.")
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
    except Exception as e:
        logger.error(f"[mem0] Qdrant collection setup failed: {e}")
        raise


# ── Init sequence ─────────────────────────────────────────────────────────────
_embed_server_ready = _wait_for_embedding_server()
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

try:
    mem_client = Memory.from_config(mem0_config)
    logger.info(f"[mem0] Ready — collection '{_COLLECTION}' @ {_EMBED_DIMS} dims")
except Exception as e:
    logger.critical(f"[mem0] FATAL: Could not initialize Memory client: {e}")
    sys.exit(1)

# ── Request-Scoped Context Variables ─────────────────────────────────────────
_current_user_id:    ContextVar[str] = ContextVar('user_id',    default='default_user')
_current_session_id: ContextVar[str] = ContextVar('session_id', default='default_session')

# ── File Extension Sets ──────────────────────────────────────────────────────
_RAG_EXTS = {'.pdf', '.docx', '.pptx', '.txt', '.csv', '.tsv', '.xlsx', '.xls', '.html'}
_IMG_EXTS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}

# ── Helper: Safe param parser ─────────────────────────────────────────────────
def _parse(params) -> Any:
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
    parsed = _parse(params)
    if isinstance(parsed, dict):
        return parsed.get(key, default)
    return default


def _build_messages(raw_messages: list) -> list:
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
        file_items: list = []

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


# ── Retry Decorator ───────────────────────────────────────────────────────────
def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            current_delay = delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"[retry] {func.__name__} attempt {attempt+1}/{max_retries} failed: {e}"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
            logger.error(f"[retry] {func.__name__} exhausted {max_retries} attempts. Last error: {last_error}")
            raise last_error
        return wrapper
    return decorator

# ── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Airi Agent API",
    description="Friendly Windows Desktop AI Assistant powered by Qwen3-VL-2B",
    version="3.0.0"
)

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
    defaults = {
        "model_server":     "http://127.0.0.1:11434/v1",
        "model":            "default",
        "api_key":          "none",
        "thinking_enabled": True,
        "theme":            "Night",
    }
    if os.path.exists(_SETTINGS_PATH):
        try:
            with open(_SETTINGS_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
            logger.info(f"[settings] Loaded from {_SETTINGS_PATH}")
        except Exception as e:
            logger.warning(f"[settings] Could not load settings.json: {e} — using defaults")
    return defaults


def _save_settings(s: dict):
    try:
        with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
        logger.info("[settings] Saved")
    except Exception as e:
        logger.warning(f"[settings] Could not save: {e}")


_settings = _load_settings()

# ── LLM Configuration ────────────────────────────────────────────────────────
def _build_llm_cfg(settings: dict) -> dict:
    is_local = (
        not settings.get("model_server") or
        "127.0.0.1" in settings["model_server"] or
        "localhost" in settings["model_server"]
    )
    generate_cfg = {
        "temperature":        0.5,
        "top_p":              0.9,
        "top_k":              20,
        "presence_penalty":   0.5,
        "max_tokens":         2048,
        "repetition_penalty": 1.1,
    }
    if is_local:
        generate_cfg["extra_body"] = {"enable_thinking": settings.get("thinking_enabled", True)}
    return {
        "model":        settings["model"],
        "model_server": settings["model_server"],
        "api_key":      settings.get("api_key", "none"),
        "generate_cfg": generate_cfg,
    }

llm_cfg = _build_llm_cfg(_settings)

# ── Path alias resolver ───────────────────────────────────────────────────────
def _resolve_path(path: str) -> str:
    aliases = {
        "desktop":   os.path.join(os.path.expanduser("~"), "Desktop"),
        "downloads": os.path.join(os.path.expanduser("~"), "Downloads"),
        "documents": os.path.join(os.path.expanduser("~"), "Documents"),
        "pictures":  os.path.join(os.path.expanduser("~"), "Pictures"),
    }
    return aliases.get(path.lower().strip(), path)

# ── TOOLS ─────────────────────────────────────────────────────────────────────

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
        app  = (p.get('app', '') if isinstance(p, dict) else str(p)).strip()
        args = (p.get('args', '') if isinstance(p, dict) else '').strip()
        if not app:
            logger.warning("[windows_launch] called without app name")
            return json.dumps({"status": "error", "detail": "app is required"})
        logger.info(f"[windows_launch] launching '{app}' args='{args}'")
        try:
            result = engine.launch_app(app, args)
            logger.info(f"[windows_launch] result: {result.get('status')}")
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[windows_launch] '{app}' failed: {e}")
            return json.dumps({"status": "error", "detail": str(e), "app": app})


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
        app          = (p.get('app', '') if isinstance(p, dict) else str(p)).strip()
        depth        = int(p.get('depth') or 4) if isinstance(p, dict) else 4
        filter_types = (p.get('filter_types', '') if isinstance(p, dict) else '').strip()
        if not app:
            return json.dumps({"error": "app is required"})
        logger.info(f"[windows_inspect] app='{app}' depth={depth} filter='{filter_types}'")
        try:
            result = engine.inspect_window(app, depth=depth, filter_types=filter_types)
            element_count = len(result) if isinstance(result, list) else "?"
            logger.info(f"[windows_inspect] returned {element_count} elements")
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[windows_inspect] '{app}' failed: {e}")
            return json.dumps({"error": str(e), "app": app})


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
        app     = (p.get('app', '') if isinstance(p, dict) else '').strip()
        actions = p.get('actions', []) if isinstance(p, dict) else []

        if not app:
            return json.dumps({"error": "app is required"})

        # Normalize actions if passed as string
        if isinstance(actions, str):
            try:
                actions = json.loads(actions)
            except Exception:
                try:
                    import ast
                    actions = ast.literal_eval(actions)
                except Exception:
                    return json.dumps({"error": "actions must be a JSON array"})

        if not isinstance(actions, list) or len(actions) == 0:
            return json.dumps({"error": "actions must be a non-empty list"})

        logger.info(f"[windows_do] app='{app}' actions={len(actions)}")
        try:
            result = engine.execute_batch(app, actions)
            errors = [r for r in (result if isinstance(result, list) else []) if r.get("status") == "error"]
            if errors:
                logger.warning(f"[windows_do] {len(errors)}/{len(actions)} actions failed")
            else:
                logger.info(f"[windows_do] all {len(actions)} actions completed")
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[windows_do] '{app}' batch failed: {e}")
            return json.dumps({"error": str(e), "app": app})


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
        import glob as _glob
        p       = _parse(params)
        op      = (p.get('op',   '') if isinstance(p, dict) else str(p)).strip()
        path    = _resolve_path((p.get('path',    '') if isinstance(p, dict) else '').strip())
        dest    = _resolve_path((p.get('dest',    '') if isinstance(p, dict) else '').strip())
        pattern = (p.get('pattern', '') if isinstance(p, dict) else '').strip()

        if not op:
            return json.dumps({"error": "op is required"})
        if not path:
            return json.dumps({"error": "path is required"})

        logger.info(f"[file_op] op='{op}' path='{path}'")
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
                logger.info(f"[file_op] list returned {len(items)} items")
                return json.dumps(items)

            elif op == 'open':
                if not os.path.exists(path):
                    return json.dumps({"error": f"Path not found: {path}"})
                os.startfile(path)
                return json.dumps({"status": "opened", "path": path})

            elif op == 'copy':
                if not dest:
                    return json.dumps({"error": "dest is required for copy"})
                if not os.path.exists(path):
                    return json.dumps({"error": f"Source not found: {path}"})
                if os.path.isdir(path):
                    shutil.copytree(path, dest)
                else:
                    shutil.copy2(path, dest)
                return json.dumps({"status": "copied", "from": path, "to": dest})

            elif op == 'move':
                if not dest:
                    return json.dumps({"error": "dest is required for move"})
                if not os.path.exists(path):
                    return json.dumps({"error": f"Source not found: {path}"})
                shutil.move(path, dest)
                return json.dumps({"status": "moved", "from": path, "to": dest})

            elif op == 'delete':
                if not os.path.exists(path):
                    return json.dumps({"error": f"Path not found: {path}"})
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return json.dumps({"status": "deleted", "path": path})

            elif op == 'create_folder':
                os.makedirs(path, exist_ok=True)
                return json.dumps({"status": "created", "path": path})

            elif op == 'search':
                base = path if path else os.path.expanduser("~")
                pat  = pattern or '*'
                if not os.path.exists(base):
                    return json.dumps({"error": f"Search base not found: {base}"})
                if '*' in pat or '?' in pat:
                    matches = _glob.glob(os.path.join(base, '**', pat), recursive=True)
                else:
                    matches = [
                        os.path.join(root, f)
                        for root, dirs, files in os.walk(base)
                        for f in files + dirs
                        if pat.lower() in f.lower()
                    ]
                logger.info(f"[file_op] search found {len(matches)} results")
                return json.dumps(matches[:100])

            else:
                return json.dumps({"error": f"Unknown op: '{op}'. Valid: list|open|copy|move|delete|create_folder|search"})

        except PermissionError as e:
            logger.error(f"[file_op] Permission denied: {e}")
            return json.dumps({"error": f"Permission denied: {e}"})
        except Exception as e:
            logger.error(f"[file_op] op='{op}' failed: {e}")
            return json.dumps({"error": str(e)})


_INSTALLED_APPS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "installed_apps.json")


@register_tool('list_installed_apps')
class ListInstalledApps(BaseTool):
    description = 'List installed Windows apps from the pre-built app index. Use to find app names before windows_launch.'
    parameters = []

    def call(self, params: str, **kwargs) -> str:
        logger.info("[list_installed_apps] reading installed_apps.json")
        try:
            with open(_INSTALLED_APPS_PATH, encoding="utf-8") as f:
                apps = json.load(f)
            logger.info(f"[list_installed_apps] {len(apps)} apps loaded")
            return json.dumps(apps)
        except FileNotFoundError:
            logger.error(f"[list_installed_apps] installed_apps.json not found at {_INSTALLED_APPS_PATH}")
            return json.dumps({"error": "installed_apps.json not found — please restart the app to rebuild it"})
        except Exception as e:
            logger.error(f"[list_installed_apps] failed to read: {e}")
            return json.dumps({"error": str(e)})

# ── Memory Tools ──────────────────────────────────────────────────────────────

@register_tool('add_memory')
class AddMemory(BaseTool):
    description = "Save a fact or preference about the user to long-term memory."
    parameters = [
        {'name': 'content', 'type': 'string', 'required': True,
         'description': "The fact or preference to remember (e.g. 'User prefers dark mode')"},
    ]

    def call(self, params: str, **kwargs) -> str:
        p       = _parse(params)
        content = (p.get('content', '') if isinstance(p, dict) else str(p)).strip()
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
            logger.info(f"[add_memory] saved {len(ids)} memories for user='{user_id}'")
            return json.dumps({"saved": True, "ids": ids})
        except Exception as e:
            logger.error(f"[add_memory] error: {e}")
            return json.dumps({"error": str(e)})


@register_tool('search_memories')
class SearchMemories(BaseTool):
    description = "Search user's long-term memories for relevant facts."
    parameters = [
        {'name': 'query', 'type': 'string', 'required': True,
         'description': "What to search for (e.g. 'user preferences', 'name', 'work')"},
        {'name': 'limit', 'type': 'integer',
         'description': "Max results to return (default 8)"},
    ]

    def call(self, params: str, **kwargs) -> str:
        p       = _parse(params)
        query   = (p.get('query', '') if isinstance(p, dict) else str(p)).strip()
        limit   = int(p.get('limit', 8)) if isinstance(p, dict) else 8
        user_id = _current_user_id.get()
        if not query:
            return json.dumps({"error": "query is required"})
        try:
            raw      = mem_client.search(query, user_id=user_id, limit=limit, threshold=0.15)
            items    = raw.get("results", []) if isinstance(raw, dict) else []
            memories = [{"id": r["id"], "memory": r["memory"]} for r in items if r.get("memory")]
            logger.info(f"[search_memories] '{query}' → {len(memories)} results")
            return json.dumps(memories)
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
            logger.info(f"[get_memories] {len(memories)} memories for user='{user_id}'")
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
        memory_id = (p.get('memory_id', '') if isinstance(p, dict) else str(p)).strip()
        if not memory_id:
            return json.dumps({"error": "memory_id is required"})
        try:
            result = mem_client.get(memory_id)
            if result:
                return json.dumps(result)
            return json.dumps({"error": f"Memory not found: {memory_id}"})
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
        memory_id = (p.get('memory_id', '') if isinstance(p, dict) else '').strip()
        content   = (p.get('content',   '') if isinstance(p, dict) else '').strip()
        if not memory_id:
            return json.dumps({"error": "memory_id is required"})
        if not content:
            return json.dumps({"error": "content is required"})
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
        memory_id = (p.get('memory_id', '') if isinstance(p, dict) else str(p)).strip()
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
            logger.info(f"[delete_all_memories] cleared all for user='{user_id}'")
            return json.dumps({"deleted": True, "user_id": user_id})
        except Exception as e:
            logger.error(f"[delete_all_memories] error: {e}")
            return json.dumps({"error": str(e)})

# ── Internet Search ───────────────────────────────────────────────────────────

@register_tool('internet_search')
class InternetSearch(BaseTool):
    description = "Search the internet using SearXNG and return a list of results with titles, URLs, and snippets."
    parameters = [
        {'name': 'query', 'type': 'string', 'required': True,
         'description': "The search query string"},
    ]

    def call(self, params: str, **kwargs) -> str:
        p     = _parse(params)
        query = (p.get('query', '') if isinstance(p, dict) else str(p)).strip()
        if not query:
            return json.dumps({"error": "query is required"})
        try:
            import urllib.request, urllib.parse
            url = f"http://127.0.0.1:11455/search?q={urllib.parse.quote(query)}&format=json"
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            results = [
                {"title": r.get("title"), "url": r.get("url"), "content": r.get("content")}
                for r in data.get("results", [])
            ]
            logger.info(f"[internet_search] '{query}' → {len(results)} results")
            return json.dumps({"query": query, "results": results})
        except Exception as e:
            logger.error(f"[internet_search] error: {e}")
            return json.dumps({"error": str(e)})

# ── SYSTEM PROMPT ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """# You are Airi — A Friendly Windows Desktop Assistant

You are Airi, a warm, helpful, and efficient AI companion for Windows users.
Your goal is to make every task feel easy and enjoyable.

## Your Personality
- Friendly & Warm: Speak naturally, like a helpful friend. Use emojis sparingly to add warmth.
- Clear & Simple: Explain steps in plain language. Avoid technical jargon unless asked.
- Proactive & Thorough: Anticipate follow-up needs. Confirm before destructive actions.
- Patient & Encouraging: Never make users feel silly for asking.

## Your Capabilities
- Windows Apps: Open, control, and automate any installed application via UI automation
- File Management: List, open, copy, move, delete files and folders
- Documents & Images: Analyze uploaded files automatically (PDF, Word, images, etc.)
- Memory: Remember user preferences and important details across sessions

## Golden Rules
1. ONE tool at a time — Call one tool, wait for result, then proceed.
2. Launch before interacting — Use windows_launch if the app isn't open yet.
3. Inspect when unsure — Use windows_inspect to discover element names before windows_do.
4. Batch actions — Use windows_do with multiple actions in one call to minimize round-trips.
5. Read screen, not screenshots — Use read_screen action in windows_do; it's faster.
6. Save important info — When user shares preferences/facts, use add_memory.
7. Check memory first — At conversation start, use search_memories to retrieve relevant context.
8. Files are automatic — Uploaded documents/images are analyzed directly (no tool needed).
9. Be honest about limits — If something fails, explain clearly and suggest alternatives.
10. Error recovery — When windows_do returns an error, check inspect_fallback in the result before retrying.

## Available Tools
| Tool | When to Use |
|------|-------------|
| windows_launch(app, args?) | Open a Windows app by name |
| windows_inspect(app, depth?, filter_types?) | Discover UI elements in a running app |
| windows_do(app, actions[]) | Execute UI actions (click, type, key, scroll, read, etc.) |
| file_op(op, path, dest?, pattern?) | File operations: list/open/copy/move/delete/create_folder/search |
| list_installed_apps() | List all installed apps to find the right name |
| add_memory(content) | Save a fact about the user |
| search_memories(query) | Find relevant past memories |
| get_memories() | List all user memories |
| get_memory(memory_id) | Get a specific memory by ID |
| update_memory(memory_id, content) | Update an existing memory |
| delete_memory(memory_id) | Delete a specific memory |
| delete_all_memories() | Clear all user memories |
| internet_search(query) | Search the internet and return results |

## windows_do Action Types
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
| read_screen | — | return ALL visible text in window (preferred) |
| wait | ms | sleep N milliseconds |
| screenshot | — | capture screen to file (use sparingly) |
| close_app | — | close the window (must be explicit) |
"""

# ── Skill Files ───────────────────────────────────────────────────────────────
_AGENT_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_skill(filename: str) -> str:
    path = os.path.join(_AGENT_DIR, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        logger.warning(f"[skills] Could not load '{filename}': {e}")
        return ""

_SKILLS: list = [
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
logger.info(f"[skills] Loaded {_loaded_skills}/3 skill files")


def _build_system_prompt(user_text: str) -> str:
    """Return SYSTEM_PROMPT + any skill sections relevant to the user message."""
    if not user_text:
        return SYSTEM_PROMPT
    lower = user_text.lower()
    sections = [content for content, keywords in _SKILLS if content and any(kw in lower for kw in keywords)]
    if not sections:
        return SYSTEM_PROMPT
    skill_block = "\n\n---\n\n".join(sections)
    return f"{SYSTEM_PROMPT}\n\n---\n\n## Skill Reference\n\n{skill_block}"


# ── Agent Initialization ─────────────────────────────────────────────────────
_TOOL_LIST = [
    'windows_launch', 'windows_inspect', 'windows_do',
    'file_op', 'list_installed_apps',
    'add_memory', 'search_memories', 'get_memories', 'get_memory',
    'update_memory', 'delete_memory', 'delete_all_memories',
]

_agent_lock = Lock()
_airi: Optional[Assistant] = None


def _get_agent() -> Assistant:
    """Get or create the agent instance (thread-safe)."""
    global _airi
    with _agent_lock:
        if _airi is None:
            logger.info("[agent] Initializing Airi assistant...")
            try:
                _airi = Assistant(
                    llm=llm_cfg,
                    system_message=SYSTEM_PROMPT,
                    function_list=_TOOL_LIST,
                )
                logger.info("[agent] Airi ready")
            except Exception as e:
                logger.critical(f"[agent] Failed to initialize: {e}")
                raise
        return _airi


def _reload_agent():
    """Force re-create the agent (e.g. after settings change)."""
    global _airi
    # Build new config first (outside lock) to minimize lock hold time
    new_cfg = _build_llm_cfg(_settings)
    logger.info("[agent] Reloading agent with new settings...")
    try:
        new_agent = Assistant(
            llm=new_cfg,
            system_message=SYSTEM_PROMPT,
            function_list=_TOOL_LIST,
        )
        # Swap atomically under lock
        with _agent_lock:
            _airi = new_agent
        logger.info("[agent] Agent reloaded successfully")
    except Exception as e:
        logger.error(f"[agent] Reload failed: {e}")
        raise


# Initialize on startup
try:
    _get_agent()
except Exception as e:
    logger.critical(f"[startup] Agent initialization failed: {e}")
    sys.exit(1)

# ── FastAPI Endpoints ────────────────────────────────────────────────────────

def _msg_role(m) -> str:
    """Get role from a Qwen-agent Message (attribute) or plain dict (key)."""
    return getattr(m, "role", None) or (m.get("role", "") if isinstance(m, dict) else "")


def _msg_content(m):
    """Get content from a Qwen-agent Message (attribute) or plain dict (key)."""
    return getattr(m, "content", None) or (m.get("content") if isinstance(m, dict) else None) or ""


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        data = await request.json()
    except Exception as e:
        logger.error(f"[chat] Failed to parse request body: {e}")
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': 'Invalid JSON body'})}\n\ndata: [DONE]\n\n"]),
            media_type="text/event-stream"
        )

    raw_messages = data.get("messages", [])
    user_id      = data.get("user_id",    "default_user")
    session_id   = data.get("session_id", "default_session")

    messages = _build_messages(raw_messages)

    # Extract last user text for skill keyword matching
    last_user_text = ""
    for m in reversed(raw_messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            last_user_text = c if isinstance(c, str) else " ".join(
                p.get("text", "") for p in c if isinstance(p, dict)
            )
            break

    # Build run_messages here (in async context) before handing off to thread
    sys_prompt   = _build_system_prompt(last_user_text)

    # Only pass user + assistant text messages to the agent.
    # Tool role messages from previous turns confuse the model into thinking
    # tools already ran, causing it to skip tool calls on follow-up prompts.
    def _is_passthrough(m) -> bool:
        role = _msg_role(m)
        if role == "tool":
            return False
        if role == "assistant":
            # Drop assistant messages that are pure tool-call lists (no text)
            content = _msg_content(m)
            if isinstance(content, list):
                has_text = any(
                    (item.get("text") if isinstance(item, dict) else getattr(item, "text", None))
                    for item in content
                )
                return has_text
        return True

    run_messages = [Message("system", sys_prompt)] + [
        m for m in messages if _msg_role(m) != "system" and _is_passthrough(m)
    ]

    def stream_gen():
        import re as _re

        # Re-set ContextVars inside the generator thread
        _current_user_id.set(user_id)
        _current_session_id.set(session_id)

        chunk_id      = f"chatcmpl-{int(time.time())}"
        seen_tool_ids = set()
        prev_content  = ""

        def _tool_event(tool_name: str, detail: str = "") -> str:
            payload = json.dumps({"tool": tool_name, "detail": detail}, ensure_ascii=False)
            return f"event: tool_call\ndata: {payload}\n\n"

        def _text_chunk(delta: str) -> str:
            chunk = {
                "id":      chunk_id,
                "object":  "chat.completion.chunk",
                "created": int(time.time()),
                "model":   modelName,
                "choices": [{"index": 0, "delta": {"content": delta}, "finish_reason": None}],
            }
            return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        try:
            agent = _get_agent()

            for response in agent.run(run_messages):
                if not response:
                    continue

                # ── Detect and emit tool call / tool result events ─────────────
                for m in response:
                    role    = _msg_role(m)
                    content = _msg_content(m)

                    if role == "assistant" and isinstance(content, list):
                        for item in content:
                            if not isinstance(item, dict):
                                continue
                            # Qwen-agent stores tool calls as {"function": "name", "id": "..."}
                            # or {"name": "...", "call_id": "..."}
                            fn      = item.get("function") or item.get("name") or ""
                            call_id = item.get("id") or item.get("call_id") or fn
                            if fn and call_id not in seen_tool_ids:
                                seen_tool_ids.add(call_id)
                                logger.info(f"[stream] → tool call: {fn}")
                                yield _tool_event(fn)

                    elif role == "tool":
                        # tool_call_id links back to the assistant's call
                        tool_name = (
                            getattr(m, "name", None)
                            or (m.get("name") if isinstance(m, dict) else None)
                            or getattr(m, "tool_call_id", None)
                            or (m.get("tool_call_id") if isinstance(m, dict) else None)
                            or "tool"
                        )
                        result_id = f"result_{tool_name}"
                        if result_id not in seen_tool_ids:
                            seen_tool_ids.add(result_id)
                            logger.info(f"[stream] ✓ tool done: {tool_name}")
                            yield _tool_event(tool_name, "done")

                # ── Stream assistant text delta ────────────────────────────────
                assistant_msgs = [m for m in response if _msg_role(m) == "assistant"]
                if not assistant_msgs:
                    continue

                raw = _msg_content(assistant_msgs[-1])
                if isinstance(raw, list):
                    full_content = " ".join(
                        item.get("text", "") if isinstance(item, dict)
                        else (getattr(item, "text", "") or "")
                        for item in raw
                        if (item.get("text") if isinstance(item, dict) else getattr(item, "text", None))
                    )
                else:
                    full_content = str(raw) if raw else ""

                # Strip <think>...</think> blocks (Qwen3 thinking mode)
                if "<think>" in full_content:
                    full_content = _re.sub(r"<think>.*?</think>", "", full_content, flags=_re.DOTALL).strip()

                delta = full_content[len(prev_content):]
                prev_content = full_content
                if delta:
                    yield _text_chunk(delta)

            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[chat] Stream error: {e}", exc_info=True)
            yield _text_chunk(f"\n\n⚠️ Something went wrong: {e}")
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream_gen(), media_type="text/event-stream")


# ── Settings Endpoints ────────────────────────────────────────────────────────

class SettingsPayload(BaseModel):
    model_server:     Optional[str]  = None
    model:            Optional[str]  = None
    api_key:          Optional[str]  = None
    thinking_enabled: Optional[bool] = None
    theme:            Optional[str]  = None  # "Day" | "Night"


@app.get("/settings")
async def get_settings():
    return _settings


@app.post("/settings")
async def update_settings(payload: SettingsPayload):
    global _settings, llm_cfg
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return {"status": "no_changes", "settings": _settings}
    _settings.update(updates)
    _save_settings(_settings)
    # Only rebuild LLM config and reload agent if inference settings changed
    inference_keys = {"model_server", "model", "api_key", "thinking_enabled"}
    if updates.keys() & inference_keys:
        llm_cfg = _build_llm_cfg(_settings)
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            # Run blocking _reload_agent in a thread pool to avoid blocking the event loop
            await loop.run_in_executor(None, _reload_agent)
        except Exception as e:
            logger.error(f"[settings] Agent reload failed after update: {e}")
            return {"status": "settings_saved_but_agent_reload_failed", "error": str(e), "settings": _settings}
    return {"status": "updated", "settings": _settings}


# ── File Upload ───────────────────────────────────────────────────────────────

USER_STUFF_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "user_stuff")
os.makedirs(USER_STUFF_DIR, exist_ok=True)

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
        info = {"name": fname, "size": stat.st_size, "modified": stat.st_mtime, "ext": ext.lstrip(".")}
        if ext in _IMG_EXTS_SET:
            media.append(info)
        else:
            docs.append(info)
    return {"documents": docs, "media": media}


@app.delete("/library/{filename}")
async def delete_library_file(filename: str):
    """Delete a file from user_stuff by name."""
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


from fastapi.responses import FileResponse as _FileResponse


@app.get("/library/file/{filename}")
async def serve_library_file(filename: str):
    """Serve a file from user_stuff for inline preview."""
    safe_name = os.path.basename(filename)
    fpath = os.path.join(USER_STUFF_DIR, safe_name)
    if not os.path.exists(fpath):
        return {"error": "File not found"}
    return _FileResponse(fpath)


# ── Memory HTTP endpoints ─────────────────────────────────────────────────────

@app.get("/memories")
async def get_memories_endpoint(user_id: str = "default_user"):
    try:
        raw = mem_client.get_all(user_id=user_id, limit=200)
        results = raw.get("results", []) if isinstance(raw, dict) else raw
        return {"memories": results}
    except Exception as e:
        logger.error(f"[memories] get error: {e}")
        return {"memories": [], "error": str(e)}


@app.delete("/memories/{memory_id}")
async def delete_memory_endpoint(memory_id: str):
    try:
        mem_client.delete(memory_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"[memories] delete error: {e}")
        return {"success": False, "error": str(e)}


class MemoryUpdateBody(BaseModel):
    data: str


@app.put("/memories/{memory_id}")
async def update_memory_endpoint(memory_id: str, body: MemoryUpdateBody):
    try:
        mem_client.update(memory_id, body.data)
        return {"success": True}
    except Exception as e:
        logger.error(f"[memories] update error: {e}")
        return {"success": False, "error": str(e)}


@app.post("/upload")
async def upload_files(files: list[UploadFile] = File(...)):
    saved = []
    errors = []
    for f in files:
        try:
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
        except Exception as e:
            logger.error(f"[upload] Failed to save '{f.filename}': {e}")
            errors.append({"file": f.filename, "error": str(e)})
    return {"paths": saved, "count": len(saved), "errors": errors}


# ── Whisper STT ───────────────────────────────────────────────────────────────

_whisper_model = None
_whisper_lock  = Lock()


def _get_whisper():
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            try:
                from faster_whisper import WhisperModel
                from huggingface_hub import try_to_load_from_cache
                cached    = try_to_load_from_cache("Systran/faster-whisper-tiny", "model.bin")
                is_cached = cached is not None and not isinstance(cached, type(None))
                if is_cached:
                    os.environ["HF_HUB_OFFLINE"] = "1"
                    _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8", local_files_only=True)
                    logger.info("[whisper] Loaded from local cache (offline)")
                else:
                    logger.info("[whisper] Downloading tiny model (~75MB)...")
                    _whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                    logger.info("[whisper] Model downloaded and cached")
            except Exception as e:
                logger.error(f"[whisper] Failed to load model: {e}")
                raise
    return _whisper_model


def _prewarm_whisper():
    def _load():
        try:
            _get_whisper()
            logger.info("[whisper] Pre-warm complete")
        except Exception as e:
            logger.warning(f"[whisper] Pre-warm failed: {e}")
    threading.Thread(target=_load, daemon=True).start()

_prewarm_whisper()


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
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
        logger.info(f"[transcribe] result: '{text[:80]}...' " if len(text) > 80 else f"[transcribe] result: '{text}'")
        return {"text": text}
    except Exception as e:
        logger.error(f"[transcribe] failed: {e}")
        return {"text": "", "error": str(e)}

# ── WebSocket Real-Time Transcription ─────────────────────────────────────────

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

    try:
        model = _get_whisper()
    except Exception as e:
        logger.error(f"[ws_transcribe] Whisper unavailable: {e}")
        await websocket.send_json({"type": "error", "text": f"Whisper unavailable: {e}"})
        await websocket.close()
        return

    import wave, io, queue

    SAMPLE_RATE   = 16000
    CHANNELS      = 1
    SAMPLE_WIDTH  = 2
    CHUNK_SAMPLES = int(SAMPLE_RATE * 1.2)

    audio_queue:  queue.Queue = queue.Queue()
    result_queue: queue.Queue = queue.Queue()
    running = True

    def _transcribe_pcm(pcm: bytes, label: str) -> Optional[str]:
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
            return text or None
        except Exception as e:
            logger.error(f"[ws_transcribe] {label} error: {e}")
            return None

    def transcribe_worker():
        buf = b""
        while running:
            try:
                chunk = audio_queue.get(timeout=0.3)
                if chunk is None:
                    break
                buf += chunk
                if len(buf) >= CHUNK_SAMPLES * SAMPLE_WIDTH:
                    pcm, buf = buf, b""
                    text = _transcribe_pcm(pcm, "chunk")
                    if text:
                        result_queue.put({"type": "interim", "text": text})
            except queue.Empty:
                # Flush remaining buffer on silence
                if len(buf) > SAMPLE_RATE * SAMPLE_WIDTH * 0.3:
                    pcm, buf = buf, b""
                    text = _transcribe_pcm(pcm, "flush")
                    if text:
                        result_queue.put({"type": "final", "text": text})

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
            elif "text" in msg and msg.get("text") == "stop":
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"[ws_transcribe] Unexpected error: {e}")
    finally:
        running = False
        audio_queue.put(None)
        send_task.cancel()
        worker.join(timeout=2)
        logger.info("[ws_transcribe] Client disconnected")


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status":        "ok",
        "model":         _settings.get("model"),
        "model_server":  _settings.get("model_server"),
        "embed_dims":    _EMBED_DIMS,
        "embed_ready":   _embed_server_ready,
        "skills_loaded": _loaded_skills,
        "memory_collection": _COLLECTION,
    }


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    logger.info("[startup] Starting Airi agent server on port 11435")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=11435,
        log_level="info",
        access_log=False,
    )
