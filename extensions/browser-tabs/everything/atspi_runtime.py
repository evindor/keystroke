from __future__ import annotations

import asyncio
import json
import os
import select
import signal
import sys
import threading
from collections.abc import Awaitable, Callable, Iterator
from concurrent.futures import Future
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Protocol, TypeVar


Result = TypeVar("Result")
AT_SPI_CLOSE_TIMEOUT = 0.5
AT_SPI_CLOSE_POLL_INTERVAL = 0.01
_AT_SPI_CANCEL_EVENT: ContextVar[threading.Event | None] = ContextVar(
    "everything_atspi_cancel_event",
    default=None,
)


def atspi_cancel_checkpoint() -> None:
    """Abort cancelled owner-thread work between synchronous native calls."""

    event = _AT_SPI_CANCEL_EVENT.get()
    if event is not None and event.is_set():
        raise asyncio.CancelledError


@contextmanager
def atspi_cleanup() -> Iterator[None]:
    """Allow owner-thread modal cleanup after the operation was cancelled."""

    token = _AT_SPI_CANCEL_EVENT.set(None)
    try:
        yield
    finally:
        _AT_SPI_CANCEL_EVENT.reset(token)


class AtspiExecutor:
    """Run every in-process AT-SPI operation on one dedicated asyncio thread."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._lock = threading.Lock()
        self._cancel_events: set[threading.Event] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._closed = False
        self._startup_error: BaseException | None = None
        self.thread_id: int | None = None
        self._thread = threading.Thread(
            target=self._thread_main,
            name="everything-atspi-owner",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(2.0):
            raise RuntimeError("AT-SPI owner thread did not start")
        if self._startup_error is not None:
            raise RuntimeError("AT-SPI owner thread failed to start") from self._startup_error

    def _thread_main(self) -> None:
        loop: asyncio.AbstractEventLoop | None = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self.thread_id = threading.get_ident()
        except BaseException as error:
            self._startup_error = error
            self._ready.set()
            return
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            asyncio.set_event_loop(None)

    async def run(self, factory: Callable[[], Awaitable[Result]]) -> Result:
        with self._lock:
            if self._closed or self._loop is None:
                raise RuntimeError("AT-SPI owner thread is closed")
            cancel_event = threading.Event()
            self._cancel_events.add(cancel_event)
            loop = self._loop

        async def invoke() -> Result:
            token = _AT_SPI_CANCEL_EVENT.set(cancel_event)
            try:
                atspi_cancel_checkpoint()
                return await factory()
            finally:
                _AT_SPI_CANCEL_EVENT.reset(token)

        future: Future[Result] = asyncio.run_coroutine_threadsafe(invoke(), loop)
        try:
            return await asyncio.wrap_future(future)
        except asyncio.CancelledError:
            # Setting the event does not need the owner loop to be runnable, so
            # a synchronous tree walk observes cancellation at its next native
            # call even while that loop is occupied by the current coroutine.
            cancel_event.set()
            future.cancel()
            raise
        finally:
            with self._lock:
                self._cancel_events.discard(cancel_event)

    async def close(self, *, timeout: float = AT_SPI_CLOSE_TIMEOUT) -> bool:
        with self._lock:
            first_close = not self._closed
            self._closed = True
            events = tuple(self._cancel_events) if first_close else ()
            loop = self._loop
        for event in events:
            event.set()
        if first_close and loop is not None:
            try:
                loop.call_soon_threadsafe(loop.stop)
            except RuntimeError:
                # The owner completed between the lock release and the stop
                # request. is_alive() below remains the source of truth.
                pass

        # Never hand an unbounded Thread.join to asyncio's default executor.
        # Its worker is non-daemon and would itself keep the helper or a test
        # process alive if one libatspi call never returned. Polling the daemon
        # owner keeps shutdown cancellable and bounded; normal completion still
        # joins immediately once the owner has released its thread-state lock.
        timeout = max(0.0, float(timeout))
        deadline = asyncio.get_running_loop().time() + timeout
        while self._thread.is_alive():
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(AT_SPI_CLOSE_POLL_INTERVAL, remaining))
        self._thread.join(timeout=0)
        return True


class StatusBackend(Protocol):
    def get(self, name: str) -> bool: ...

    def set(self, name: str, value: bool) -> None: ...


class GioStatusBackend:
    def __init__(self) -> None:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib

        self.Gio = Gio
        self.GLib = GLib
        self.proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.NONE,
            None,
            "org.a11y.Bus",
            "/org/a11y/bus",
            "org.freedesktop.DBus.Properties",
            None,
        )

    def get(self, name: str) -> bool:
        result = self.proxy.call_sync(
            "Get",
            self.GLib.Variant("(ss)", ("org.a11y.Status", name)),
            self.Gio.DBusCallFlags.NONE,
            1500,
            None,
        )
        unpacked = result.unpack()[0]
        if hasattr(unpacked, "unpack"):
            unpacked = unpacked.unpack()
        return bool(unpacked)

    def set(self, name: str, value: bool) -> None:
        self.proxy.call_sync(
            "Set",
            self.GLib.Variant(
                "(ssv)",
                ("org.a11y.Status", name, self.GLib.Variant("b", bool(value))),
            ),
            self.Gio.DBusCallFlags.NONE,
            1500,
            None,
        )


@dataclass(slots=True)
class AtspiRuntimeLease:
    """Temporarily enables AT-SPI, never screen-reader mode."""

    backend: StatusBackend
    original_enabled: bool | None = None
    original_screen_reader: bool | None = None
    changed: bool = False

    def acquire(self) -> None:
        if self.original_enabled is not None:
            return
        self.original_enabled = self.backend.get("IsEnabled")
        self.original_screen_reader = self.backend.get("ScreenReaderEnabled")
        if not self.original_enabled:
            self.backend.set("IsEnabled", True)
            self.changed = True

    def restore(self) -> None:
        if self.original_enabled is None:
            return
        try:
            if self.changed:
                self.backend.set("IsEnabled", self.original_enabled)
            # Everything never writes ScreenReaderEnabled. If an external
            # actor changed it while the panel was open, leave that choice
            # alone rather than racing it during restoration.
        finally:
            self.original_enabled = None
            self.original_screen_reader = None
            self.changed = False


def run_guard(parent_pid: int) -> int:
    """Own the runtime flag so pipe EOF restores it even if the helper dies."""

    lease: AtspiRuntimeLease | None = None
    stopping = False

    def stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        lease = AtspiRuntimeLease(GioStatusBackend())
        lease.acquire()
        print(
            json.dumps(
                {
                    "ok": True,
                    "changed": lease.changed,
                    "enabledBefore": lease.original_enabled,
                    "screenReaderBefore": lease.original_screen_reader,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )
    except Exception as error:  # D-Bus absence is a provider failure, not fatal.
        print(json.dumps({"ok": False, "error": str(error)}, separators=(",", ":")), flush=True)
        return 1

    try:
        descriptor = sys.stdin.fileno()
        while not stopping:
            if os.getppid() != parent_pid:
                break
            readable, _, _ = select.select([descriptor], [], [], 0.5)
            if not readable:
                continue
            data = os.read(descriptor, 4096)
            if not data or b"stop" in data:
                break
    finally:
        if lease:
            lease.restore()
    return 0


class AtspiGuardClient:
    def __init__(self, helper_path: str) -> None:
        self.helper_path = helper_path
        self.process: asyncio.subprocess.Process | None = None
        self.warning = ""

    async def start(self) -> bool:
        if self.process and self.process.returncode is None:
            return True
        self.process = await asyncio.create_subprocess_exec(
            sys.executable,
            self.helper_path,
            "--atspi-guard",
            str(os.getpid()),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            line = await asyncio.wait_for(self.process.stdout.readline(), 3.0)  # type: ignore[union-attr]
            status = json.loads(line)
        except (TimeoutError, json.JSONDecodeError, TypeError) as error:
            self.warning = f"AT-SPI runtime guard did not start: {error}"
            await self.stop()
            return False
        if not isinstance(status, dict) or status.get("ok") is not True:
            self.warning = "AT-SPI unavailable: " + str(status.get("error") or "unknown error")
            await self.stop()
            return False
        return True

    async def stop(self) -> None:
        process = self.process
        self.process = None
        if not process or process.returncode is not None:
            return
        if process.stdin:
            try:
                process.stdin.write(b"stop\n")
                await process.stdin.drain()
                process.stdin.close()
            except (BrokenPipeError, ConnectionResetError):
                pass
        try:
            await asyncio.wait_for(process.wait(), 2.0)
        except TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 1.0)
            except TimeoutError:
                process.kill()
                await process.wait()
