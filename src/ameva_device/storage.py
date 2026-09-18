"""
ameva_device.storage
====================
Authoritative storage, path resolution, and cryptographic verification
conforming to the AMEVA Ecosystem Shared Storage Specification.
Open-Source under Apache-2.0.
"""
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger("ameva_device.storage")


def get_unified_model_search_dirs(submodule: str = "models") -> List[Path]:
    """Returns multi-tier model search paths adhering to the AMEVA Shared Storage Specification.
    
    Enables zero-redundancy model sharing across STT, TTS, LLaMA, Vision, Diffusion, BitNet, etc.
    Order of precedence:
    1. Custom environment variable override: AMEVA_MODELS_DIR or TERMUX_{SUBMODULE}_MODELS_DIR
    2. Primary user home paths and Termux prefix paths
    3. Multi-tier shared directories (models, ameva-models, .cache/ameva/models, .cache/termux-{submodule}/models)
    
    Args:
        submodule: Subsystem name, e.g. "stt", "tts", "llama", "vision", "diffusion", "bitnet".
        
    Returns:
        List of candidate Path objects deduplicated while preserving precedence.
    """
    dirs: List[Path] = []
    clean_submodule = submodule.lower().strip()

    # 1. Custom ENV override
    env_sub_override = os.environ.get(f"TERMUX_{clean_submodule.upper()}_MODELS_DIR")
    if env_sub_override:
        dirs.append(Path(env_sub_override))

    env_dir = os.environ.get("AMEVA_MODELS_DIR")
    if env_dir:
        p = Path(env_dir)
        dirs.extend([p / clean_submodule, p])

    # 2. Candidate prefixes (User Home + Termux $PREFIX/../home if different)
    home = Path.home()
    prefixes = [home]
    prefix_env = os.environ.get("PREFIX")
    if prefix_env:
        termux_home = Path(prefix_env).parent / "home"
        if termux_home != home:
            prefixes.append(termux_home)

    for base in prefixes:
        dirs.extend([
            base / "models" / clean_submodule,
            base / "models",
            base / "ameva-models" / clean_submodule,
            base / "ameva-models",
            base / ".cache" / "ameva" / "models" / clean_submodule,
            base / ".cache" / "ameva" / "models",
            base / ".cache" / f"termux-{clean_submodule}" / "models",
            base / f".termux-{clean_submodule}" / "models",
        ])

    # Termux shared package data dir
    if prefix_env:
        dirs.append(Path(prefix_env) / "share" / f"termux-{clean_submodule}" / "models")

    # Deduplicate while strictly preserving precedence order
    seen = set()
    unique_dirs = []
    for d in dirs:
        resolved = str(d.resolve()) if d.exists() else str(d)
        if resolved not in seen:
            seen.add(resolved)
            unique_dirs.append(d)

    return unique_dirs


def verify_file_sha256(
    file_path: Union[str, Path],
    expected_sha256: str,
    block_size: int = 65536,
) -> bool:
    """Validate a file's SHA-256 checksum against an expected hash in constant memory.
    
    Args:
        file_path: Path to the target file.
        expected_sha256: Expected hexadecimal SHA-256 hash.
        block_size: Buffer block size in bytes (default: 64 KiB).
        
    Returns:
        True if the file exists and its hash matches; False otherwise.
    """
    target = Path(file_path)
    if not target.is_file():
        return False

    clean_expected = expected_sha256.strip().lower()
    hasher = hashlib.sha256()

    try:
        with open(target, "rb") as f:
            while chunk := f.read(block_size):
                hasher.update(chunk)
        return hasher.hexdigest().lower() == clean_expected
    except (OSError, ValueError) as e:
        logger.debug("[ameva-device] Hash computation failed for %s: %s", target, e)
        return False


def check_disk_space(target_path: Union[str, Path], required_bytes: int) -> bool:
    """Verify whether the disk partition holding target_path has at least required_bytes available.
    
    Args:
        target_path: File or directory path to check partition for.
        required_bytes: Minimum required free storage in bytes.
        
    Returns:
        True if free disk space >= required_bytes, False otherwise.
    """
    target = Path(target_path)
    check_dir = target if target.is_dir() else target.parent
    try:
        check_dir.mkdir(parents=True, exist_ok=True)
        usage = shutil.disk_usage(check_dir)
        return usage.free >= required_bytes
    except OSError:
        return False


def atomic_replace(temp_path: Union[str, Path], target_path: Union[str, Path]) -> None:
    """Safely and atomically replace target_path with temp_path.
    
    Ensures parent directories exist before replacing.
    
    Args:
        temp_path: Path to temporary source file.
        target_path: Path to final destination file.
    """
    src = Path(temp_path)
    dst = Path(target_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dst)


def download_file_atomic(
    url: str,
    dest_path: Union[str, Path],
    expected_sha256: Optional[str] = None,
    expected_size: Optional[int] = None,
    chunk_size: int = 1024 * 1024,
    force: bool = False,
    show_progress: bool = True,
    user_agent: Optional[str] = None,
    timeout: float = 30.0,
) -> Path:
    """Authoritative on-device atomic model/artifact downloader template.
    
    Conforms to OpenSSF Zero-Corruption and BigTech atomic rename standards:
    1. Fast-Skip: If target exists and hash/size is valid, return immediately without network overhead.
    2. Isolation: Writes only to dest.part during streaming.
    3. Resume: Resumes partial downloads via HTTP Range headers.
    4. Verification: Streaming SHA-256 and byte-size checks before replacing destination.
    5. Atomic: Uses os.replace() so the destination file is never visible in an incomplete state.
    
    Args:
        url: Direct HTTP(S) remote download URL.
        dest_path: Final destination path.
        expected_sha256: Optional SHA-256 hexadecimal hash to verify.
        expected_size: Optional expected byte length.
        chunk_size: Streaming chunk size in bytes (default: 1 MiB).
        force: If True, re-download even if already present.
        show_progress: If True, display streaming progress.
        user_agent: Custom User-Agent header string.
        timeout: Socket timeout in seconds.
        
    Returns:
        Path: Resolved destination Path object.
    """
    import sys
    dest = Path(dest_path).resolve()

    # 1. Fast-Skip validation
    if not force and dest.is_file():
        if expected_sha256:
            if verify_file_sha256(dest, expected_sha256):
                return dest
        elif expected_size is not None and expected_size > 0:
            if dest.stat().st_size == expected_size:
                return dest
        elif dest.stat().st_size > 0:
            return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    part_path = dest.with_suffix(dest.suffix + ".part")

    # 2. Check disk space if size is known
    if expected_size:
        if not check_disk_space(dest.parent, expected_size):
            raise OSError(f"Insufficient disk space in {dest.parent} for {expected_size} bytes.")

    headers = {}
    if user_agent:
        headers["User-Agent"] = user_agent
    else:
        headers["User-Agent"] = "ameva-device-sdk/0.1.0 (Android; ARM64)"

    downloaded = 0
    mode = "wb"

    if part_path.exists() and not force:
        downloaded = part_path.stat().st_size
        if expected_size and downloaded >= expected_size:
            downloaded = 0
            part_path.unlink(missing_ok=True)
        else:
            headers["Range"] = f"bytes={downloaded}-"
            mode = "ab"

    # Try requests first for robust chunking / connection pooling
    use_requests = False
    try:
        import requests
        use_requests = True
    except ImportError:
        pass

    if use_requests:
        resp = requests.get(url, headers=headers, stream=True, timeout=timeout)
        if resp.status_code == 416:  # Range Not Satisfiable -> file already complete or server changed
            downloaded = 0
            mode = "wb"
            headers.pop("Range", None)
            resp = requests.get(url, headers=headers, stream=True, timeout=timeout)

        if resp.status_code not in (200, 206):
            part_path.unlink(missing_ok=True)
            raise RuntimeError(f"HTTP {resp.status_code} downloading {url}: {resp.text[:200]}")

        total_bytes = None
        cl = resp.headers.get("Content-Length")
        if cl and cl.isdigit():
            total_bytes = int(cl) + (downloaded if resp.status_code == 206 else 0)

        with open(part_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if show_progress and total_bytes:
                        pct = (downloaded / total_bytes) * 100
                        sys.stdout.write(f"\r[download] {pct:.1f}% ({downloaded // (1024*1024)}MB / {total_bytes // (1024*1024)}MB)")
                        sys.stdout.flush()
    else:
        import urllib.request
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                total_bytes = None
                cl = response.headers.get("Content-Length")
                if cl and cl.isdigit():
                    total_bytes = int(cl) + downloaded

                with open(part_path, mode) as f:
                    while True:
                        buf = response.read(chunk_size)
                        if not buf:
                            break
                        f.write(buf)
                        downloaded += len(buf)
                        if show_progress and total_bytes:
                            pct = (downloaded / total_bytes) * 100
                            sys.stdout.write(f"\r[download] {pct:.1f}% ({downloaded // (1024*1024)}MB / {total_bytes // (1024*1024)}MB)")
                            sys.stdout.flush()
        except Exception as e:
            part_path.unlink(missing_ok=True)
            raise RuntimeError(f"Network error downloading {url}: {e}") from e

    if show_progress:
        sys.stdout.write("\n")
        sys.stdout.flush()

    # 3. Post-download validations
    if expected_size is not None and expected_size > 0:
        actual_sz = part_path.stat().st_size
        if actual_sz != expected_size:
            part_path.unlink(missing_ok=True)
            raise ValueError(f"Size mismatch: expected {expected_size}, got {actual_sz}")

    if expected_sha256:
        if not verify_file_sha256(part_path, expected_sha256):
            part_path.unlink(missing_ok=True)
            raise ValueError(f"SHA-256 verification failed for downloaded artifact: {url}")

    # 4. Atomic Replace
    atomic_replace(part_path, dest)
    return dest

