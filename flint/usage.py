"""Local selection frecency. Only opaque stable IDs, weights and timestamps."""
import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path


class Usage:
    HALF_LIFE = 14 * 86400

    def __init__(self, path=None, clock=time.time):
        self.path = Path(path or os.environ.get("FLINT_USAGE", Path(os.environ.get(
            "XDG_STATE_HOME", Path.home() / ".local/state")) / "flint/usage.json"))
        self.clock = clock
        self.entries = {}
        try:
            data = json.loads(self.path.read_text())
            if data.get("version") == 1:
                for key, entry in data.get("entries", {}).items():
                    weight, updated = entry["weight"], entry["updated"]
                    if (isinstance(key, str) and len(key) == 64 and type(weight) in (int, float)
                            and type(updated) in (int, float) and math.isfinite(weight)
                            and math.isfinite(updated) and 0 <= weight <= 1e6):
                        self.entries[key] = {"weight": weight, "updated": updated}
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            self.entries = {}

    @staticmethod
    def key(extension, id):
        return hashlib.sha256((extension + "/" + str(id)).encode()).hexdigest()

    def weight(self, key):
        entry = self.entries.get(key)
        if not entry:
            return 0
        return entry["weight"] * 2 ** (-max(0, self.clock() - entry["updated"]) / self.HALF_LIFE)

    def bonus(self, key):
        return min(36, 12 * math.log2(1 + self.weight(key))) if key else 0

    def record(self, key):
        self.entries[key] = {"weight": min(1e6, self.weight(key) + 1), "updated": self.clock()}
        if len(self.entries) > 2000:
            self.entries = dict(sorted(self.entries.items(), key=lambda x: self.weight(x[0]), reverse=True)[:2000])
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".usage-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"version": 1, "entries": self.entries}, f)
                f.write("\n")
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
