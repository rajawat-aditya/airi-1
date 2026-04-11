const { app, BrowserWindow, ipcMain, screen, protocol } = require('electron/main')
const path = require('node:path')
const fs = require('fs');
// Load .env.local — in dev it's next to the repo root, in packaged builds it's an extraResource
const IS_PACKAGED_EARLY = !process.defaultApp;
const envPath = IS_PACKAGED_EARLY
    ? path.join(process.resourcesPath, '.env.local')
    : path.join(__dirname, '../.env.local');
require('dotenv').config({ path: envPath });
const isDev = process.env.NODE_ENV == "development";
const { nativeImage } = require('electron');
const { spawn } = require('child_process');
const { MongoClient } = require('mongodb');
const { createHandler } = require('next-electron-rsc');
const { ensureModels } = require('./model-download');

// Redirect console to a log file in packaged mode so we can debug
if (IS_PACKAGED_EARLY) {
    const logPath = path.join(require('os').homedir(), 'airi-debug.log');
    const logStream = fs.createWriteStream(logPath, { flags: 'a' });
    const origLog = console.log.bind(console);
    const origErr = console.error.bind(console);
    console.log = (...args) => { origLog(...args); logStream.write('[LOG] ' + args.join(' ') + '\n'); };
    console.error = (...args) => { origErr(...args); logStream.write('[ERR] ' + args.join(' ') + '\n'); };
    console.log(`\n\n=== Airi started at ${new Date().toISOString()} ===`);
    console.log('STANDALONE_DIR will be:', path.join(app.getAppPath(), '.next', 'standalone'));
}

// Required for Web Speech API (Google speech service) to work inside Electron
app.commandLine.appendSwitch('enable-speech-dispatcher');
app.commandLine.appendSwitch('unsafely-treat-insecure-origin-as-secure', 'http://localhost:3000');
app.commandLine.appendSwitch('enable-features', 'WebSpeechAPI');

let mainWindow = null;
let llamaProcess = null;
let embeddingProcess = null;
let searxngProcess = null;
let agentProcess = null;
let atlasCollection = null;
let store = null;

let dbReady;
const dbReadyPromise = new Promise((resolve) => { dbReady = resolve; });

// ── Path helpers ──────────────────────────────────────────────────────────────
// electron-builder puts extraResources at process.resourcesPath
// In dev, everything is relative to the repo root (__dirname/../)
const IS_PACKAGED = app.isPackaged;
const RESOURCES   = IS_PACKAGED ? process.resourcesPath : path.join(__dirname, '..');

const AGENT_BUNDLE_EXE  = path.join(RESOURCES, 'airi-agent', 'airi-agent.exe');
const AGENT_BUNDLE_DIR  = path.join(RESOURCES, 'airi-agent');
const AGENT_SCRIPT      = path.join(__dirname, '../agent-server/agent.py');
const AGENT_SETTINGS    = IS_PACKAGED
    ? path.join(AGENT_BUNDLE_DIR, 'settings.json')
    : path.join(__dirname, '../agent-server/settings.json');
const INSTALLED_APPS_OUT = IS_PACKAGED
    ? path.join(AGENT_BUNDLE_DIR, 'installed_apps.json')
    : path.join(__dirname, '../agent-server/installed_apps.json');

const LLAMA_EXE    = path.join(RESOURCES, 'deps', 'llama-cpp', 'llama-server.exe');
const SEARXNG_EXE  = path.join(RESOURCES, 'deps', 'searxng', 'searxng-server.exe');
const MODELS_DIR   = IS_PACKAGED
    ? path.join(RESOURCES, 'models')
    : path.join(__dirname, '../models');

const isPackaged = IS_PACKAGED && fs.existsSync(AGENT_BUNDLE_EXE);

// next-electron-rsc: only used in production to serve the standalone Next.js build
// In dev, we connect directly to the already-running next dev server on localhost:3000
// In prod, dir must be inside the app bundle so resolve.sync('next', {basedir: dir}) can find node_modules/next
const STANDALONE_DIR = IS_PACKAGED
    ? path.join(app.getAppPath(), '.next', 'standalone')
    : path.join(__dirname, '..');

if (IS_PACKAGED) {
    console.log('[NEXT] STANDALONE_DIR:', STANDALONE_DIR, '| exists:', fs.existsSync(STANDALONE_DIR));
}

const { createInterceptor, localhostUrl } = IS_PACKAGED
    ? createHandler({ dev: false, dir: STANDALONE_DIR, protocol, debug: true })
    : { createInterceptor: null, localhostUrl: 'http://localhost:3000' };

async function setupDb() {
    // electron-store must be dynamically imported (ESM-only in v9+)
    const { default: Store } = await import('electron-store');
    store = new Store({ name: 'airi-chats' });

    // Connect to Atlas for sync (non-blocking — local store works even if offline)
    try {
        const client = new MongoClient(process.env.APP_MONGO_URI);
        await client.connect();
        atlasCollection = client.db("airi_db").collection("chats");
        console.log('[DB] Connected to MongoDB Atlas');
    } catch (err) {
        console.error('[DB] Atlas connection failed (offline mode):', err.message);
    }

    dbReady();
}

// --- helpers ---

function getStorageKey(userId) {
    return `chats_${userId}`;
}

function getLocalChats(userId) {
    return store.get(getStorageKey(userId), []);
}

function setLocalChats(userId, chats) {
    store.set(getStorageKey(userId), chats);
}

// --- IPC handlers (registered immediately, await dbReadyPromise before use) ---

ipcMain.handle('pull-chats', async (_event, userId) => {
    await dbReadyPromise;
    if (!userId) return { success: false, error: 'userId required' };
    if (!atlasCollection) return { success: false, error: 'Atlas not connected' };
    try {
        const remoteDocs = await atlasCollection
            .find({ userId }, { projection: { _id: 0 } })
            .sort({ updatedAt: -1 })
            .toArray();

        // Merge remote into local — remote wins on conflict
        const local = getLocalChats(userId);
        const merged = [...remoteDocs];
        for (const localDoc of local) {
            if (!merged.find((r) => r.chatId === localDoc.chatId)) {
                merged.push(localDoc);
            }
        }
        merged.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
        setLocalChats(userId, merged);

        return { success: true, count: merged.length };
    } catch (err) {
        console.error('[DB] pull-chats failed:', err.message);
        return { success: false, error: err.message };
    }
});

ipcMain.handle('get-chats', async (_event, userId) => {
    await dbReadyPromise;
    if (!userId) return [];
    return getLocalChats(userId);
});

ipcMain.handle('save-chat', async (_event, chatData) => {
    await dbReadyPromise;
    if (!chatData?.userId || !chatData?.chatId) {
        return { success: false, error: 'userId and chatId required' };
    }

    const userId = chatData.userId;
    const doc = { ...chatData, updatedAt: Date.now() };

    // Save to local store
    const chats = getLocalChats(userId);
    const idx = chats.findIndex((c) => c.chatId === doc.chatId);
    if (idx === -1) {
        chats.unshift(doc);
    } else {
        chats[idx] = doc;
    }
    setLocalChats(userId, chats);

    // Sync to Atlas in background (don't await — don't block the response)
    if (atlasCollection) {
        atlasCollection.updateOne(
            { chatId: doc.chatId },
            { $set: doc },
            { upsert: true }
        ).catch((err) => console.error('[DB] Atlas sync failed:', err.message));
    }

    return { success: true };
});

ipcMain.handle('delete-chat', async (_event, { chatId, userId }) => {
    await dbReadyPromise;
    if (!chatId || !userId) return { success: false, error: 'chatId and userId required' };

    const chats = getLocalChats(userId);
    setLocalChats(userId, chats.filter((c) => c.chatId !== chatId));

    if (atlasCollection) {
        atlasCollection.deleteOne({ chatId, userId })
            .catch((err) => console.error('[DB] Atlas delete failed:', err.message));
    }

    return { success: true };
});

// --- window & process management ---

function snapToOverlay() {
    if (!mainWindow) return;
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    const agentWidth = 348;
    const agentHeight = Math.round(height * 0.8);
    mainWindow.setResizable(true);
    mainWindow.setSize(agentWidth, agentHeight);
    mainWindow.setPosition(width - agentWidth, height - agentHeight);
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.focus();
}

function startSearxng() {
    searxngProcess = spawn(SEARXNG_EXE, ["--port", "11455"]);
    searxngProcess.stdout.on("data", (data) => console.log(`[SEARXNG] ${data}`));
    searxngProcess.stderr.on("data", (data) => console.error(`[SEARXNG ERROR] ${data}`));
}

function startEmbeddingServer() {
    const embeddingEnv = { ...process.env, LLAMA_CACHE: MODELS_DIR };
    embeddingProcess = spawn(LLAMA_EXE, [
        "-hf", "unsloth/embeddinggemma-300m-GGUF:Q4_0",
        "--port", "11445",
        "--embedding",
        "--threads", "4",
        "--n-gpu-layers", "0",
    ], { env: embeddingEnv });
    embeddingProcess.stdout.on("data", (data) => console.log(`[EMBEDDING] ${data}`));
    embeddingProcess.stderr.on("data", (data) => console.error(`[EMBEDDING ERROR] ${data}`));
}

function startLlama() {
    const settingsPath = AGENT_SETTINGS;
    let useLocal = true;
    let modelName = "Qwen/Qwen3-VL-2B-Instruct-GGUF";

    if (fs.existsSync(settingsPath)) {
        try {
            const settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
            if (settings.model && settings.model !== 'default') {
                modelName = settings.model;
            }
            // If model_server points to a remote API, don't start local llama
            if (settings.model_server &&
                !settings.model_server.includes('127.0.0.1') &&
                !settings.model_server.includes('localhost')) {
                useLocal = false;
            }
        } catch (e) {
            console.error('[LLAMA] Failed to read settings.json:', e.message);
        }
    }

    if (!useLocal) {
        console.log('[LLAMA] Remote API mode — skipping local llama-server');
        return;
    }

    const llamaExe = LLAMA_EXE;
    const llamaEnv = { ...process.env, LLAMA_CACHE: MODELS_DIR };

    // Try to use locally cached model file to avoid HF network dependency
    const snapshotDir = path.join(MODELS_DIR, 'models--Qwen--Qwen3-VL-2B-Instruct-GGUF/snapshots/52d6c8ffea26cc873ac5ad116f8631268d7eb503');
    const localModel  = path.join(snapshotDir, 'Qwen3VL-2B-Instruct-Q4_K_M.gguf');
    const localMmproj = path.join(snapshotDir, 'mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf');

    let args;
    if (fs.existsSync(localModel)) {
        console.log('[LLAMA] Using cached local model:', localModel);
        args = [
            "-m", localModel,
            "--mmproj", localMmproj,
            "--ctx-size", "32768",
            "-np", "2",
            "--threads", "6",
            "--n-gpu-layers", "0",
            "--port", "11434",
            "--cache-type-k", "q4_0",
            "--cache-type-v", "q8_0",
            "--jinja"
        ];
    } else {
        console.log('[LLAMA] Local model not found, downloading from HF:', modelName);
        args = [
            "-hf", modelName,
            "--ctx-size", "32768",
            "-np", "2",
            "--threads", "6",
            "--n-gpu-layers", "0",
            "--port", "11434",
            "--cache-type-k", "q4_0",
            "--cache-type-v", "q8_0",
            "--jinja"
        ];
    }

    llamaProcess = spawn(llamaExe, args, { env: llamaEnv });
    llamaProcess.stdout.on("data", (data) => console.log(`[LLAMA] ${data}`));
    llamaProcess.stderr.on("data", (data) => console.error(`[LLAMA ERROR] ${data}`));
}

function startAgentServer() {
    const agentEnv = { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' };

    if (isPackaged) {
        console.log('[Agent-Server] Starting bundled exe:', AGENT_BUNDLE_EXE);
        agentProcess = spawn(AGENT_BUNDLE_EXE, [], { cwd: AGENT_BUNDLE_DIR, env: agentEnv });
    } else {
        console.log('[Agent-Server] Starting dev script:', AGENT_SCRIPT);
        agentProcess = spawn('python', [AGENT_SCRIPT], { env: agentEnv });
    }

    agentProcess.on("error", (err) => {
        console.error(`[Agent-Server] Failed to start:`, err.message);
    });
    agentProcess.on("close", (code) => {
        if (code !== 0 && code !== null) {
            console.error(`[Agent-Server] Exited with code ${code}`);
        }
    });
    agentProcess.stdout.on("data", (data) => console.log(`[Agent-Server] ${data}`));
    agentProcess.stderr.on("data", (data) => console.error(`[Agent-Server] ${data}`));
}

/**
 * Scan installed apps via PowerShell and write agent-server/installed_apps.json.
 * Runs once at startup; non-blocking (errors are logged, not thrown).
 *
 * Output format: [{ name, exe, title_hint }]
 *
 * Sources (merged, deduped by exe path):
 *   1. Start Menu .lnk shortcuts (user + common)
 *   2. HKLM + HKCU Uninstall registry keys (InstallLocation + DisplayIcon)
 *   3. Get-StartApps (UWP + pinned classic apps)
 *   4. Common install directory scan for known exe names
 */
function buildInstalledAppsJson() {
    const outPath = INSTALLED_APPS_OUT;
    // Write temp PS1 to a writable location — app.asar is read-only in packaged builds
    const psPath = path.join(require('os').tmpdir(), '_airi_scan_apps.ps1');

    // Write the PowerShell script to a file — avoids all JS template literal escaping issues
    const psScript = [
        "$ErrorActionPreference = 'SilentlyContinue'",
        "$results = [System.Collections.Generic.List[hashtable]]::new()",
        "$seen    = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)",
        "",
        "function Add-App($name, $exe, $hint) {",
        "    if (-not $exe) { return }",
        "    $exe = $exe.Trim('\"').Trim()",
        "    if (-not $exe.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) { return }",
        "    if (-not (Test-Path $exe -PathType Leaf)) { return }",
        "    if (-not $seen.Add($exe)) { return }",
        "    if (-not $hint) { $hint = [System.IO.Path]::GetFileNameWithoutExtension($exe) }",
        "    if (-not $name) { $name = $hint }",
        "    $results.Add(@{ name = $name.Trim(); exe = $exe; title_hint = $hint.Trim() })",
        "}",
        "",
        "# 1. Start Menu .lnk shortcuts",
        "$shell = New-Object -ComObject WScript.Shell",
        "@(",
        "    [System.Environment]::GetFolderPath('StartMenu'),",
        "    [System.Environment]::GetFolderPath('CommonStartMenu')",
        ") | ForEach-Object {",
        "    Get-ChildItem -Path $_ -Recurse -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {",
        "        try {",
        "            $lnk    = $shell.CreateShortcut($_.FullName)",
        "            $target = $lnk.TargetPath",
        "            $name   = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)",
        "            Add-App $name $target ''",
        "        } catch {}",
        "    }",
        "}",
        "",
        "# 2. Registry Uninstall keys (HKLM 64-bit, 32-bit, HKCU)",
        "$regPaths = @(",
        "    'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',",
        "    'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*',",
        "    'HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'",
        ")",
        "foreach ($rp in $regPaths) {",
        "    Get-ItemProperty $rp -ErrorAction SilentlyContinue | ForEach-Object {",
        "        $name = $_.DisplayName",
        "        if (-not $name) { return }",
        "        $icon = ($_.DisplayIcon -split ',')[0].Trim().Trim('\"')",
        "        if ($icon -and $icon.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {",
        "            Add-App $name $icon ''",
        "            return",
        "        }",
        "        $loc = $_.InstallLocation",
        "        if ($loc -and (Test-Path $loc -PathType Container)) {",
        "            $stem = ($name -replace '[^a-zA-Z0-9]', '').ToLower()",
        "            Get-ChildItem -Path $loc -Filter '*.exe' -ErrorAction SilentlyContinue |",
        "                Where-Object { $_.Name -notmatch 'uninstall|setup|update|helper|crash|redist' } |",
        "                Sort-Object { [Math]::Abs($_.BaseName.ToLower().Length - $stem.Length) } |",
        "                Select-Object -First 1 | ForEach-Object { Add-App $name $_.FullName '' }",
        "        }",
        "    }",
        "}",
        "",
        "# 3. Get-StartApps",
        "Get-StartApps -ErrorAction SilentlyContinue | ForEach-Object {",
        "    $appId = $_.AppID",
        "    if ($appId -and $appId.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {",
        "        Add-App $_.Name $appId ''",
        "    }",
        "}",
        "",
        "# 4. Common install directory scan",
        "$scanDirs = @(",
        "    $env:ProgramFiles,",
        "    ${env:ProgramFiles(x86)},",
        "    \"$env:LOCALAPPDATA\\Programs\"",
        ") | Where-Object { $_ -and (Test-Path $_) }",
        "foreach ($dir in $scanDirs) {",
        "    Get-ChildItem -Path $dir -Recurse -Filter '*.exe' -Depth 3 -ErrorAction SilentlyContinue |",
        "        Where-Object { $_.Name -notmatch 'uninstall|setup|update|helper|crash|redist|vcredist|dotnet' } |",
        "        ForEach-Object {",
        "            $name = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)",
        "            Add-App $name $_.FullName ''",
        "        }",
        "}",
        "",
        "$results | ConvertTo-Json -Depth 2 -Compress",
    ].join('\n');

    try {
        fs.writeFileSync(psPath, psScript, 'utf8');
    } catch (err) {
        console.error('[Apps] Could not write _scan_apps.ps1:', err.message);
        return;
    }

    const proc = spawn('powershell', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', psPath], { timeout: 60000 });
    let stdout = '';
    let stderr = '';
    proc.stdout.on('data', d => stdout += d);
    proc.stderr.on('data', d => stderr += d);

    proc.on('close', () => {
        try {
            let apps = JSON.parse(stdout.trim());
            if (!Array.isArray(apps)) apps = apps ? [apps] : [];
            apps = apps
                .filter(a => a && a.exe)
                .map(a => ({
                    name:       (a.name       || path.basename(a.exe, '.exe')).trim(),
                    exe:        a.exe.trim(),
                    title_hint: (a.title_hint || path.basename(a.exe, '.exe')).trim(),
                }));
            fs.writeFileSync(outPath, JSON.stringify(apps, null, 2), 'utf8');
            console.log(`[Apps] Wrote ${apps.length} entries to installed_apps.json`);
        } catch (err) {
            console.error('[Apps] Failed to build installed_apps.json:', err.message);
            if (stderr) console.error('[Apps] PowerShell stderr:', stderr.slice(0, 600));
        }
        // Clean up temp script
        try { fs.unlinkSync(psPath); } catch (_) {}
    });

    proc.on('error', err => console.error('[Apps] PowerShell spawn error:', err.message));
}

async function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            webSecurity: true,
        },
    });

    // Grant microphone + speech recognition permission
    mainWindow.webContents.session.setPermissionRequestHandler((_webContents, permission, callback) => {
        const allowed = ['media', 'microphone', 'audioCapture', 'speech'];
        callback(allowed.includes(permission));
    });

    mainWindow.webContents.session.setPermissionCheckHandler((_webContents, permission) => {
        const allowed = ['media', 'microphone', 'audioCapture', 'speech'];
        return allowed.includes(permission);
    });

    // Register next-electron-rsc interceptor on this window's session (prod only)
    const stopIntercept = IS_PACKAGED
        ? await createInterceptor({ session: mainWindow.webContents.session })
        : null;
    mainWindow.on('closed', () => stopIntercept?.());

    mainWindow.setMenuBarVisibility(false);
    mainWindow.setIcon(nativeImage.createFromPath(path.join(__dirname, '../public/logo.png')), 'Airi');
    mainWindow.loadURL(localhostUrl + '/');
}

app.whenReady().then(async () => {
    ipcMain.on('trigger-snap-overlay', () => {
        console.log('[IPC] trigger-snap-overlay received');
        snapToOverlay();
    });
    setupDb();
    buildInstalledAppsJson();
    await ensureModels(MODELS_DIR);
    startAgentServer();
    startLlama();
    startEmbeddingServer();
    startSearxng();
    await createWindow();
});

app.on('before-quit', () => {
    [llamaProcess, embeddingProcess, searxngProcess, agentProcess].forEach(proc => {
        if (proc && !proc.killed) proc.kill();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
});
