const assert = require('assert');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const js = fs.readFileSync(path.join(root, 'SABLON_V2_MIMARI', 'static', 'js', 'petek_editor_v477.js'), 'utf8');
const html = fs.readFileSync(path.join(root, 'SABLON_V2_MIMARI', 'templates', 'index.html'), 'utf8');

assert.ok(js.includes('async function previewAllArtwork()'));
assert.ok(js.includes("api('/api/petek/preview-artwork',payload)"));
assert.ok(js.includes("view.card.classList.add('failed')"));
assert.ok(js.includes('diagnostic_preview'));
assert.ok(html.includes('id="petekV477PreviewAll"'));
assert.ok(html.includes('id="petekV477BatchPreviewGrid"'));
const previewFunction = js.slice(js.indexOf('async function previewAllArtwork()'),
  js.indexOf('function limited()'));
assert.ok(!previewFunction.includes('/api/petek/approve'));

console.log('batch preview isolation contract: PASS');
