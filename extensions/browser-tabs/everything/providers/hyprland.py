from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from ..commands import CommandError
from ..model import Thing, process_birth, stable_id
from .base import ProviderResult, ScanContext, normalized_address


ADDRESS = re.compile(r"^0x[0-9a-f]+$")


def lua_string(value: str) -> str:
    # JSON string syntax is valid for the string subset consumed by Hyprland's
    # Lua expression dispatcher and avoids hand-built quote escaping.
    return json.dumps(str(value), ensure_ascii=False)


async def focus_address(context: ScanContext, address: str) -> None:
    target = normalized_address(address)
    if not ADDRESS.fullmatch(target):
        raise CommandError("refusing an invalid Hyprland address")
    expression = f"hl.dsp.focus({{ window = {lua_string('address:' + target)} }})"
    result = await context.runner.run(["hyprctl", "dispatch", expression], timeout=1.0)
    if result.returncode != 0 or result.stdout.strip() not in ("", "ok"):
        raise CommandError(result.stderr.strip() or result.stdout.strip() or "Hyprland focus failed")


async def _live_clients(context: ScanContext) -> list[dict[str, Any]]:
    result = await context.runner.run(["hyprctl", "-j", "clients"], timeout=0.8)
    if result.returncode != 0:
        raise CommandError(result.stderr.strip() or "hyprctl clients failed")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise CommandError("hyprctl returned invalid client JSON") from error
    if not isinstance(value, list):
        raise CommandError("hyprctl client response was not a list")
    return [client for client in value if isinstance(client, dict)]


async def launch_terminal_and_focus(context: ScanContext, argv: list[object]) -> str:
    """Launch a fresh terminal and focus its newly managed exact address."""

    try:
        before_clients = await _live_clients(context)
    except CommandError:
        before_clients = context.hypr_clients
    before = {normalized_address(client.get("address")) for client in before_clients}
    await context.runner.spawn_detached(argv)

    terminal_class = re.compile(r"(?:kitty|ghostty|foot|alacritty)", re.IGNORECASE)
    for _attempt in range(64):
        try:
            clients = await _live_clients(context)
        except CommandError:
            await asyncio.sleep(0.06)
            continue
        candidates = [
            client
            for client in clients
            if client.get("mapped") is not False
            and normalized_address(client.get("address")) not in before
            and terminal_class.search(
                str(client.get("class") or client.get("initialClass") or "")
            )
        ]
        if len(candidates) == 1:
            address = normalized_address(candidates[0].get("address"))
            await focus_address(context, address)
            return address
        await asyncio.sleep(0.06)
    raise CommandError("fresh terminal client could not be identified")


class HyprlandProvider:
    name = "hyprland"

    async def scan(self, context: ScanContext) -> ProviderResult:
        result = await context.runner.run(["hyprctl", "-j", "clients"], timeout=1.0)
        if result.returncode != 0:
            raise CommandError(result.stderr.strip() or "hyprctl clients failed")
        try:
            clients = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise CommandError("hyprctl returned invalid client JSON") from error
        if not isinstance(clients, list):
            raise CommandError("hyprctl client response was not a list")

        # Child providers route only through mapped clients. Preserve every
        # current record separately as matching-only evidence so a lingering
        # AT-SPI top can still bind to its unmapped, non-routable former parent
        # instead of being reassigned to another live same-PID window.
        context.hypr_matching_clients = [
            client for client in clients if isinstance(client, dict)
        ]
        context.hypr_clients = [
            client
            for client in context.hypr_matching_clients
            if client.get("mapped") is not False
        ]
        items: list[Thing] = []
        metadata_clients: list[dict[str, Any]] = []
        for client in context.hypr_clients:
            address = normalized_address(client.get("address"))
            if not ADDRESS.fullmatch(address):
                continue
            pid = int(client.get("pid") or 0)
            birth = process_birth(pid)
            app_class = str(client.get("class") or client.get("initialClass") or "Application")
            title = str(client.get("title") or client.get("initialTitle") or app_class)
            icon_hints = [
                value
                for value in (
                    client.get("icon"),
                    client.get("class"),
                    client.get("initialClass"),
                    client.get("initialTitle"),
                )
                if isinstance(value, str) and value.strip()
            ]
            workspace = client.get("workspace") if isinstance(client.get("workspace"), dict) else {}
            workspace_name = str(workspace.get("name") or workspace.get("id") or "unknown")
            badges = ["Window", "Workspace " + workspace_name]
            if client.get("hidden") is True:
                badges.append("Hidden")
            if client.get("grouped"):
                badges.append("Group")
            if workspace_name.startswith("special:"):
                badges.append("Scratchpad")
            focus_history = int(client.get("focusHistoryID") or 0)
            item_id = stable_id(self.name, address, pid, birth)
            items.append(
                Thing(
                    id=item_id,
                    kind="window",
                    provider="Hyprland",
                    title=title,
                    icon_hints=icon_hints,
                    context=f"{app_class} · workspace {workspace_name}",
                    search_terms=[
                        app_class,
                        str(client.get("initialClass") or ""),
                        str(client.get("initialTitle") or ""),
                        workspace_name,
                    ],
                    badges=badges,
                    active=focus_history == 0 and client.get("hidden") is not True,
                    recency=max(-4000, 4000 - focus_history * 100),
                    activation={
                        "address": address,
                        "pid": pid,
                        "birth": birth,
                    },
                )
            )
            metadata_clients.append(
                {
                    "address": address,
                    "pid": pid,
                    "birth": birth,
                    "class": app_class,
                    "title": title,
                    "item_id": item_id,
                    "workspace": workspace_name,
                    "active": focus_history == 0,
                }
            )
        return ProviderResult(self.name, items, metadata={"clients": metadata_clients})

    async def activate(self, activation: dict[str, Any], context: ScanContext) -> None:
        address = normalized_address(activation.get("address"))
        client = context.client_by_address(address)
        if not client:
            # Exact-address liveness is rechecked immediately before dispatch;
            # an address that vanished is stale, never redirected by title.
            refreshed = await self.scan(context)
            client = context.client_by_address(address)
            if not client:
                raise CommandError("window is no longer managed")
        pid = int(client.get("pid") or 0)
        if pid != int(activation.get("pid") or 0) or process_birth(pid) != str(activation.get("birth")):
            raise CommandError("window address was reused by another process")
        await focus_address(context, address)
