"""Live adapter for Omarchy 4's JSONC command tree, not a copied menu snapshot."""
import os
import re
import shlex
import time
from pathlib import Path
from flint.api import row, navigate, command, read_jsonc, run, score

DEFAULTS = dict(icon="", iconFont="", label="", title="", target="", description="", action="", provider="", aliases=[], when="", checked="")


def load_menu(paths):
    items = {}
    for path in paths:
        if not path.exists():
            continue
        parsed = read_jsonc(path)
        source = parsed.get("items", parsed)
        for id, raw in source.items():
            if not isinstance(raw, dict):
                continue
            value = {**DEFAULTS, **raw, "id": id}
            value["label"] = raw.get("label", id)
            value["parent"] = raw.get("parent", id.rpartition(".")[0] or "root")
            aliases = value["aliases"]
            value["aliases"] = [aliases] if isinstance(aliases, str) else aliases
            items[id] = value
    return items


def ancestors(items, id):
    seen, result = set(), []
    while id in items and id not in seen:
        seen.add(id)
        result.append(items[id])
        id = items[id]["parent"]
    return result


def resolve(items, route):
    seen = set()
    if route not in items:
        route = next((id for id, e in items.items() if route in e["aliases"]), route)
    while route in items and items[route]["target"] and route not in seen:
        seen.add(route)
        route = items[route]["target"]
    return route


async def guards(entries, cache):
    expressions = list(dict.fromkeys(e[k] for e in entries for k in ("when", "checked") if e.get(k)))
    now = time.monotonic()
    missing = [s for s in expressions if now - cache.get(s, (0, False))[0] > 30]
    if missing:
        lines = []
        for i, expression in enumerate(missing):
            lines.append(f"if ( {expression}\n) >/dev/null 2>&1; then printf '{i}:1\\n'; else printf '{i}:0\\n'; fi")
        result = await run(["bash", "-c", "\n".join(lines)], timeout=8)
        for line in result.splitlines():
            index, value = line.split(":")
            cache[missing[int(index)]] = (now, value == "1")
    return {s: cache[s][1] for s in expressions}


async def provider(ctx, entry):
    name = entry["provider"]
    if name == "apps":
        return []
    stamp, cached = ctx.cache.get("provider:" + name, (0, []))
    if time.monotonic() - stamp < 30:
        return cached
    rows = []
    if name in {"fonts", "power-profiles"}:
        fonts = name == "fonts"
        values = await run(["omarchy-font-list" if fonts else "omarchy-powerprofiles-list"])
        try:
            current = (await run(["omarchy-font-current"] if fonts else ["powerprofilesctl", "get"])).strip()
        except RuntimeError:
            current = ""
        for i, value in enumerate(values.splitlines()):
            if value.strip():
                rows.append({**DEFAULTS, "id": entry["id"] + f".value-{i}", "parent": entry["id"],
                    "label": value, "icon": "✓" if value == current else entry["icon"],
                    "action": ("omarchy-font-set " if fonts else "omarchy-powerprofiles-set autodetect ") + shlex.quote(value)})
    else:
        # Omarchy documents custom provider commands returning JSON rows.
        raw = await run(shlex.split(name))
        parsed = __import__("json").loads(raw)
        for i, r in enumerate(parsed):
            rows.append({**DEFAULTS, **r, "id": r.get("id", entry["id"] + f".value-{i}"), "parent": entry["id"]})
    ctx.cache["provider:" + name] = (time.monotonic(), rows)
    return rows


async def query(ctx):
    if ctx.scope and not ctx.scope.startswith("flint.omarchy"):
        return []
    paths = [ctx.omarchy / "default/omarchy/omarchy-menu.jsonc",
             Path.home() / ".config/omarchy/extensions/omarchy-menu.jsonc"]
    stamps = tuple(p.stat().st_mtime_ns if p.exists() else 0 for p in paths)
    if ctx.cache.get("stamps") != stamps:
        ctx.cache.update(items=load_menu(paths), stamps=stamps, guards={})
    items = dict(ctx.cache["items"])
    if not items:
        raise RuntimeError("Omarchy 4 menu definition was not found")
    if not ctx.query and not ctx.scope:
        return [row("menu", "Omarchy Menu", "Your entire desktop, at your fingertips", "󰣇", score=28, order=1,
                    action=navigate("flint.omarchy/root"))]
    route = resolve(items, ctx.scope.partition("/")[2] or "root")
    # Dynamic providers are indexed only when relevant, then kept warm.
    for entry in list(items.values()):
        if entry["provider"] and entry["provider"] != "apps" and (entry["id"] == route or ctx.query and
                (score(ctx.query, entry["label"], entry["provider"]) or entry["provider"] in {"fonts", "power-profiles"})):
            for value in await provider(ctx, entry):
                items[value["id"]] = value
    candidates = []
    for id, entry in items.items():
        if id == "root":
            continue
        chain = ancestors(items, id)
        if route != "root" and not any(e["id"] == route for e in chain):
            continue
        if not ctx.query and entry["parent"] != route and not (entry["id"] == route and entry["action"]):
            continue
        path = " › ".join(e["label"] for e in reversed(chain))
        s = score(ctx.query, entry["label"], path + " " + " ".join(entry["aliases"]))
        if s:
            candidates.append((entry, chain, path, s))
    # Hidden parents hide all descendants; run both when and checked expressions.
    expressions = [e for _, chain, _, _ in candidates for e in chain]
    checks = await guards(expressions, ctx.cache["guards"])
    results = []
    for entry, chain, path, s in candidates:
        if any(e["when"] and not checks.get(e["when"], False) for e in chain):
            continue
        if entry["action"]:
            action = {"type": "shell", "script": entry["action"]}
            if ctx.settings["confirmDestructive"] and (entry["id"] in {"system.shutdown", "system.reboot", "system.logout", "system.hibernate"}
                    or entry["id"].startswith(("remove.", "update.config."))):
                action["confirm"] = "Run “" + entry["label"] + "”?"
        else:
            target = resolve(items, entry["target"] or entry["id"])
            action = navigate("flint.applications" if entry["provider"] == "apps" else "flint.omarchy/" + target)
        results.append(row(entry["id"], entry["label"], path if ctx.query else entry["description"], entry["icon"] or "󰣇",
            score=s + (3 if entry["action"] else 0), order=list(items).index(entry["id"]), action=action, remember=True,
            iconFont=entry["iconFont"], accessory="✓" if entry["checked"] and checks.get(entry["checked"]) else "",
            previewDetail=path))
    return results
