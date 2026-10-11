/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * Tests for the GPU runtime guard (Node.js). The installed runtime is simulated through
 * the probe option; no GPU and no real ameva-runtime are needed.
 */
const assert = require('assert');
const { spawnSync } = require('child_process');
const path = require('path');
const dev = require('../index');

console.log('Running runtime guard tests...');

assert.deepStrictEqual(dev.parseVersion('2.8.1'), [2, 8, 1]);
assert.deepStrictEqual(dev.parseVersion('2.8.1rc1'), [2, 8, 1]);
assert.deepStrictEqual(dev.parseVersion('garbage'), []);

// Missing runtime
assert.throws(() => dev.requireAmevaRuntime('termux-test', 'GPU inference', { probe: () => null }), (err) => {
  assert.ok(err instanceof dev.AmevaRuntimeRequiredError);
  assert.strictEqual(err.code, 'AMU_ERR_RUNTIME_REQUIRED');
  assert.ok(err.message.startsWith('[AMU_ERR_RUNTIME_REQUIRED] termux-test:'));
  assert.ok(err.message.includes('not installed'));
  assert.ok(err.message.includes('no CPU fallback was used'));
  assert.ok(err.message.includes('pip install "ameva-runtime>=2.0.0"'));
  assert.ok(err.message.includes('npm install -g @ameva/runtime'));
  assert.ok(err.message.includes('AMUDA'));
  assert.ok(err.message.includes('https://github.com/uno-km/ameva-runtime-releases'));
  assert.ok(err.message.includes('--device cpu'));
  assert.ok(/^[\x00-\x7f]*$/.test(err.message), 'message must be ASCII');
  return true;
});

// Too old
assert.throws(() => dev.requireAmevaRuntime('termux-test', 'GPU', { probe: () => '1.9.0', minVersion: '2.0.0' }),
  (err) => err.found === '1.9.0' && err.message.includes('1.9.0 is installed, but >= 2.0.0 is required'));

// Unreadable version is rejected, not assumed
assert.throws(() => dev.requireAmevaRuntime('termux-test', 'GPU', { probe: () => 'unknown' }),
  (err) => err.message.includes('version could not be read'));

// Sufficient
assert.strictEqual(dev.requireAmevaRuntime('termux-test', 'GPU', { probe: () => '2.8.1', minVersion: '2.8.0' }), '2.8.1');
assert.strictEqual(dev.requireAmevaRuntime('termux-test', 'GPU', { probe: () => '2.10.0', minVersion: '2.9.9' }), '2.10.0');

// Exit variant in a child process: stderr text and status 69, nothing on stdout
const script = `const d=require(${JSON.stringify(path.join(__dirname, '..', 'index'))});d.exitIfRuntimeMissing('termux-test','GPU inference',{probe:()=>null});console.log('SHOULD NOT PRINT');`;
const res = spawnSync(process.execPath, ['-e', script], { encoding: 'utf8' });
assert.strictEqual(res.status, 69);
assert.strictEqual(res.stdout, '');
assert.ok(res.stderr.includes('AMU_ERR_RUNTIME_REQUIRED'));

console.log('runtime guard tests PASS');
