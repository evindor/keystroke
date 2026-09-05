"""Event-driven JSON-lines host. Extensions own all search capabilities."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

from flint.api import run, score
from flint.config import Config
from flint.usage import Usage

ROOT = Path(__file__).resolve().parent.parent


class Host:
    def __init__(self, config=None, extra_dir=None, usage_path=None):
        self.config = config or Config()
        self.extensions, self.errors, self.cache = [], [], {}
        self.apps = []
        self.actions = {}
        self.generation = 0
        self.usage = Usage(usage_path)
        user_dir = Path(extra_dir or self.config.path.parent / "extensions")
        for base, external in ((ROOT / "extensions", False), (user_dir, True)):
            for path in sorted(base.glob("*/manifest.json")):
                try:
                    m = json.loads(path.read_text())
                    if m.get("apiVersion") != 1 or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)+", m["id"]):
                        raise ValueError("Expected apiVersion 1 and a namespaced id")
                    if any(x.id == m["id"] for x in self.extensions):
                        raise ValueError("Duplicate extension id")
                    m["external"] = external
                    if external:
                        if not isinstance(m.get("command"), list) or not m["command"] or not all(isinstance(a, str) for a in m["command"]):
                            raise ValueError("External extensions need a command argv array")
                        module = None
                    else:
                        spec = importlib.util.spec_from_file_location(m["id"], path.parent / "extension.py")
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                    self.extensions.append(SimpleNamespace(id=m["id"], manifest=m, module=module, path=path.parent))
                except Exception as e:
                    self.errors.append(f"{path.parent.name}: {e}")

    def context(self, extension, query, scope):
        return SimpleNamespace(query=query, scope=scope, settings=self.config.settings(extension.manifest),
                               config=self.config, extensions=self.extensions, apps=self.apps,
                               cache=self.cache.setdefault(extension.id, {}),
                               omarchy=Path(os.environ.get("OMARCHY_PATH", "/usr/share/omarchy")))

    async def query(self, query, scope="", emit=None):
        self.generation += 1
        generation = self.generation
        self.actions = {}
        self.config.reload()
        errors = list(self.errors)
        if self.config.error:
            errors.append(self.config.error)
        rows = []
        started = time.perf_counter()

        def snapshot(pending):
            def rank(r):
                base = r.get("score", 1)
                # Learning breaks relevant ties; it never outranks computed answers.
                bonus = self.usage.bonus(r.get("usageKey"))
                value = min(179, base + bonus) if base < 180 else base
                return (-value, r.get("order", 50), r["title"].casefold())
            ranked = sorted(rows, key=rank)
            # Query results never include executable actions: activation uses a
            # generation-bound opaque token registered by this host.
            settings_ext = next((e for e in self.extensions if e.id == "flint.settings"), None)
            return dict(rows=ranked[:120], pending=pending, errors=errors[:5],
                        appearance=self.config.settings(settings_ext.manifest) if settings_ext else {},
                        elapsedMs=round((time.perf_counter() - started) * 1000, 2), scope=scope)

        async def one(ext):
            if not self.config.enabled(ext.manifest):
                return
            prefix = ext.manifest.get("prefix")
            if ext.manifest["external"] and (scope and scope != ext.id or prefix and not query.startswith(prefix)):
                return
            if ext.manifest["external"] and not scope and len(query) < ext.manifest.get("minQueryLength", 2):
                return
            try:
                ctx = self.context(ext, query, scope)
                if ext.module:
                    result = await ext.module.query(ctx)
                else:
                    argv = [str(ext.path / a) if a.startswith("./") else a for a in ext.manifest["command"]]
                    raw = await run(argv, input=json.dumps({"type": "query", "query": query,
                        "scope": scope, "settings": ctx.settings, "apiVersion": 1}),
                        timeout=min(3, ext.manifest.get("timeoutMs", 800) / 1000))
                    result = json.loads(raw).get("rows", [])
                if not isinstance(result, list):
                    raise ValueError("rows must be an array")
                for r in result[:400]:
                    if not isinstance(r, dict) or not isinstance(r.get("title"), str):
                        continue
                    action = r.pop("action", {})
                    token = f"{generation}:{ext.id}:{len(self.actions)}"
                    self.validate_action(action, ext.manifest)
                    usage_key = self.usage.key(ext.id, r.get("id", "")) if r.get("remember") else ""
                    self.actions[token] = (action, ext, usage_key)
                    r["usageKey"] = usage_key
                    r.update(token=token, extension=ext.manifest["name"], extensionId=ext.id)
                    r.setdefault("section", ext.manifest["name"])
                    r.setdefault("score", score(query, r["title"], r.get("keywords", "")))
                    r.setdefault("subtitle", "")
                    r.setdefault("icon", "⌘")
                    r.setdefault("verb", "Open" if action.get("type") == "navigate" else "Run")
                    r.setdefault("preview", "")
                    r.setdefault("iconName", "")
                    r.setdefault("tint", ext.manifest.get("color", "#aaa9b0"))
                    if r["score"] > 0:
                        rows.append(r)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                errors.append(f"{ext.manifest['name']}: {e}")

        tasks = [asyncio.create_task(one(e)) for e in self.extensions]
        try:
            # Coalesce fast providers into one response. A slow provider can
            # still complete later without withholding the fast results.
            done, pending = await asyncio.wait(tasks, timeout=.016)
            for task in done:
                await task
            if emit and pending:
                emit(snapshot(True))
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    await task
                if emit and pending:
                    emit(snapshot(True))
            return snapshot(False)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def validate_action(action, manifest):
        kind = action.get("type")
        if kind not in {"exec", "shell", "copy", "url", "navigate", "setting", "edit", "compound", "noop"}:
            raise ValueError("Unsupported action type")
        if kind == "exec" and (not isinstance(action.get("argv"), list) or not action["argv"] or
                               not all(isinstance(a, str) and "\0" not in a for a in action["argv"])):
            raise ValueError("exec requires a nonempty argv array")
        permissions = manifest.get("permissions", [])
        permission = {"exec": "process", "shell": "process", "copy": "clipboard.write", "url": "open-url", "edit": "process"}.get(kind)
        if permission and permission not in permissions:
            raise ValueError(f"Missing declared permission: {permission}")
        if kind == "compound":
            for item in action.get("actions", []):
                Host.validate_action(item, manifest)
        if kind == "url" and not re.match(r"^https?://", action.get("url", "")):
            raise ValueError("URL action must use HTTP(S)")
        if kind in {"setting", "edit"} and manifest.get("external"):
            raise ValueError("Settings mutations are reserved for the settings extension")

    async def activate(self, token, confirmed=False):
        if token not in self.actions:
            raise ValueError("Result expired; search again")
        action, ext, usage_key = self.actions[token]
        if action.get("confirm") and not confirmed:
            return {"confirm": action["confirm"], "token": token}
        result = await self.effect(action)
        if usage_key and action["type"] in {"exec", "shell", "navigate"}:
            try:
                self.usage.record(usage_key)
            except OSError:
                pass  # A read-only state directory must never prevent a launch.
        return result

    async def effect(self, action):
        kind = action["type"]
        if kind == "noop":
            return {}
        if kind == "navigate":
            return {"scope": action["scope"], "title": action.get("title", "")}
        if kind == "setting":
            ext = next(e for e in self.extensions if e.id == action["extension"])
            self.config.set(ext.manifest, action["key"], action["value"])
            return {"refresh": True, "message": "Setting saved"}
        if kind == "edit":
            if not self.config.path.exists():
                ext = next(e for e in self.extensions if e.id == "flint.settings")
                self.config.set(ext.manifest, "enabled", True)
            return {"launch": [["xdg-open", str(self.config.path)]], "close": True}
        if kind == "copy":
            await run(["wl-copy", "--", str(action["text"])], timeout=2)
            return {"message": "Copied to clipboard", "close": True}
        if kind == "compound":
            launches = []
            message = ""
            for a in action["actions"]:
                result = await self.effect(a)
                launches.extend(result.get("launch", []))
                message = result.get("message", message)
            return {"launch": launches, "close": True, "message": message}
        argv = (action["argv"] if kind == "exec" else ["bash", "-c", action["script"]]
                if kind == "shell" else ["xdg-open", action["url"]])
        # The UI closes its keyboard-grabbing layer before dispatching these.
        return {"launch": [argv], "close": True}


async def serve():
    host = Host()
    reader = asyncio.StreamReader(limit=2_097_152)
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    def send(data):
        print(json.dumps(data, ensure_ascii=False), flush=True)
    send({"type": "ready", "extensions": len(host.extensions), "errors": host.errors})
    pending = None
    async def query(msg):
        def emit(result):
            send({"type": "results", "id": msg["id"], **result})
        try:
            emit(await host.query(str(msg.get("query", ""))[:2048], str(msg.get("scope", "")), emit))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            send({"type": "error", "message": str(e)})
    try:
        while line := await reader.readline():
            try:
                msg = json.loads(line)
                if msg["type"] == "apps":
                    host.apps = msg.get("apps", [])
                elif msg["type"] in {"query", "cancel"}:
                    if pending:
                        pending.cancel()
                        await pending
                    if msg["type"] == "query":
                        pending = asyncio.create_task(query(msg))
                elif msg["type"] == "activate":
                    result = await host.activate(msg["token"], msg.get("confirmed", False))
                    send({"type": "action", **result})
            except Exception as e:
                send({"type": "error", "message": str(e)})
    finally:
        if pending:
            pending.cancel()
            await pending


if __name__ == "__main__":
    asyncio.run(serve())
