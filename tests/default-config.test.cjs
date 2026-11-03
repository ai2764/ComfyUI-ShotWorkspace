const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/workspace.js'), 'utf8');

test('new workspaces have provider-neutral LLM defaults and explicit opt-in unload', () => {
  const match = source.match(/const defaultConfig = (\{[^\n]+\});/);
  assert.ok(match, 'default config declaration exists');
  const config = vm.runInNewContext('(' + match[1] + ')');
  assert.equal(config.base_url, 'http://127.0.0.1:1234/v1');
  assert.equal(config.text_model, '');
  assert.equal(config.vision_model, '');
  assert.equal(config.unload_url, '');
  assert.equal(config.unload_before_generation, false);
});
