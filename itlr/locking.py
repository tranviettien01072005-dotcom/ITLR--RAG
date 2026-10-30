"""Interprocess locks for local artifact and pipeline writers.

Production targets a local Linux filesystem (flock). Windows dev hosts fall back
to an exclusive msvcrt lock so the module stays importable and tests runnable.
"""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import threading

try:
    import fcntl
except ImportError:  # Windows dev host; deployment still requires Linux flock
    fcntl = None
    import msvcrt

_LOCAL = threading.RLock()


@contextmanager
def file_lock(path, *, shared=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCAL, path.open('a') as handle:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        else:
            # shortcut: Windows has no shared lock; exclusive only, locks byte 0
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
            else:
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def artifact_locked(fn):
    @wraps(fn)
    def wrapped(root=None, *args, **kwargs):
        from itlr import config
        root = Path(root or config.ARTIFACTS_DIR)
        with file_lock(root / '.activation.lock'):
            return fn(root, *args, **kwargs)
    return wrapped
