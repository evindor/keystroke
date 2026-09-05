from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


class Config:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("FLINT_CONFIG", Path(os.environ.get(
            "XDG_CONFIG_HOME", Path.home() / ".config")) / "flint/config.json"))
        self.data = {"version": 1, "extensions": {}}
        self.error = ""
        self.reload()

    def reload(self):
        self.error = ""
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("extensions", {}), dict):
                raise ValueError("Expected version: 1 and an extensions object")
            self.data = data
        except FileNotFoundError:
            pass
        except (ValueError, OSError) as e:
            self.error = f"Config kept at last valid version: {e}"

    def settings(self, manifest):
        values = {s["key"]: s.get("default") for s in manifest.get("settings", [])}
        saved = self.data.get("extensions", {}).get(manifest["id"], {})
        if isinstance(saved, dict):
            for s in manifest.get("settings", []):
                if s["key"] in saved:
                    try:
                        self.validate(s, saved[s["key"]])
                        values[s["key"]] = saved[s["key"]]
                    except ValueError:
                        pass
        return values

    def enabled(self, manifest):
        saved = self.data.get("extensions", {}).get(manifest["id"], {})
        return isinstance(saved, dict) and saved.get("enabled", not manifest.get("external", False)) is True

    @staticmethod
    def validate(schema, value):
        kind = schema["type"]
        valid = ((kind == "boolean" and type(value) is bool)
                 or (kind == "string" and isinstance(value, str) and len(value) <= 4096)
                 or (kind == "number" and type(value) in (int, float)
                     and schema.get("min", -1e9) <= value <= schema.get("max", 1e9)
                     and (not schema.get("integer", False) or type(value) is int))
                 or (kind == "enum" and value in schema["options"]))
        if not valid:
            raise ValueError(f"Invalid value for {schema['key']}")

    def set(self, manifest, key, value):
        self.reload()
        if self.error:
            raise ValueError(self.error)
        schema = ({"key": "enabled", "type": "boolean"} if key == "enabled" else
                  next(s for s in manifest.get("settings", []) if s["key"] == key))
        self.validate(schema, value)
        self.data.setdefault("extensions", {}).setdefault(manifest["id"], {})[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".config-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
