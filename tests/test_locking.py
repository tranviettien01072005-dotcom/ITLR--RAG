"""The lock module must import and work on every supported dev host.

Windows lacks fcntl, so the module falls back to msvcrt; a broken import there
also broke 6 unrelated test modules at collection time.
"""

from itlr.locking import file_lock


def test_file_lock_creates_parent_and_reacquires(tmp_path):
    lock = tmp_path / "nested" / ".activation.lock"
    with file_lock(lock):
        assert lock.exists()

    with file_lock(lock, shared=True):
        pass
