/**
 * Copies .next/static and public into .next/standalone/airi so electron-builder
 * can pick them up via the files glob.
 * Also patches required-server-files.json to remove hardcoded absolute paths.
 *
 * Next.js standalone output for a package named "airi" goes to .next/standalone/airi/
 * The electron-builder files glob picks up .next/standalone/airi/**
 */
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');

// Package name must match the "name" field in package.json
const PKG_NAME = require(path.join(root, 'package.json')).name;
const standaloneDir = path.join(root, '.next', 'standalone', PKG_NAME);

// Fallback: if Next.js put standalone at root (no subdirectory), use that
const standaloneRoot = fs.existsSync(standaloneDir)
    ? standaloneDir
    : path.join(root, '.next', 'standalone');

console.log('[copy-next-static] Standalone dir:', standaloneRoot);

function copyDir(src, dest) {
    if (!fs.existsSync(src)) return;
    fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
        const s = path.join(src, entry.name);
        const d = path.join(dest, entry.name);
        if (entry.isDirectory()) copyDir(s, d);
        else fs.copyFileSync(s, d);
    }
}

// Copy static assets into the standalone dir
copyDir(
    path.join(root, '.next', 'static'),
    path.join(standaloneRoot, '.next', 'static')
);
copyDir(
    path.join(root, 'public'),
    path.join(standaloneRoot, 'public')
);

// Patch required-server-files.json — remove hardcoded outputFileTracingRoot
const serverFilesPath = path.join(standaloneRoot, '.next', 'required-server-files.json');
if (fs.existsSync(serverFilesPath)) {
    const serverFiles = JSON.parse(fs.readFileSync(serverFilesPath, 'utf8'));
    if (serverFiles.config) {
        delete serverFiles.config.outputFileTracingRoot;
        serverFiles.config.distDir = '.next';
    }
    fs.writeFileSync(serverFilesPath, JSON.stringify(serverFiles, null, 2), 'utf8');
    console.log('[copy-next-static] Patched required-server-files.json');
}

console.log('[copy-next-static] Done');

// ── Patch next-electron-rsc to allow external http:// requests ───────────────
// The library asserts all http requests are localhost, breaking Auth0 redirects.
// We replace the assert with a net.fetch passthrough for non-localhost URLs.
const rscIndexPath = path.join(root, 'node_modules', 'next-electron-rsc', 'build', 'index.js');
if (fs.existsSync(rscIndexPath)) {
    let src = fs.readFileSync(rscIndexPath, 'utf8');
    const oldAssert = `(0, node_assert_1.default)(request.url.startsWith(localhostUrl), 'External HTTP not supported, use HTTPS');`;
    const newCheck = `if (!request.url.startsWith(localhostUrl)) {
                        const { net } = require('electron');
                        return net.fetch(request.url, {
                            method: request.method,
                            headers: Object.fromEntries(request.headers.entries()),
                            body: ['GET', 'HEAD'].includes(request.method) ? undefined : request.body,
                            duplex: 'half',
                            bypassCustomProtocolHandlers: true,
                        });
                    }`;
    if (src.includes(oldAssert)) {
        src = src.replace(oldAssert, newCheck);
        fs.writeFileSync(rscIndexPath, src, 'utf8');
        console.log('[copy-next-static] Patched next-electron-rsc for external http support');
    } else if (!src.includes('bypassCustomProtocolHandlers')) {
        console.warn('[copy-next-static] WARNING: next-electron-rsc patch target not found — may already be patched or version changed');
    }
}
