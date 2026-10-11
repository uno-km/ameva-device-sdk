/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * ameva-device-sdk
 * ================
 * Authoritative on-device telemetry and storage foundation for Node.js / JavaScript.
 * Open-Source under Apache-2.0.
 */

'use strict';

const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');

/**
 * Authoritative detection for Android Termux environment.
 * @returns {boolean}
 */
function isTermux() {
  if (process.env.TERMUX_VERSION || process.env.TERMUX_APP_PID) {
    return true;
  }
  const prefix = process.env.PREFIX || '';
  if (prefix.includes('com.termux')) {
    return true;
  }
  try {
    return fs.existsSync('/data/data/com.termux');
  } catch {
    return false;
  }
}

/**
 * Check whether running on Android platform.
 * Within on-device Termux ecosystem, running in Termux implies Android.
 * @returns {boolean}
 */
function isAndroid() {
  return isTermux();
}

/**
 * Check if execution is running inside a PRoot container.
 * @returns {boolean}
 */
function isProot() {
  if (process.env.PROOT_TMP_DIR || process.env.PROOT) {
    return true;
  }
  try {
    const mountinfo = '/proc/1/mountinfo';
    if (fs.existsSync(mountinfo)) {
      const content = fs.readFileSync(mountinfo, 'utf8');
      return content.toLowerCase().includes('proot');
    }
  } catch {}
  return false;
}

/**
 * Get total and available RAM in megabytes without synthetic metric stubs.
 * @returns {{ totalMb: number, availableMb: number }}
 */
function getMemoryInfo() {
  let totalMb = 0;
  let availMb = 0;

  // 1. Linux / Android /proc/meminfo
  if (fs.existsSync('/proc/meminfo')) {
    try {
      const content = fs.readFileSync('/proc/meminfo', 'utf8');
      for (const line of content.split('\n')) {
        const parts = line.trim().split(/\s+/);
        if (parts.length >= 2) {
          if (parts[0] === 'MemTotal:') {
            totalMb = parseFloat(parts[1]) / 1024.0;
          } else if (parts[0] === 'MemAvailable:' || parts[0] === 'MemFree:') {
            if (availMb === 0 || parts[0] === 'MemAvailable:') {
              availMb = parseFloat(parts[1]) / 1024.0;
            }
          }
        }
      }
      if (totalMb > 0) {
        return {
          totalMb: Math.round(totalMb * 10) / 10,
          availableMb: Math.round(availMb * 10) / 10,
        };
      }
    } catch {}
  }

  // 2. Cross-platform OS fallback
  try {
    totalMb = os.totalmem() / (1024 * 1024);
    availMb = os.freemem() / (1024 * 1024);
  } catch {}

  return {
    totalMb: Math.round(totalMb * 10) / 10,
    availableMb: Math.round(availMb * 10) / 10,
  };
}

/**
 * Read CPU microarchitecture features from /proc/cpuinfo and architecture flags.
 * @returns {{ neon: boolean, fp16: boolean, dotprod: boolean }}
 */
function readCpuFeatures() {
  const isArm = process.arch === 'arm64';
  const features = {
    neon: isArm,
    fp16: false,
    dotprod: false,
  };

  try {
    if (fs.existsSync('/proc/cpuinfo')) {
      const content = fs.readFileSync('/proc/cpuinfo', 'utf8').toLowerCase();
      features.neon = features.neon || content.includes('neon') || content.includes('asimd');
      features.fp16 = content.includes('fp16') || content.includes('fphp') || content.includes('asimdhp');
      features.dotprod = content.includes('dotprod') || content.includes('asimddp');
    }
  } catch {}

  return features;
}

/**
 * Calculate recommended compute thread count balancing throughput and stability.
 * @param {number} [cores] Optional core count override.
 * @returns {number}
 */
function getOptimalThreads(cores) {
  const count = cores && cores > 0 ? cores : (os.cpus() ? os.cpus().length : 4);
  if (count >= 8) return 4;
  if (count >= 6) return 4;
  if (count >= 4) return Math.min(3, count);
  return Math.max(1, count);
}

/**
 * Probe for usable Vulkan driver across Android system libraries and Termux prefix.
 * @returns {{ hasVulkan: boolean, description: string | null }}
 */
function probeVulkanDriver() {
  const candidates = [
    { path: '/system/lib64/libvulkan.so', desc: 'Android System 64-bit Vulkan Driver' },
    { path: '/vendor/lib64/hw/vulkan.adreno.so', desc: 'Qualcomm Adreno Vulkan Driver' },
    { path: '/vendor/lib64/libvulkan.so', desc: 'Vendor 64-bit Vulkan Driver' },
    { path: '/system/lib/libvulkan.so', desc: 'Android System 32-bit Vulkan Driver' },
    { path: '/vendor/lib/hw/vulkan.adreno.so', desc: 'Qualcomm Adreno 32-bit Vulkan Driver' },
    { path: '/data/data/com.termux/files/usr/lib/libvulkan.so', desc: 'Termux Userland Vulkan Driver' },
  ];

  for (const { path: p, desc } of candidates) {
    try {
      if (fs.existsSync(p)) {
        return { hasVulkan: true, description: desc };
      }
    } catch {}
  }

  return { hasVulkan: false, description: null };
}

/**
 * Returns multi-tier model search paths adhering to AMEVA Shared Storage Specification.
 * @param {string} [submodule="models"] Subsystem name, e.g. "stt", "tts", "llama", "vision".
 * @returns {string[]}
 */
function getUnifiedModelSearchDirs(submodule = 'models') {
  const dirs = [];
  const cleanSub = submodule.toLowerCase().trim();

  // 1. Custom ENV override
  const envSub = process.env[`TERMUX_${cleanSub.toUpperCase()}_MODELS_DIR`];
  if (envSub) dirs.push(envSub);

  const envDir = process.env.AMEVA_MODELS_DIR;
  if (envDir) {
    dirs.push(path.join(envDir, cleanSub));
    dirs.push(envDir);
  }

  // 2. Prefixes (home + Termux prefix home)
  const home = os.homedir();
  const prefixes = [home];
  const prefixEnv = process.env.PREFIX;
  if (prefixEnv) {
    const termuxHome = path.resolve(prefixEnv, '../home');
    if (termuxHome !== home) {
      prefixes.push(termuxHome);
    }
  }

  for (const base of prefixes) {
    dirs.push(path.join(base, 'models', cleanSub));
    dirs.push(path.join(base, 'models'));
    dirs.push(path.join(base, 'ameva-models', cleanSub));
    dirs.push(path.join(base, 'ameva-models'));
    dirs.push(path.join(base, '.cache', 'ameva', 'models', cleanSub));
    dirs.push(path.join(base, '.cache', 'ameva', 'models'));
    dirs.push(path.join(base, '.cache', `termux-${cleanSub}`, 'models'));
    dirs.push(path.join(base, `.termux-${cleanSub}`, 'models'));
  }

  if (prefixEnv) {
    dirs.push(path.join(prefixEnv, 'share', `termux-${cleanSub}`, 'models'));
  }

  // Deduplicate preserving precedence
  const seen = new Set();
  const uniqueDirs = [];
  for (const d of dirs) {
    const normalized = path.normalize(d);
    if (!seen.has(normalized)) {
      seen.add(normalized);
      uniqueDirs.push(normalized);
    }
  }

  return uniqueDirs;
}

/**
 * Validate a file's SHA-256 checksum against an expected hash in constant memory.
 * @param {string} filePath Path to target file.
 * @param {string} expectedSha256 Expected hexadecimal SHA-256 string.
 * @returns {Promise<boolean>}
 */
function verifyFileSha256(filePath, expectedSha256) {
  return new Promise((resolve) => {
    try {
      if (!fs.existsSync(filePath)) {
        return resolve(false);
      }
      const cleanExpected = expectedSha256.trim().toLowerCase();
      const hash = crypto.createHash('sha256');
      const stream = fs.createReadStream(filePath);

      stream.on('data', (chunk) => hash.update(chunk));
      stream.on('end', () => {
        const digest = hash.digest('hex').toLowerCase();
        resolve(digest === cleanExpected);
      });
      stream.on('error', () => resolve(false));
    } catch {
      resolve(false);
    }
  });
}

/**
 * Validate a file's SHA-256 synchronously.
 * @param {string} filePath Path to target file.
 * @param {string} expectedSha256 Expected hexadecimal SHA-256 string.
 * @returns {boolean}
 */
function verifyFileSha256Sync(filePath, expectedSha256) {
  try {
    if (!fs.existsSync(filePath)) return false;
    const cleanExpected = expectedSha256.trim().toLowerCase();
    const hash = crypto.createHash('sha256');
    const buffer = fs.readFileSync(filePath);
    hash.update(buffer);
    return hash.digest('hex').toLowerCase() === cleanExpected;
  } catch {
    return false;
  }
}

/**
 * Atomically replace targetPath with tempPath.
 * @param {string} tempPath Path to temporary file.
 * @param {string} targetPath Path to final file.
 */
function atomicReplace(tempPath, targetPath) {
  const targetDir = path.dirname(targetPath);
  if (!fs.existsSync(targetDir)) {
    fs.mkdirSync(targetDir, { recursive: true });
  }
  fs.renameSync(tempPath, targetPath);
}

/**
 * Authoritative Python 3 runtime resolver for Termux & cross-platform execution.
 * Validates executable existence without throwing ENOENT.
 * @returns {string} Path or command name to invoke Python 3.
 */
function resolvePythonRuntime() {
  const { execSync } = require('child_process');
  if (process.env.PYTHON && fs.existsSync(process.env.PYTHON)) {
    return process.env.PYTHON;
  }
  const termuxBin = '/data/data/com.termux/files/usr/bin/python3';
  if (fs.existsSync(termuxBin)) {
    return termuxBin;
  }
  const termuxBinAlt = '/data/data/com.termux/files/usr/bin/python';
  if (fs.existsSync(termuxBinAlt)) {
    return termuxBinAlt;
  }
  const candidates = ['python3', 'python'];
  for (const cmd of candidates) {
    try {
      const checkCmd = process.platform === 'win32' ? `where ${cmd}` : `command -v ${cmd}`;
      const res = execSync(checkCmd, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
      if (res) return cmd;
    } catch (_) {}
  }
  return 'python3';
}

const runtimeGuard = require('./runtime_guard');

module.exports = {
  ...runtimeGuard,
  version: '0.2.0',
  isTermux,
  isAndroid,
  isProot,
  getMemoryInfo,
  readCpuFeatures,
  getOptimalThreads,
  probeVulkanDriver,
  getUnifiedModelSearchDirs,
  resolvePythonRuntime,
  verifyFileSha256,
  verifyFileSha256Sync,
  atomicReplace,
};
