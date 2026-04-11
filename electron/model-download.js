const { BrowserWindow, ipcMain } = require('electron');
const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');

const MODELS = [
  {
    id: 'main',
    url: 'https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF/resolve/main/Qwen3VL-2B-Instruct-Q4_K_M.gguf',
    filename: 'Qwen3VL-2B-Instruct-Q4_K_M.gguf',
    subdir: 'models--Qwen--Qwen3-VL-2B-Instruct-GGUF/snapshots/52d6c8ffea26cc873ac5ad116f8631268d7eb503',
  },
  {
    id: 'mmproj',
    url: 'https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct-GGUF/resolve/main/mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf',
    filename: 'mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf',
    subdir: 'models--Qwen--Qwen3-VL-2B-Instruct-GGUF/snapshots/52d6c8ffea26cc873ac5ad116f8631268d7eb503',
  },
  {
    id: 'embed',
    url: 'https://huggingface.co/unsloth/embeddinggemma-300m-GGUF/resolve/main/embeddinggemma-300m-Q4_0.gguf',
    filename: 'embeddinggemma-300m-Q4_0.gguf',
    subdir: '',
  },
];

function modelsExist(modelsDir) {
  return MODELS.every(m => {
    const dest = m.subdir
      ? path.join(modelsDir, m.subdir, m.filename)
      : path.join(modelsDir, m.filename);
    return fs.existsSync(dest);
  });
}

function downloadFile(url, dest, onProgress) {
  return new Promise((resolve, reject) => {
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    const tmp = dest + '.part';
    const file = fs.createWriteStream(tmp);

    const get = (url) => {
      const mod = url.startsWith('https') ? https : http;
      mod.get(url, { headers: { 'User-Agent': 'Airi-Installer/1.0' } }, res => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          return get(res.headers.location);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
        }
        const total = parseInt(res.headers['content-length'] || '0', 10);
        let received = 0;
        res.on('data', chunk => {
          received += chunk.length;
          file.write(chunk);
          if (total > 0) onProgress(Math.round((received / total) * 100));
        });
        res.on('end', () => {
          file.end();
          fs.renameSync(tmp, dest);
          resolve();
        });
        res.on('error', reject);
      }).on('error', reject);
    };
    get(url);
  });
}

async function downloadModels(modelsDir, win) {
  const send = (model, percent, status) => {
    if (win && !win.isDestroyed()) {
      win.webContents.send('download-progress', { model, percent, status });
    }
  };

  for (const model of MODELS) {
    const dest = model.subdir
      ? path.join(modelsDir, model.subdir, model.filename)
      : path.join(modelsDir, model.filename);

    if (fs.existsSync(dest)) {
      send(model.id, 100, `${model.filename} already present`);
      continue;
    }

    send(model.id, 0, `Downloading ${model.filename}...`);
    await downloadFile(model.url, dest, pct => send(model.id, pct, `Downloading ${model.filename}... ${pct}%`));
    send(model.id, 100, `${model.filename} done`);
  }
}

async function ensureModels(modelsDir, parentWin) {
  if (modelsExist(modelsDir)) return;

  const win = new BrowserWindow({
    width: 500,
    height: 320,
    resizable: false,
    frame: false,
    show: false,
    parent: parentWin || undefined,
    webPreferences: { nodeIntegration: true, contextIsolation: false },
  });

  win.loadFile(path.join(__dirname, 'model-downloader.html'));
  win.once('ready-to-show', () => win.show());

  await downloadModels(modelsDir, win);

  if (!win.isDestroyed()) win.close();
}

module.exports = { ensureModels, modelsExist };
