import json
from flint.api import row, copy, navigate, score


async def query(ctx):
    if ctx.scope and ctx.scope != "flint.emoji":
        return []
    if not ctx.query and not ctx.scope:
        return [row("emoji", "Emoji Picker", "Find the right feeling", "☺", score=22, order=5, action=navigate("flint.emoji"))]
    q = ctx.query.lstrip(":").strip()
    if not ctx.scope and not ctx.query.startswith(":"):
        s = score(q, "Emoji Picker", "smile emoticon")
        return [row("emoji", "Emoji Picker", "Type : followed by a feeling", "☺", score=s, action=navigate("flint.emoji"))] if s else []
    if "data" not in ctx.cache:
        ctx.cache["data"] = json.loads((ctx.omarchy / "shell/plugins/emojis/emojis.json").read_text())
    results = []
    for i, e in enumerate(ctx.cache["data"]):
        s = score(q, e["k"])
        if s:
            results.append(row(str(i), e["k"].split(" ")[:6] and " ".join(e["k"].split()[:6]).capitalize(), e["e"], e["e"],
                score=s, action=copy(e["e"]), verb="Copy emoji", emoji=True, preview=e["e"], previewLabel="EMOJI"))
    return sorted(results, key=lambda r: -r["score"])[:80]
