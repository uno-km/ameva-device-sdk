# ameva-device-sdk

> Authoritative on-device telemetry, capability probing, and shared storage foundation for the AMEVA & Android Termux ecosystem.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-16+-339933.svg?logo=node.js&logoColor=white)](https://nodejs.org/)

---

## Architecture & Purpose

`ameva-device-sdk` serves as the Single Source of Truth (SSOT) foundation across all submodules in the `uno-km/termux` and `uno-km/ameva` ecosystems (including `termux-llamacpp`, `termux-vision`, `termux-diffusion`, `termux-tts`, `termux-stt`, `termux-bitnet`, and `termux-playwright`).

It eliminates cross-project fragmentation (AST drift) by unifying:
1. **Environment Diagnostics**: Authoritative `is_termux()`, `is_android()`, `is_proot()`.
2. **Hardware Telemetry**: Direct `/proc/meminfo` RAM detection, ARM64 feature flags (`neon`, `fp16`, `dotprod`), Vulkan ICD discovery, and thermal/compute thread heuristics.
3. **Storage & Verification**: Multi-tier directory resolution according to the *AMEVA Shared Storage Specification*, streaming SHA-256 integrity checks, and atomic file replacements.
4. **Dual-Engine ABI**: 100% functional parity between Python (`ameva_device`) and Node.js (`ameva-device-sdk`).

---

## Installation

### Python
```bash
pip install ./ameva-device-sdk
# or within editable development mode:
pip install -e ./dev/ameva/ameva-device-sdk
```

### Node.js
```bash
npm install ./ameva-device-sdk
# or link locally:
npm link ./dev/ameva/ameva-device-sdk
```

---

## API Specification

### 1. Python API (`import ameva_device as dev`)

```python
import ameva_device as dev

# Environment
is_termux: bool = dev.is_termux()
is_android: bool = dev.is_android()
is_proot: bool = dev.is_proot()

# Hardware Telemetry
total_mb, avail_mb = dev.get_memory_info()
features: dict[str, bool] = dev.read_cpu_features()  # {'neon': bool, 'fp16': bool, 'dotprod': bool}
threads: int = dev.get_optimal_threads()
has_vulkan, desc = dev.probe_vulkan_driver()

# Storage & Cryptographic Verification
search_dirs = dev.get_unified_model_search_dirs(submodule="vision")
is_valid = dev.verify_file_sha256("model.bin", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
dev.atomic_replace("model.bin.tmp", "model.bin")
```

### 2. JavaScript / TypeScript API (`const dev = require('ameva-device-sdk')`)

```typescript
import {
  isTermux,
  isAndroid,
  isProot,
  getMemoryInfo,
  readCpuFeatures,
  getOptimalThreads,
  probeVulkanDriver,
  getUnifiedModelSearchDirs,
  verifyFileSha256,
  verifyFileSha256Sync,
  atomicReplace,
} from 'ameva-device-sdk';

// Hardware Telemetry
const { totalMb, availableMb } = getMemoryInfo();
const { neon, fp16, dotprod } = readCpuFeatures();
const optimalThreads = getOptimalThreads();

// Storage Resolution
const searchDirs: string[] = getUnifiedModelSearchDirs('llamacpp');

// Cryptographic Verification
const valid = await verifyFileSha256('model.gguf', '<sha256_hash>');
```

---

## Verification & Compliance

All interfaces are strictly validated against:
- Automated regression test suites (`python tests/test_device.py`, `node tests/test_device.js`).
- OpenSSF best practices, zero synthetic stubs, and strict Linux ABI specifications.

---

## License

Apache License 2.0. Copyright (c) 2026 uno-km / AMEVA Systems Team.
