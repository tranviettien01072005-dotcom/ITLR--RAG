"""Linux interprocess locks for local artifact and pipeline writers."""
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
import fcntl
import threading

_LOCAL = threading.RLock()


@contextmanager
def file_lock(path, *, shared=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCAL, path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def artifact_locked(fn):
    @wraps(fn)
    def wrapped(root=None, *args, **kwargs):
        from itlr import config
        root = Path(root or config.ARTIFACTS_DIR)
        with file_lock(root / '.activation.lock'):
            return fn(root, *args, **kwargs)
    return wrapped
