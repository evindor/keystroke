import hashlib
import json
from pathlib import Path
from flint.api import row, copy, navigate, command, score


async def query(ctx):
    if ctx.scope and ctx.scope != "flint.clipboard":
        return []
    if not ctx.scope:
        s = 26 if not ctx.query else score(ctx.query, "Clipboard History", "paste copied text images")
        return [row("clipboard", "Clipboard History", "Text & images, ready to use again", "󰅌", score=s, order=2,
                    action=navigate("flint.clipboard"))] if s else []
    # Reuse Omarchy's existing capture service; never start a second watcher.
    path = Path.home() / ".local/state/omarchy/clipboard-history.json"
    if not path.exists():
        return []
    stamp = path.stat().st_mtime_ns
    if ctx.cache.get("stamp") != stamp:
        ctx.cache.update(stamp=stamp, entries=json.loads(path.read_text()))
    results = []
    for i, entry in enumerate(ctx.cache["entries"][:ctx.settings["limit"]]):
        if isinstance(entry, str):
            entry = {"type": "text", "text": entry}
        if not isinstance(entry, dict):
            continue
        image = entry.get("type") == "image"
        text = entry.get("text", "")
        title = "Image · " + entry.get("capturedAt", "Clipboard") if image else text.replace("\n", " ")[:120]
        s = score(ctx.query, title, text[:4000])
        if not s:
            continue
        action = (command("omarchy-clipboard-paste-file", "--copy-only", entry.get("mime", "image/png"), entry["path"])
                  if image else copy(text))
        results.append(row(hashlib.sha256((entry.get("path", "") if image else text).encode()).hexdigest(), title,
                          "Image" if image else f"{len(text):,} characters", "󰅌", score=s, order=i,
                          action=action, verb="Copy", preview=text[:12000], previewImage=entry.get("path", "") if image else "",
                          previewLabel="CLIPBOARD", previewDetail="Copied locally · never included in global search"))
    return results
