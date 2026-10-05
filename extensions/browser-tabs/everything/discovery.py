from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .atspi_runtime import AtspiExecutor
from .commands import CommandError, CommandRunner
from .model import SnapshotRegistry, TokenError
from .processes import ProcTable
from .providers import AtspiProvider, HyprlandProvider
from .providers.base import ProviderResult, ScanContext


Emitter = Callable[[dict[str, Any]], Awaitable[None]]


class DiscoveryManager:
    def __init__(
        self,
        emit: Emitter,
        *,
        atspi_available: bool = True,
        test_mode: bool = False,
    ) -> None:
        self.emit = emit
        self.runner = CommandRunner()
        self.registry = SnapshotRegistry()
        self.metadata: dict[str, dict[str, Any]] = {}
        self.warnings: dict[str, list[str]] = {}
        self.test_mode = test_mode
        self.allow_ghostty_palette = False
        self.providers: dict[str, Any] = {}
        self.atspi_executor: AtspiExecutor | None = None
        if not test_mode:
            # Keystroke browser-tabs: Hyprland (exact window routing) and AT-SPI (tabs) only.
            self.providers = {"hyprland": HyprlandProvider()}
            if atspi_available:
                self.atspi_executor = AtspiExecutor()
                self.providers["atspi"] = AtspiProvider()

    async def close(self) -> None:
        if self.atspi_executor is not None:
            executor = self.atspi_executor
            self.atspi_executor = None
            await executor.close()

    async def _scan_provider(self, name: str, context: ScanContext) -> ProviderResult:
        provider = self.providers[name]
        if name in {"atspi", "ghostty"} and self.atspi_executor is not None:
            return await self.atspi_executor.run(lambda: provider.scan(context))
        return await provider.scan(context)

    async def _activate_provider(
        self,
        name: str,
        activation: dict[str, Any],
        context: ScanContext,
    ) -> None:
        provider = self.providers[name]
        if name in {"atspi", "ghostty"} and self.atspi_executor is not None:
            await self.atspi_executor.run(lambda: provider.activate(activation, context))
            return
        await provider.activate(activation, context)

    def context(self, *, include_ghostty: bool = False) -> ScanContext:
        return ScanContext(
            runner=self.runner,
            processes=ProcTable.read(),
            provider_metadata=self.metadata,
            providers=self.providers,
            include_ghostty=include_ghostty,
            allow_ghostty_palette=self.allow_ghostty_palette,
        )

    async def scan(
        self, request_id: str, *, include_ghostty: bool, allow_ghostty_palette: bool = False
    ) -> None:
        self.allow_ghostty_palette = allow_ghostty_palette
        if self.test_mode:
            await self.emit(
                {
                    "version": 1,
                    "type": "snapshot",
                    "requestId": request_id,
                    "full": True,
                    "items": [],
                    "providers": {},
                    "warnings": [],
                }
            )
            return

        context = self.context(include_ghostty=include_ghostty)
        hyprland = self.providers["hyprland"]
        try:
            hypr_result = await hyprland.scan(context)
            await self._publish_partial(request_id, hypr_result)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self._publish_failure(request_id, "hyprland", error)
            await self._emit_full(request_id)
            return

        provider_names = ["atspi", "kitty", "tmux", "herdr", "neovim", "ghostty"]
        provider_names = [name for name in provider_names if name in self.providers]

        async def run_provider(name: str) -> tuple[str, ProviderResult | None, Exception | None]:
            try:
                return name, await self._scan_provider(name, context), None
            except asyncio.CancelledError:
                raise
            except Exception as error:
                return name, None, error

        tasks = [asyncio.create_task(run_provider(name), name=f"scan:{name}") for name in provider_names]
        try:
            for completed in asyncio.as_completed(tasks):
                name, result, error = await completed
                if error:
                    await self._publish_failure(request_id, name, error)
                    continue
                assert result is not None
                await self._publish_partial(request_id, result)

            # Neovim scans concurrently for responsiveness, then makes one
            # cheap second RPC after container metadata arrives so breadcrumbs
            # and activation routes never guess a host.
            if "neovim" in provider_names:
                try:
                    context.processes = ProcTable.read()
                    result = await self.providers["neovim"].scan(context)
                    await self._publish_partial(request_id, result)
                except asyncio.CancelledError:
                    raise
                except Exception as error:
                    await self._publish_failure(request_id, "neovim", error)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        await self._emit_full(request_id)

    async def _publish_partial(self, request_id: str, result: ProviderResult) -> None:
        self.metadata[result.provider] = result.metadata
        self.warnings[result.provider] = list(result.warnings)
        public = self.registry.publish(result.provider, result.items)
        await self.emit(
            {
                "version": 1,
                "type": "snapshot",
                "requestId": request_id,
                "provider": result.provider,
                "full": False,
                "items": public,
                "warnings": result.warnings,
            }
        )

    async def _emit_full(self, request_id: str) -> None:
        providers = {
            provider: self.registry.provider_public(provider)
            for provider in sorted(self.registry.providers)
        }
        await self.emit(
            {
                "version": 1,
                "type": "snapshot",
                "requestId": request_id,
                "full": True,
                "items": self.registry.all_public(),
                "providers": providers,
                "warnings": [
                    warning
                    for provider in sorted(self.warnings)
                    for warning in self.warnings[provider]
                ],
            }
        )

    async def _emit_error(self, request_id: str, provider: str, error: Exception) -> None:
        await self.emit(
            {
                "version": 1,
                "type": "error",
                "requestId": request_id,
                "provider": provider,
                "message": f"{self._label(provider)}: {self._error_text(error)}",
                "nonfatal": True,
            }
        )

    async def _publish_failure(
        self, request_id: str, provider: str, error: Exception
    ) -> None:
        warning = f"{self._label(provider)}: {self._error_text(error)}"
        self.warnings[provider] = [warning]
        public = self.registry.publish(provider, [])
        await self.emit(
            {
                "version": 1,
                "type": "snapshot",
                "requestId": request_id,
                "provider": provider,
                "full": False,
                "items": public,
                "warnings": [warning],
            }
        )
        await self._emit_error(request_id, provider, error)

    async def activate(self, request_id: str, item_id: str, token: str) -> None:
        if self.test_mode:
            await self._activation_response(request_id, item_id, False, True, "Unknown test thing")
            return
        try:
            reference = self.registry.decode_reference(item_id, token)
        except TokenError as error:
            await self._activation_response(request_id, item_id, False, True, str(error))
            return
        provider_name = str(reference["provider"])
        provider = self.providers.get(provider_name)
        if not provider:
            await self._activation_response(request_id, item_id, False, True, "Thing provider is unavailable")
            return

        context = self.context(
            include_ghostty=provider_name == "ghostty"
            and reference.get("activation", {}).get("target") == "surface"
        )
        try:
            # Refresh exact managed clients without publishing a new Hyprland
            # generation, otherwise merely checking liveness would stale the
            # token currently displayed in QML.
            if "hyprland" in self.providers:
                hypr = await self.providers["hyprland"].scan(context)
                self.metadata["hyprland"] = hypr.metadata
            row = self.registry.current(provider_name, item_id)
            if not row or not self.registry.token_is_current(reference):
                row = await self._refresh_for_activation(provider_name, item_id, context)
                if not row:
                    raise StaleThing("That thing closed before it could be focused")

            activation = dict(row.thing.activation)
            activation["item_id"] = item_id
            try:
                await self._activate_provider(provider_name, activation, context)
            except Exception as first_error:
                if not self._looks_stale(first_error):
                    raise
                # Exactly one stale refresh/retry. The refreshed native id must
                # still be the same row; title-only lookalikes do not qualify.
                refreshed = await self._refresh_for_activation(provider_name, item_id, context)
                if not refreshed:
                    raise StaleThing("That thing closed before it could be focused") from first_error
                activation = dict(refreshed.thing.activation)
                activation["item_id"] = item_id
                await self._activate_provider(provider_name, activation, context)
        except Exception as error:
            stale = isinstance(error, StaleThing) or self._looks_stale(error)
            await self._activation_response(
                request_id,
                item_id,
                False,
                stale,
                self._error_text(error) or "Could not focus that thing",
            )
            return
        await self._activation_response(request_id, item_id, True, False, "")

    async def _refresh_for_activation(
        self, provider_name: str, item_id: str, context: ScanContext
    ) -> Any:
        context.processes = ProcTable.read()
        try:
            result = await self._scan_provider(provider_name, context)
        except Exception:
            return None
        self.metadata[provider_name] = result.metadata
        self.warnings[provider_name] = result.warnings
        self.registry.publish(provider_name, result.items)
        return self.registry.current(provider_name, item_id)

    async def _activation_response(
        self,
        request_id: str,
        item_id: str,
        ok: bool,
        stale: bool,
        message: str,
    ) -> None:
        await self.emit(
            {
                "version": 1,
                "type": "activation",
                "requestId": request_id,
                "itemId": item_id,
                "ok": ok,
                "stale": stale,
                "message": message,
            }
        )

    @staticmethod
    def _looks_stale(error: Exception) -> bool:
        text = str(error).lower()
        return any(
            word in text
            for word in ("stale", "closed", "replaced", "reused", "no longer", "disappeared", "not found")
        )

    @staticmethod
    def _error_text(error: Exception) -> str:
        return str(error).strip() or error.__class__.__name__

    @staticmethod
    def _label(provider: str) -> str:
        return {
            "atspi": "AT-SPI tabs",
            "hyprland": "Hyprland",
            "kitty": "Kitty",
            "ghostty": "Ghostty",
            "tmux": "tmux",
            "herdr": "Herdr",
            "neovim": "Neovim",
        }.get(provider, provider)


class StaleThing(CommandError):
    pass
