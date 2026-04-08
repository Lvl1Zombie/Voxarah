/**
 * Copies the FastAPI frontend assets into tauri-app/frontend/
 * so Tauri can bundle them as its static webview content.
 * Run automatically as 'prebuild' before every tauri build/dev.
 */

const fs   = require('fs');
const path = require('path');

const ROOT     = path.resolve(__dirname, '../../audioflow');
const FRONTEND = path.resolve(__dirname, '../frontend');

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(s, d);
    } else {
      fs.copyFileSync(s, d);
    }
  }
}

// index.html → frontend/index.html
fs.mkdirSync(FRONTEND, { recursive: true });
fs.copyFileSync(
  path.join(ROOT, 'templates', 'index.html'),
  path.join(FRONTEND, 'index.html')
);

// static/ → frontend/static/
copyDir(
  path.join(ROOT, 'static'),
  path.join(FRONTEND, 'static')
);

console.log('[prepare-frontend] Done — frontend/ is up to date.');
