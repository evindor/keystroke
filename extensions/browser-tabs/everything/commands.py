from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Mapping, Sequence


class CommandError(RuntimeError):
    pass


class CommandTimeout(CommandError):
    pass


def safe_argv(argv: Sequence[object]) -> tuple[str, ...]:
    if isinstance(argv, (str, bytes)):
        raise TypeError("commands must be argv arrays, never shell strings")
    values = tuple(str(value) for value in argv)
    if not values or not values[0]:
        raise ValueError("command argv must not be empty")
    if any("\x00" in value or "\n" in value or "\r" in value for value in values):
        raise ValueError("command arguments must be single NUL-free strings")
    return values


@dataclass(slots=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str

    def require_success(self) -> "CommandResult":
        if self.returncode != 0:
            detail = self.stderr.strip() or self.stdout.strip() or f"exit {self.returncode}"
            raise CommandError(f"{self.argv[0]} failed: {detail}")
        return self


class CommandRunner:
    def __init__(self, default_timeout: float = 1.5) -> None:
        self.default_timeout = default_timeout

    async def run(
        self,
        argv: Sequence[object],
        *,
        timeout: float | None = None,
        input_text: str | None = None,
        env: Mapping[str, str] | None = None,
        check: bool = False,
    ) -> CommandResult:
        command = safe_argv(argv)
        stdin = asyncio.subprocess.PIPE if input_text is not None else asyncio.subprocess.DEVNULL
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=stdin,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=dict(env) if env is not None else None,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(None if input_text is None else input_text.encode()),
                timeout=self.default_timeout if timeout is None else timeout,
            )
        except TimeoutError as error:
            process.kill()
            await process.communicate()
            raise CommandTimeout(f"{command[0]} timed out") from error
        result = CommandResult(
            command,
            int(process.returncode or 0),
            stdout.decode("utf-8", "replace"),
            stderr.decode("utf-8", "replace"),
        )
        return result.require_success() if check else result

    async def spawn_detached(self, argv: Sequence[object], *, env: Mapping[str, str] | None = None) -> int:
        command = safe_argv(argv)
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env=dict(env) if env is not None else None,
            start_new_session=True,
        )
        return int(process.pid)


async def unix_json_request(
    socket_path: str,
    request: dict,
    *,
    timeout: float = 1.0,
    max_bytes: int = 8 * 1024 * 1024,
) -> dict:
    if not os.path.isabs(socket_path) or "\x00" in socket_path:
        raise ValueError("Unix socket path must be an absolute NUL-free path")
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(socket_path), timeout)
    try:
        raw = (json_dumps(request) + "\n").encode()
        writer.write(raw)
        await asyncio.wait_for(writer.drain(), timeout)
        line = await asyncio.wait_for(reader.readline(), timeout)
        if not line or len(line) > max_bytes:
            raise CommandError("socket returned an empty or oversized response")
        import json

        value = json.loads(line)
        if not isinstance(value, dict):
            raise CommandError("socket response is not a JSON object")
        return value
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass


def json_dumps(value: object) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
