"""
Atomic JSON writes for the node databases.

Every database in this pack is rewritten in full on each save. Truncating the
file in place means a reader - a queued PromptStack execution, another browser
tab, an external tool - can observe a half-written file and parse nothing. So
writes go to a temp file in the same directory and are moved into place with
os.replace(), which is atomic on every platform ComfyUI runs on.
"""
import json
import os
import tempfile


def write_json_atomic(path, data):
    """Serialise `data` to `path` as JSON, replacing the file atomically."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=directory or None,
        prefix=os.path.basename(path) + ".",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
