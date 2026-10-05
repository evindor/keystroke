from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(slots=True)
class ProcessInfo:
    pid: int
    ppid: int
    start_time: str
    comm: str
    argv: tuple[str, ...]
    cwd: str


class ProcTable:
    """A bounded, same-user process snapshot used only as routing metadata."""

    def __init__(self, processes: dict[int, ProcessInfo], uid: int | None = None) -> None:
        self.processes = processes
        self.uid = os.getuid() if uid is None else uid

    @classmethod
    def read(cls, proc_root: str = "/proc", uid: int | None = None) -> "ProcTable":
        owner = os.getuid() if uid is None else uid
        processes: dict[int, ProcessInfo] = {}
        try:
            entries = os.scandir(proc_root)
        except OSError:
            return cls({}, owner)
        with entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                pid = int(entry.name)
                base = os.path.join(proc_root, entry.name)
                try:
                    if os.stat(base).st_uid != owner:
                        continue
                    stat = Path(base, "stat").read_text(encoding="utf-8")
                    closing = stat.rfind(")")
                    comm = stat[stat.find("(") + 1 : closing]
                    fields = stat[closing + 2 :].split()
                    ppid = int(fields[1])
                    start_time = fields[19]
                    raw = Path(base, "cmdline").read_bytes()
                    argv = tuple(
                        part.decode("utf-8", "replace") for part in raw.split(b"\0") if part
                    )
                    try:
                        cwd = os.path.realpath(os.readlink(Path(base, "cwd")))
                    except OSError:
                        cwd = ""
                    processes[pid] = ProcessInfo(pid, ppid, start_time, comm, argv, cwd)
                except (OSError, ValueError, IndexError):
                    continue
        return cls(processes, owner)

    def get(self, pid: int | str | None) -> ProcessInfo | None:
        try:
            return self.processes.get(int(pid or 0))
        except (TypeError, ValueError):
            return None

    def ancestors(self, pid: int | str | None, limit: int = 128) -> list[ProcessInfo]:
        out: list[ProcessInfo] = []
        seen: set[int] = set()
        current = self.get(pid)
        while current and current.pid not in seen and len(out) < limit:
            out.append(current)
            seen.add(current.pid)
            current = self.get(current.ppid)
        return out

    def ancestor_pid_in(self, pid: int | str | None, candidates: Iterable[int]) -> int | None:
        wanted = {int(candidate) for candidate in candidates}
        for process in self.ancestors(pid):
            if process.pid in wanted:
                return process.pid
        return None

    def is_descendant(self, pid: int, ancestor_pid: int) -> bool:
        return any(process.pid == ancestor_pid for process in self.ancestors(pid))

    def named(self, *names: str) -> list[ProcessInfo]:
        wanted = {name.lower() for name in names}
        return [
            process
            for process in self.processes.values()
            if process.comm.lower() in wanted
            or (process.argv and os.path.basename(process.argv[0]).lower() in wanted)
        ]

    def environment(
        self,
        pid: int | str | None,
        names: Iterable[str],
        *,
        proc_root: str = "/proc",
        max_bytes: int = 256 * 1024,
    ) -> dict[str, str]:
        """Read only explicitly requested variables from one same-user process."""

        process = self.get(pid)
        wanted = {str(name) for name in names if str(name)}
        if not process or not wanted or max_bytes <= 0:
            return {}
        base = Path(proc_root, str(process.pid))
        try:
            if os.stat(base, follow_symlinks=False).st_uid != self.uid:
                return {}
            with Path(base, "environ").open("rb") as handle:
                raw = handle.read(max_bytes + 1)
        except OSError:
            return {}
        if len(raw) > max_bytes:
            return {}

        values: dict[str, str] = {}
        for entry in raw.split(b"\0"):
            key, separator, value = entry.partition(b"=")
            if not separator:
                continue
            name = key.decode("utf-8", "replace")
            if name in wanted:
                values[name] = value.decode("utf-8", "replace")
        return values


def canonical_path(value: str) -> str:
    if not value:
        return ""
    try:
        return os.path.realpath(os.path.expanduser(value))
    except (OSError, ValueError):
        return value


def username(uid: int | None = None) -> str:
    try:
        return pwd.getpwuid(os.getuid() if uid is None else uid).pw_name
    except KeyError:
        return str(os.getuid() if uid is None else uid)
