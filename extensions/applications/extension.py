from flint.api import row, navigate, command, score


async def query(ctx):
    if ctx.scope and ctx.scope != "flint.applications":
        return []
    results = []
    if not ctx.query and not ctx.scope:
        results.append(row("apps", "Applications", "Every app, one shortcut away", "󰀻",
                           action=navigate("flint.applications"), order=0, score=30))
    for app in ctx.apps:
        s = score(ctx.query, app["name"], app.get("keywords", "") + " " + app.get("comment", ""))
        if s and (ctx.query or ctx.scope):
            results.append(row(app["id"], app["name"], app.get("comment", "Application"), "󰀻",
                iconName=app.get("icon", ""), score=s + (45 if s >= 78 else 8), verb="Launch", remember=True,
                action=command("uwsm-app", "--", "gtk-launch", app["id"] + ("" if app["id"].endswith(".desktop") else ".desktop"))))
    return results
