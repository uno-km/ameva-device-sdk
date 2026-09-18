"""
Unit tests for ameva-device-sdk Python interface.
"""
import hashlib
import sys
import tempfile
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import ameva_device as dev


def test_env_equivalence():
    assert dev.is_android() == dev.is_termux()
    assert isinstance(dev.is_proot(), bool)


def test_memory_info():
    total, avail = dev.get_memory_info()
    if total is not None:
        assert total > 0
        assert avail is not None
        assert avail >= 0


def test_cpu_features():
    features = dev.read_cpu_features()
    assert "neon" in features
    assert "fp16" in features
    assert "dotprod" in features
    for val in features.values():
        assert isinstance(val, bool)


def test_optimal_threads():
    assert dev.get_optimal_threads(cores=8) == 4
    assert dev.get_optimal_threads(cores=6) == 4
    assert dev.get_optimal_threads(cores=4) == 3
    assert dev.get_optimal_threads(cores=2) == 2
    assert dev.get_optimal_threads(cores=1) == 1


def test_unified_model_search_dirs():
    dirs = dev.get_unified_model_search_dirs("vision")
    assert len(dirs) > 0
    # Ensure deduplicated
    dir_strs = [str(d) for d in dirs]
    assert len(dir_strs) == len(set(dir_strs))


def test_sha256_and_atomic_replace():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.bin"
        payload = b"AMEVA Unified Device Test Payload 2026"
        expected_hash = hashlib.sha256(payload).hexdigest()

        # Write temp file
        temp_src = tmp_path / "temp_src.bin"
        temp_src.write_bytes(payload)

        # Atomic replace
        dev.atomic_replace(temp_src, test_file)
        assert test_file.exists()
        assert not temp_src.exists()

        # Verify hash
        assert dev.verify_file_sha256(test_file, expected_hash)
        assert not dev.verify_file_sha256(test_file, "0" * 64)
        assert not dev.verify_file_sha256(tmp_path / "nonexistent.bin", expected_hash)


def test_check_disk_space():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Require 1 KB
        assert dev.check_disk_space(tmpdir, 1024)
        # Require 10,000 TB (should fail on standard disk)
        assert not dev.check_disk_space(tmpdir, 10**16)


def test_download_file_atomic():
    import http.server
    import threading

    payload = b"Atomic Downloader Unit Test Payload 12345"
    sha = hashlib.sha256(payload).hexdigest()

    class TestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), TestHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "sub" / "output.bin"
            url = f"http://127.0.0.1:{port}/model.bin"
            res = dev.download_file_atomic(
                url,
                dest,
                expected_sha256=sha,
                expected_size=len(payload),
                show_progress=False,
            )
            assert res == dest
            assert dest.is_file()
            assert dest.read_bytes() == payload

            # Fast-skip test
            res2 = dev.download_file_atomic(
                url,
                dest,
                expected_sha256=sha,
                show_progress=False,
            )
            assert res2 == dest
    finally:
        server.shutdown()


if __name__ == "__main__":
    print("Running ameva-device-sdk test suite...")
    test_env_equivalence()
    test_memory_info()
    test_cpu_features()
    test_optimal_threads()
    test_unified_model_search_dirs()
    test_sha256_and_atomic_replace()
    test_check_disk_space()
    test_download_file_atomic()
    print("All Python tests PASSED successfully.")
