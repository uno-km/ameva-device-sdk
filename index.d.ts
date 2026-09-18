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
