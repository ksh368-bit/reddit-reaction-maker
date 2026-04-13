#!/usr/bin/env python3
"""
Tests for file locking utility (crontab concurrent execution safety).
"""

import os
import sys
import tempfile
import time
import threading
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.file_lock import FileLock, file_lock


def test_file_lock_acquire_release():
    """Test basic acquire and release."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "test.lock")

        lock = FileLock(lock_file)
        assert not lock.acquired
        assert not Path(lock_file).exists()

        # Acquire
        result = lock.acquire()
        assert result is True
        assert lock.acquired
        assert Path(lock_file).exists()

        # Release
        lock.release()
        assert not lock.acquired
        assert not Path(lock_file).exists()


def test_file_lock_context_manager():
    """Test context manager usage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "test.lock")

        with file_lock(lock_file, timeout=5):
            assert Path(lock_file).exists()

        # Released after context
        assert not Path(lock_file).exists()


def test_file_lock_prevents_concurrent_acquisition():
    """Test that lock prevents concurrent access."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "test.lock")
        results = []

        def try_acquire(lock_id):
            """Try to acquire lock and record success/failure."""
            lock = FileLock(lock_file, timeout=0.5)
            acquired = lock.acquire()
            results.append({"id": lock_id, "acquired": acquired})

            if acquired:
                time.sleep(0.2)  # Hold lock briefly
                lock.release()

        # First thread acquires lock and holds it
        lock1 = FileLock(lock_file, timeout=5)
        assert lock1.acquire()

        # Second thread tries to acquire immediately (should fail with short timeout)
        t2 = threading.Thread(target=try_acquire, args=(2,))
        t2.start()

        # Keep lock held while thread tries
        time.sleep(1.0)

        lock1.release()

        # Wait for thread
        t2.join()

        # Thread should have failed (lock was held initially)
        assert results[0]["acquired"] is False


def test_file_lock_timeout():
    """Test timeout when lock can't be acquired."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "test.lock")

        # Hold lock
        lock1 = FileLock(lock_file, timeout=10)
        assert lock1.acquire()

        # Try to acquire with short timeout
        lock2 = FileLock(lock_file, timeout=1)
        start = time.time()
        result = lock2.acquire()
        elapsed = time.time() - start

        assert result is False
        assert elapsed >= 0.9  # Should wait at least close to timeout

        lock1.release()


def test_file_lock_context_manager_timeout():
    """Test context manager with timeout error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "test.lock")

        # Hold lock
        lock1 = FileLock(lock_file, timeout=10)
        assert lock1.acquire()

        # Try context manager with short timeout
        try:
            with file_lock(lock_file, timeout=1):
                assert False, "Should not reach here"
        except TimeoutError as e:
            assert "Failed to acquire lock" in str(e)

        lock1.release()


def test_file_lock_double_release():
    """Test releasing already-released lock."""
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_file = os.path.join(tmpdir, "test.lock")

        lock = FileLock(lock_file)
        lock.acquire()
        lock.release()

        # Second release should be safe (no-op)
        lock.release()
        assert not lock.acquired


def test_resolve_paths_in_main():
    """Test that main.py resolves paths correctly."""
    import main

    # Create test config
    config = {
        "output": {"dir": "output", "history_file": "output/history.json"},
        "video": {
            "font": "assets/fonts/Montserrat-Bold.ttf",
            "background_dir": "assets/backgrounds",
        },
        "youtube": {
            "credentials_path": "credentials.json",
            "token_path": "token.json",
        },
        "logging": {"log_dir": "output/logs"},
    }

    # Resolve paths
    resolved = main.resolve_paths(config)

    # All paths should now be absolute
    assert Path(resolved["output"]["dir"]).is_absolute()
    assert Path(resolved["output"]["history_file"]).is_absolute()
    assert Path(resolved["video"]["font"]).is_absolute()
    assert Path(resolved["video"]["background_dir"]).is_absolute()
    assert Path(resolved["youtube"]["credentials_path"]).is_absolute()
    assert Path(resolved["youtube"]["token_path"]).is_absolute()
    assert Path(resolved["logging"]["log_dir"]).is_absolute()

    # Absolute paths should remain unchanged
    abs_path = "/tmp/test/output"
    config2 = {"output": {"dir": abs_path}}
    resolved2 = main.resolve_paths(config2)
    assert resolved2["output"]["dir"] == abs_path


if __name__ == "__main__":
    # Run tests
    test_file_lock_acquire_release()
    test_file_lock_context_manager()
    test_file_lock_prevents_concurrent_acquisition()
    test_file_lock_timeout()
    test_file_lock_context_manager_timeout()
    test_file_lock_double_release()
    test_resolve_paths_in_main()
    print("✓ All file lock tests passed!")
