/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * TypeScript definitions for ameva-device-sdk
 */

export interface MemoryInfo {
  totalMb: number;
  availableMb: number;
}

export interface CpuFeatures {
  neon: boolean;
  fp16: boolean;
  dotprod: boolean;
}

export interface VulkanDriverProbe {
  hasVulkan: boolean;
  description: string | null;
}

export declare const version: string;

export declare function isTermux(): boolean;
export declare function isAndroid(): boolean;
export declare function isProot(): boolean;

export declare function getMemoryInfo(): MemoryInfo;
export declare function readCpuFeatures(): CpuFeatures;
export declare function getOptimalThreads(cores?: number): number;
export declare function probeVulkanDriver(): VulkanDriverProbe;

export declare function getUnifiedModelSearchDirs(submodule?: string): string[];
export declare function resolvePythonRuntime(): string;
export declare function verifyFileSha256(filePath: string, expectedSha256: string): Promise<boolean>;
export declare function verifyFileSha256Sync(filePath: string, expectedSha256: string): boolean;
export declare function atomicReplace(tempPath: string, targetPath: string): void;

export declare const RUNTIME_REQUIRED_CODE: 'AMU_ERR_RUNTIME_REQUIRED';
export declare const RUNTIME_REQUIRED_EXIT_CODE: 69;
export declare class AmevaRuntimeRequiredError extends Error {
  code: 'AMU_ERR_RUNTIME_REQUIRED';
  component: string;
  feature: string;
  minVersion: string;
  found: string | null;
  constructor(component: string, feature: string, minVersion: string, found: string | null);
}
export interface RuntimeGuardOptions {
  minVersion?: string;
  /** Replaces the installed-version probe; for tests. */
  probe?: () => string | null;
}
export declare function parseVersion(text: string): number[];
export declare function installedRuntimeVersion(): string | null;
export declare function runtimeRequiredMessage(component: string, feature: string, minVersion: string, found: string | null): string;
export declare function requireAmevaRuntime(component: string, feature?: string, options?: RuntimeGuardOptions): string;
export declare function exitIfRuntimeMissing(component: string, feature?: string, options?: RuntimeGuardOptions): string;
