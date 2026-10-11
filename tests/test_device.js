/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * Unit tests for ameva-device-sdk Node.js implementation
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const dev = require('../index');

console.log('Running ameva-device-sdk Node.js test suite...');

// 1. Env check
assert.strictEqual(dev.isAndroid(), dev.isTermux());
assert.strictEqual(typeof dev.isProot(), 'boolean');

// 1.1 Python runtime resolution
const pyRuntime = dev.resolvePythonRuntime();
assert.strictEqual(typeof pyRuntime, 'string');
assert.ok(pyRuntime.length > 0);

// 2. Memory info
const mem = dev.getMemoryInfo();
assert.strictEqual(typeof mem.totalMb, 'number');
assert.strictEqual(typeof mem.availableMb, 'number');
assert.ok(mem.totalMb > 0);

// 3. CPU features
const cpu = dev.readCpuFeatures();
assert.strictEqual(typeof cpu.neon, 'boolean');
assert.strictEqual(typeof cpu.fp16, 'boolean');
assert.strictEqual(typeof cpu.dotprod, 'boolean');

// 4. Optimal threads
assert.strictEqual(dev.getOptimalThreads(8), 4);
assert.strictEqual(dev.getOptimalThreads(6), 4);
assert.strictEqual(dev.getOptimalThreads(4), 3);
assert.strictEqual(dev.getOptimalThreads(2), 2);
assert.strictEqual(dev.getOptimalThreads(1), 1);

// 5. Unified search dirs
const dirs = dev.getUnifiedModelSearchDirs('diffusion');
assert.ok(dirs.length > 0);
assert.strictEqual(dirs.length, new Set(dirs).size, 'Search dirs must be deduplicated');

// 6. SHA-256 and atomicReplace
const tmpDir = path.join(__dirname, 'tmp_test');
if (!fs.existsSync(tmpDir)) fs.mkdirSync(tmpDir, { recursive: true });

const testFile = path.join(tmpDir, 'node_test.bin');
const tempSrc = path.join(tmpDir, 'node_temp.bin');
const payload = 'AMEVA Node.js Test Payload 2026';
const expectedHash = crypto.createHash('sha256').update(payload).digest('hex');

fs.writeFileSync(tempSrc, payload);
dev.atomicReplace(tempSrc, testFile);
assert.ok(fs.existsSync(testFile));
assert.ok(!fs.existsSync(tempSrc));

// Sync hash verification
assert.strictEqual(dev.verifyFileSha256Sync(testFile, expectedHash), true);
assert.strictEqual(dev.verifyFileSha256Sync(testFile, '0000000000000000000000000000000000000000000000000000000000000000'), false);

// Async hash verification
dev.verifyFileSha256(testFile, expectedHash).then((matched) => {
  assert.strictEqual(matched, true);
  // Clean up
  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('All Node.js tests PASSED successfully.');
}).catch((err) => {
  console.error(err);
  process.exit(1);
});
