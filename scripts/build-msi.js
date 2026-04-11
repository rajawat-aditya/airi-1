const { MSICreator } = require('electron-wix-msi');
const path = require('path');
const fs = require('fs');

// electron-wix-msi's detect-wix only checks PATH, so inject WiX bin dir
const WIX_BIN = 'C:\\Program Files (x86)\\WiX Toolset v3.14\\bin';
if (!process.env.PATH.includes(WIX_BIN)) {
  process.env.PATH = WIX_BIN + ';' + process.env.PATH;
}

const APP_DIR = path.resolve(__dirname, '../build/win-unpacked');
const OUT_DIR = path.resolve(__dirname, '../build/msi');
const ICON = path.resolve(__dirname, '../public/logo.ico');

if (!fs.existsSync(APP_DIR)) {
  console.error('win-unpacked not found. Run electron-builder --win dir first.');
  process.exit(1);
}

fs.mkdirSync(OUT_DIR, { recursive: true });

const pkg = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../package.json'), 'utf8'));

const msiCreator = new MSICreator({
  appDirectory: APP_DIR,
  outputDirectory: OUT_DIR,
  description: pkg.description,
  exe: 'Airi',
  name: 'Airi',
  manufacturer: 'Slew Inc.',
  version: pkg.version,
  shortcutFolderName: 'Airi',
  icon: ICON,
  windowsKit: 'C:\\Program Files (x86)\\WiX Toolset v3.14\\bin',
  ui: {
    chooseDirectory: true,
  },
  arch: 'x64',
  language: 1033,
});

(async () => {
  console.log('Crafting MSI template...');
  await msiCreator.create();
  console.log('Compiling MSI...');
  await msiCreator.compile();
  console.log(`Done! MSI saved to: ${OUT_DIR}`);
})().catch(err => {
  console.error(err);
  process.exit(1);
});
