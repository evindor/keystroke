from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ..commands import CommandRunner
from ..model import Thing, process_birth
from ..processes import ProcTable, canonical_path


@dataclass(slots=True)
class ProviderResult:
    provider: str
    items: list[Thing] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScanContext:
    runner: CommandRunner
    processes: ProcTable
    hypr_clients: list[dict[str, Any]] = field(default_factory=list)
    hypr_matching_clients: list[dict[str, Any]] = field(default_factory=list)
    provider_metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    providers: dict[str, Any] = field(default_factory=dict)
    include_ghostty: bool = False
    allow_ghostty_palette: bool = False

    def clients_for_pid(self, pid: int) -> list[dict[str, Any]]:
        return [client for client in self.hypr_clients if int(client.get("pid") or 0) == int(pid)]

    def matching_clients_for_pid(self, pid: int) -> list[dict[str, Any]]:
        # Unit/provider callers that do not run Hyprland first retain the
        # historical mapped-client input. A real discovery generation always
        # supplies the full matching-evidence list explicitly.
        clients = self.hypr_matching_clients or self.hypr_clients
        return [client for client in clients if int(client.get("pid") or 0) == int(pid)]

    def client_by_address(self, address: str) -> dict[str, Any] | None:
        wanted = normalized_address(address)
        for client in self.hypr_clients:
            if normalized_address(client.get("address")) == wanted:
                return client
        return None


class Provider(Protocol):
    name: str

    async def scan(self, context: ScanContext) -> ProviderResult: ...

    async def activate(self, activation: dict[str, Any], context: ScanContext) -> None: ...


def normalized_address(value: Any) -> str:
    address = str(value or "").strip().lower()
    if address and not address.startswith("0x"):
        address = "0x" + address
    return address


def route_for_process(
    context: ScanContext,
    pid: int,
    *,
    title: str = "",
    cwd: str = "",
) -> dict[str, Any] | None:
    """Resolve one process to a proven terminal surface or managed window.

    Internal terminal surfaces win over their outer client. If an internal
    adapter knows that a process has multiple surfaces, exact title plus cwd
    is required; otherwise callers must open a fresh client instead of
    guessing. Shared-PID managed clients (notably foot server windows) are
    likewise ambiguous unless a native adapter supplied an exact surface.
    """

    wanted_cwd = canonical_path(cwd)
    ancestors = context.processes.ancestors(pid)
    ancestor_pids = {process.pid for process in ancestors}

    for provider_name in ("kitty", "ghostty"):
        all_surfaces = context.provider_metadata.get(provider_name, {}).get("surfaces", [])
        process_surfaces = [
            surface
            for surface in all_surfaces
            if int(surface.get("pid") or 0) in ancestor_pids
        ]
        if not process_surfaces:
            continue
        if len(process_surfaces) == 1:
            surface = process_surfaces[0]
            return {
                "provider": provider_name,
                "activation": dict(surface.get("activation") or {}),
                "item_id": str(surface.get("item_id") or ""),
            }
        matches = [
            surface
            for surface in process_surfaces
            if title
            and str(surface.get("title") or "") == title
            and wanted_cwd
            and canonical_path(str(surface.get("cwd") or "")) == wanted_cwd
        ]
        if len(matches) == 1:
            surface = matches[0]
            return {
                "provider": provider_name,
                "activation": dict(surface.get("activation") or {}),
                "item_id": str(surface.get("item_id") or ""),
            }
        return None

    # If a process is known to live inside an internal terminal but that
    # provider has no current metadata, treating the outer window as its pane
    # would be a guess. This also covers activation before a partial scan has
    # finished.
    internal_names = {"kitty", "ghostty"}
    if any(
        process.comm.lower() in internal_names
        or (process.argv and process.argv[0].rsplit("/", 1)[-1].lower() in internal_names)
        for process in ancestors
    ):
        return None

    managed_pids = {int(client.get("pid") or 0) for client in context.hypr_clients}
    ancestor_pid = context.processes.ancestor_pid_in(pid, managed_pids)
    if not ancestor_pid:
        return None
    clients = context.clients_for_pid(ancestor_pid)
    if len(clients) != 1:
        return None
    client = clients[0]
    address = normalized_address(client.get("address"))
    return {
        "provider": "hyprland",
        "activation": {
            "address": address,
            "pid": ancestor_pid,
            "birth": process_birth(ancestor_pid),
        },
        "item_id": next(
            (
                str(row.get("item_id") or "")
                for row in context.provider_metadata.get("hyprland", {}).get("clients", [])
                if normalized_address(row.get("address")) == address
            ),
            "",
        ),
    }
