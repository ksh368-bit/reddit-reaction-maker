#!/usr/bin/env python3
"""
File locking utility for concurrent execution prevention.

Used in crontab environments where multiple instances may run simultaneously.
Prevents race conditions when writing to shared files (history.json, metrics, etc).
"""

import os
import time
import logging
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FileLock:
    """Simple file-based lock for cross-process synchronization."""

    def __init__(self, lock_file: str, timeout: int = 30):
        """
        Initialize file lock.

        Args:
            lock_file: Path to lock file
            timeout: Maximum wait time in seconds before giving up
        """
        self.lock_file = Path(lock_file)
        self.timeout = timeout
        self.acquired = False

    def acquire(self) -> bool:
        """
        Try to acquire lock. Returns True if successful, False if timeout.

        Uses atomic file creation (O_EXCL flag) to prevent race conditions.
        """
        start_time = time.time()

        while time.time() - start_time < self.timeout:
            try:
                # O_CREAT | O_EXCL ensures atomic creation (fails if file exists)
                fd = os.open(
                    str(self.lock_file),
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    mode=0o666,
                )
                os.close(fd)
                self.acquired = True
                logger.debug(f"Acquired lock: {self.lock_file}")
                return True
            except FileExistsError:
                # Lock already held by another process
                time.sleep(0.1)

        logger.warning(
            f"Failed to acquire lock {self.lock_file} within {self.timeout}s"
        )
        return False

    def release(self) -> None:
        """Release the lock."""
        if self.acquired:
            try:
                self.lock_file.unlink()
                logger.debug(f"Released lock: {self.lock_file}")
            except FileNotFoundError:
                pass
            finally:
                self.acquired = False

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire():
            raise TimeoutError(f"Failed to acquire lock: {self.lock_file}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()


@contextmanager
def file_lock(lock_file: str, timeout: int = 30):
    """
    Context manager for file locking.

    Usage:
        with file_lock("output/.history.lock"):
            # Critical section: safe to modify shared files
            scraper.save_to_history(post_id)
    """
    lock = FileLock(lock_file, timeout=timeout)
    if not lock.acquire():
        raise TimeoutError(f"Failed to acquire lock: {lock_file}")
    try:
        yield lock
    finally:
        lock.release()
