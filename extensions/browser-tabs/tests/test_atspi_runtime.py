from __future__ import annotations

import asyncio
import threading
import unittest
from unittest.mock import patch

from everything.atspi_runtime import AtspiExecutor, AtspiRuntimeLease


class FakeStatus:
    def __init__(self, enabled: bool, reader: bool) -> None:
        self.values = {"IsEnabled": enabled, "ScreenReaderEnabled": reader}
        self.writes: list[tuple[str, bool]] = []

    def get(self, name: str) -> bool:
        return self.values[name]

    def set(self, name: str, value: bool) -> None:
        self.values[name] = value
        self.writes.append((name, value))


class AtspiLeaseTests(unittest.TestCase):
    def test_disabled_state_is_restored(self) -> None:
        backend = FakeStatus(False, False)
        lease = AtspiRuntimeLease(backend)
        lease.acquire()
        self.assertTrue(backend.values["IsEnabled"])
        lease.restore()
        self.assertFalse(backend.values["IsEnabled"])
        self.assertEqual(backend.writes, [("IsEnabled", True), ("IsEnabled", False)])

    def test_existing_enabled_state_is_untouched(self) -> None:
        backend = FakeStatus(True, False)
        lease = AtspiRuntimeLease(backend)
        lease.acquire()
        lease.restore()
        self.assertEqual(backend.writes, [])

    def test_screen_reader_mode_is_never_written(self) -> None:
        backend = FakeStatus(False, True)
        lease = AtspiRuntimeLease(backend)
        lease.acquire()
        lease.restore()
        self.assertNotIn("ScreenReaderEnabled", [name for name, _value in backend.writes])
        self.assertTrue(backend.values["ScreenReaderEnabled"])


class AtspiExecutorTests(unittest.IsolatedAsyncioTestCase):
    async def test_close_is_bounded_without_a_default_executor_joiner(self) -> None:
        started = threading.Event()
        release = threading.Event()
        executor = AtspiExecutor()

        async def blocked_native_call() -> None:
            started.set()
            release.wait()

        task = asyncio.create_task(executor.run(blocked_native_call))
        try:
            for _attempt in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(0.001)
            self.assertTrue(started.is_set())

            # A stalled native call cannot be interrupted in the middle of the
            # call. Shutdown must still return without creating a non-daemon
            # executor worker that blocks interpreter exit on Thread.join.
            with patch(
                "everything.atspi_runtime.asyncio.to_thread",
                side_effect=AssertionError("close must not create a join worker"),
            ):
                stopped = await asyncio.wait_for(
                    executor.close(timeout=0.02),
                    0.2,
                )
            self.assertFalse(stopped)
            self.assertTrue(executor._thread.daemon)
            self.assertTrue(executor._thread.is_alive())
        finally:
            if not task.done():
                task.cancel()
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            self.assertTrue(await executor.close(timeout=0.5))


if __name__ == "__main__":
    unittest.main()
