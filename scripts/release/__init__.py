"""Repository maintenance helpers."""
import sys
from pathlib import Path
for _directory in ("build", "verify", "release"):
    _path = str(Path(__file__).resolve().parents[1] / _directory)
    if _path not in sys.path:
        sys.path.insert(0, _path)
