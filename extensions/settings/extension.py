from flint.api import row, navigate, score


async def query(ctx):
    if not ctx.scope:
        s = 20 if not ctx.query else score(ctx.query, "Flint Settings", "preferences extensions configuration")
        return [row("settings", "Flint Settings", "Make it yours. Make it work for you.", "󰒓", score=s, order=7,
                    action=navigate("flint.settings"))] if s else []
    if not ctx.scope.startswith("flint.settings"):
        return []
    target = ctx.scope.partition("/")[2]
    if not target:
        rows = [row("config", "Open config file", str(ctx.config.path), "", score=80,
                    action={"type": "edit"}, verb="Open file")]
        for e in ctx.extensions:
            enabled = ctx.config.enabled(e.manifest)
            s = score(ctx.query, e.manifest["name"])
            if s:
                rows.append(row(e.id, e.manifest["name"], ("Enabled" if enabled else "Disabled") + " · " + e.manifest.get("description", ""),
                    e.manifest.get("icon", "⌘"), score=s, tint=e.manifest.get("color", "#aaa9b0"),
                    action=navigate("flint.settings/" + e.id)))
        return rows
    ext_id, _, key = target.partition("/")
    ext = next((e for e in ctx.extensions if e.id == ext_id), None)
    if not ext:
        return []
    settings = ctx.config.settings(ext.manifest)
    schemas = list(ext.manifest.get("settings", []))
    if ext_id != "flint.settings":
        schemas.insert(0, {"key": "enabled", "type": "boolean", "label": "Enable extension",
            "description": "Runs local code with your account permissions" if ext.manifest["external"] else "Include this extension in Flint"})
    rows = []
    for schema in schemas:
        k = schema["key"]
        value = ctx.config.enabled(ext.manifest) if k == "enabled" else settings.get(k)
        def setting(v):
            return {"type": "setting", "extension": ext_id, "key": k, "value": v}
        if key and k == key:
            if schema["type"] == "enum":
                for option in schema["options"]:
                    rows.append(row(str(option), str(option).capitalize(), "Selected" if option == value else "", "✓" if option == value else "○",
                                    score=score(ctx.query, str(option)), action=setting(option), verb="Select"))
            elif schema["type"] in {"string", "number"}:
                try:
                    new_value = int(ctx.query) if schema["type"] == "number" else ctx.query
                    ctx.config.validate(schema, new_value)
                    rows.append(row(k, "Save “" + str(new_value) + "”", schema.get("description", ""), "✓", score=100, action=setting(new_value), verb="Save"))
                except ValueError:
                    pass
        elif not key:
            action = setting(not value) if schema["type"] == "boolean" else navigate(ctx.scope + "/" + k)
            s = score(ctx.query, schema["label"])
            if s:
                rows.append(row(k, schema["label"], schema.get("description", ""), "󰒓", score=s,
                    accessory=("On" if value else "Off") if schema["type"] == "boolean" else str(value),
                    action=action, verb="Toggle" if schema["type"] == "boolean" else "Change"))
    return rows
