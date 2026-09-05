"""Maintainer helper: regenerate the bundled extension manifests."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
specs = [
    ("applications", "Applications", "Launch installed desktop apps", "󰀻", "#91adf4", ["process"], []),
    ("omarchy", "Omarchy", "The complete, live Omarchy menu", "󰣇", "#d4a774", ["process"], [
        dict(key="confirmDestructive", type="boolean", label="Confirm destructive actions", default=True,
             description="Confirm shutdown, removal and configuration resets")]),
    ("calculator", "Calculator", "Private, instant arithmetic", "󰃬", "#b1a2e8", ["clipboard.write"], [
        dict(key="precision", type="number", label="Significant digits", default=12, min=2, max=15, integer=True)]),
    ("converter", "Converter", "Units and daylight-saving aware time zones", "󰯍", "#81c8b6", ["clipboard.write"], [
        dict(key="timezone", type="string", label="Your time zone", default="Europe/Tallinn", description="IANA name, for example Europe/Tallinn or America/New_York")]),
    ("clipboard", "Clipboard History", "Uses Omarchy's existing history", "󰅌", "#8dbaec", ["clipboard.read", "clipboard.write", "process"], [
        dict(key="limit", type="number", label="Maximum entries", default=100, min=1, max=300, integer=True)]),
    ("emoji", "Emoji Picker", "Search by name with the : prefix", "☺", "#e8c575", ["clipboard.write"], []),
    ("colors", "Colors", "Screen eyedropper, HEX, RGB and HSL", "󰃉", "#e69ba9", ["process", "clipboard.write"], [
        dict(key="format", type="enum", label="Eyedropper format", default="hex", options=["hex", "rgb"])]),
    ("ai", "AI & Web Search", "Continue any query with your preferred assistant", "✳", "#e79c85", ["process", "clipboard.write", "open-url"], [
        dict(key="provider", type="enum", label="Preferred AI provider", default="chatgpt", options=["chatgpt", "claude"]),
        dict(key="mode", type="enum", label="Open conversations in", default="desktop", options=["desktop", "cli", "browser"])]),
    ("settings", "Appearance", "Flint's layout, colors and previews", "󰒓", "#a5a4ad", ["process"], [
        dict(key="density", type="enum", label="Layout density", default="compact", options=["compact", "comfortable"],
             description="Compact uses a narrower window and shorter rows"),
        dict(key="accent", type="enum", label="Accent color", default="ember", options=["ember", "violet", "mint"]),
        dict(key="showPreview", type="boolean", label="Show result previews", default=True)])
]

if __name__ == "__main__":
    for id, name, description, icon, color, permissions, settings in specs:
        manifest = dict(apiVersion=1, id="flint." + id, name=name, version="0.1.0", description=description,
                        icon=icon, color=color, permissions=permissions, settings=settings)
        (ROOT / "extensions" / id / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
