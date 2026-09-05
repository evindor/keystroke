import colorsys
import re
from flint.api import row, copy, command, score


async def query(ctx):
    if ctx.scope:
        return []
    results = []
    s = 21 if not ctx.query else score(ctx.query, "Pick a Color", "color picker eyedropper screen hex")
    if s:
        results.append(row("picker", "Pick a Color", "Sample any pixel on your screen", "󰃉", score=s, order=6,
                           action=command("hyprpicker", "-a", "-f", ctx.settings["format"]), verb="Pick color"))
    m = re.fullmatch(r"#?([a-fA-F0-9]{6}|[a-fA-F0-9]{3})", ctx.query.strip())
    if m and (ctx.query.startswith("#") or re.search("[a-f]", ctx.query, re.I)):
        hex = m[1] if len(m[1]) == 6 else "".join(c*2 for c in m[1])
        rgb = tuple(int(hex[i:i+2], 16) for i in (0, 2, 4))
        h, l, s = colorsys.rgb_to_hls(*(c/255 for c in rgb))
        values = ["#" + hex.upper(), f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})", f"hsl({h*360:.0f}, {s*100:.0f}%, {l*100:.0f}%)"]
        for i, value in enumerate(values):
            results.append(row(str(i), value, ["HEX", "RGB", "HSL"][i], "●", score=190-i, tint="#" + hex,
                action=copy(value), verb="Copy color", preview=value, previewLabel="COLOR", swatch="#" + hex))
    return results
