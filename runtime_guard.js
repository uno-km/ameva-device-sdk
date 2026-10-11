/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * Runtime guard for GPU-requiring features (Node.js counterpart of ameva_device.runtime_guard).
 *
 * GPU execution is provided by ameva-runtime (AMUDA). When a GPU run is requested and the
 * runtime is missing or too old, the process must stop with an explicit error that explains
 * how to install it. It must not continue on the CPU without telling the user.
 *
 * Detection checks that the npm package (@ameva/runtime) or the Python package
 * (ameva-runtime) is installed at the requested version. It does not prove that a GPU
 * device works; use `ameva-run doctor` for that.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const RUNTIME_REQUIRED_CODE = 'AMU_ERR_RUNTIME_REQUIRED';
// Exit status used by command-line entry points (sysexits EX_UNAVAILABLE).
const RUNTIME_REQUIRED_EXIT_CODE = 69;
const DEFAULT_MIN_VERSION = '2.0.0';
const RUNTIME_PYPI_NAME = 'ameva-runtime';
const RUNTIME_NPM_NAME = '@ameva/runtime';
const RUNTIME_RELEASES_URL = 'https://github.com/uno-km/ameva-runtime-releases';

/** Leading numeric components of a version string: '2.8.1rc1' -> [2, 8, 1]. */
function parseVersion(text) {
  const parts = [];
  for (const piece of String(text).trim().split('.')) {
    const m = /^\d+/.exec(piece);
    if (!m) break;
    parts.push(parseInt(m[0], 10));
  }
  return parts;
}

function compareVersions(a, b) {
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) {
    const x = a[i] || 0;
    const y = b[i] || 0;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

function npmRuntimeVersion() {
  const searchRoots = [process.cwd(), __dirname, ...(require.main && require.main.paths ? require.main.paths : [])];
  const globalRoots = [];
  if (process.env.PREFIX) globalRoots.push(path.join(process.env.PREFIX, 'lib', 'node_modules'));
  try {
    const res = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['root', '-g'],
      { encoding: 'utf8', timeout: 8000, stdio: ['ignore', 'pipe', 'ignore'] });
    if (res.status === 0 && res.stdout.trim()) globalRoots.push(res.stdout.trim());
  } catch (_) { /* npm not available */ }
  try {
    const manifest = require.resolve(RUNTIME_NPM_NAME + '/package.json', { paths: searchRoots });
    return String(JSON.parse(fs.readFileSync(manifest, 'utf8')).version || 'unknown');
  } catch (_) { /* not resolvable from the local tree */ }
  for (const root of globalRoots) {
    const manifest = path.join(root, '@ameva', 'runtime', 'package.json');
    try {
      return String(JSON.parse(fs.readFileSync(manifest, 'utf8')).version || 'unknown');
    } catch (_) { /* try next root */ }
  }
  return null;
}

function pythonRuntimeVersion() {
  const candidates = [];
  if (process.env.PYTHON) candidates.push(process.env.PYTHON);
  candidates.push('python3', 'python');
  for (const py of candidates) {
    try {
      const res = spawnSync(py, ['-c', 'import ameva_runtime; print(getattr(ameva_runtime, "__version__", "unknown"))'],
        { encoding: 'utf8', timeout: 15000, stdio: ['ignore', 'pipe', 'ignore'] });
      if (res.status === 0 && res.stdout.trim()) return res.stdout.trim().split(/\r?\n/).pop();
    } catch (_) { /* interpreter missing */ }
  }
  return null;
}

/** Installed runtime version ('unknown' if installed but unreadable), or null when absent. */
function installedRuntimeVersion() {
  return npmRuntimeVersion() || pythonRuntimeVersion();
}

function runtimeRequiredMessage(component, feature, minVersion, found) {
  let state;
  if (found === null) state = 'ameva-runtime is not installed.';
  else if (found === 'unknown') state = `ameva-runtime is installed but its version could not be read (need >= ${minVersion}).`;
  else state = `ameva-runtime ${found} is installed, but >= ${minVersion} is required.`;
  return [
    `[${RUNTIME_REQUIRED_CODE}] ${component}: '${feature}' needs the AMEVA GPU runtime.`,
    state,
    'Nothing was run, and no CPU fallback was used.',
    '',
    'What is AMUDA / ameva-runtime:',
    "  AMUDA is AMEVA's GPU compute layer for Android phones (Vulkan and OpenCL on",
    '  Adreno and Mali GPUs). It ships inside ameva-runtime and runs the model kernels',
    "  on the phone's GPU. Without it this tool can only run on the CPU.",
    '',
    'Install:',
    `  pip:   pip install "${RUNTIME_PYPI_NAME}>=${minVersion}"`,
    `  npm:   npm install -g ${RUNTIME_NPM_NAME}`,
    '  check: ameva-run doctor',
    `  Releases and documentation: ${RUNTIME_RELEASES_URL}`,
    '',
    'To run on the CPU instead, request it explicitly (for example --device cpu).',
    '',
  ].join('\n');
}

class AmevaRuntimeRequiredError extends Error {
  constructor(component, feature, minVersion, found) {
    super(runtimeRequiredMessage(component, feature, minVersion, found));
    this.name = 'AmevaRuntimeRequiredError';
    this.code = RUNTIME_REQUIRED_CODE;
    this.component = component;
    this.feature = feature;
    this.minVersion = minVersion;
    this.found = found;
  }
}

/**
 * Returns the installed runtime version, or throws AmevaRuntimeRequiredError.
 * @param {string} component  e.g. 'termux-bitnet'
 * @param {string} [feature]  what was requested, e.g. 'GPU inference'
 * @param {{minVersion?: string, probe?: () => (string|null)}} [options]  probe is for tests
 */
function requireAmevaRuntime(component, feature = 'GPU execution', options = {}) {
  const minVersion = options.minVersion || DEFAULT_MIN_VERSION;
  const found = (options.probe || installedRuntimeVersion)();
  if (found === null || found === undefined) throw new AmevaRuntimeRequiredError(component, feature, minVersion, null);
  if (found === 'unknown' || compareVersions(parseVersion(found), parseVersion(minVersion)) < 0) {
    throw new AmevaRuntimeRequiredError(component, feature, minVersion, found);
  }
  return found;
}

/** Command-line variant: writes the explanation to stderr and exits with status 69. */
function exitIfRuntimeMissing(component, feature = 'GPU execution', options = {}) {
  try {
    return requireAmevaRuntime(component, feature, options);
  } catch (err) {
    if (!(err instanceof AmevaRuntimeRequiredError)) throw err;
    process.stderr.write(err.message);
    process.exit(RUNTIME_REQUIRED_EXIT_CODE);
  }
  return undefined;
}

module.exports = {
  RUNTIME_REQUIRED_CODE,
  RUNTIME_REQUIRED_EXIT_CODE,
  AmevaRuntimeRequiredError,
  parseVersion,
  installedRuntimeVersion,
  runtimeRequiredMessage,
  requireAmevaRuntime,
  exitIfRuntimeMissing,
};
