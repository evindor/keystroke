"""Small SDK shared by bundled extensions. No desktop capabilities live here."""
from __future__ import annotations

import asyncio
import json
import os
import re
import signal
from pathlib import Path


def row(id, title, subtitle="", icon="⌘", *, action=None, **extra):
    return dict(id=id, title=title, subtitle=subtitle, icon=icon,
                action=action or {}, **extra)


def navigate(scope):
    return {"type": "navigate", "scope": scope}


def copy(text):
    return {"type": "copy", "text": str(text)}


def command(*argv):
    return {"type": "exec", "argv": list(argv)}


async def run(argv, *, timeout=2, input=None, limit=1_048_576):
    """Bound output, time and process lifetime, including on query cancellation."""
    proc = await asyncio.create_subprocess_exec(
        *argv, stdin=asyncio.subprocess.PIPE if input is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        start_new_session=True)
    async def communicate():
        if input is not None:
            proc.stdin.write(input.encode())
            await proc.stdin.drain()
            proc.stdin.close()
        data = bytearray()
        while chunk := await proc.stdout.read(65536):
            data.extend(chunk)
            if len(data) > limit:
                raise ValueError("Extension output exceeded 1 MiB")
        await proc.wait()
        if proc.returncode:
            raise RuntimeError(f"{Path(argv[0]).name} exited with status {proc.returncode}")
        return data.decode("utf-8", "replace")
    try:
        return await asyncio.wait_for(communicate(), timeout)
    except BaseException:
        # Descendants can retain pipes even after the leader exits.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await proc.wait()
        raise


def read_jsonc(path):
    """Strip comments and trailing commas without corrupting quoted URLs."""
    raw = Path(path).read_text()
    out, i, quoted, escaped = [], 0, False, False
    while i < len(raw):
        c = raw[i]
        if quoted:
            out.append(c)
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                quoted = False
            i += 1
        elif c == '"':
            quoted = True
            out.append(c)
            i += 1
        elif raw[i:i+2] == "//":
            end = raw.find("\n", i)
            i = len(raw) if end < 0 else end
        elif raw[i:i+2] == "/*":
            end = raw.find("*/", i+2)
            if end < 0:
                raise ValueError("Unclosed JSONC comment")
            out.append(" ")
            i = end + 2
        else:
            out.append(c)
            i += 1
    raw = "".join(out)
    out, quoted, escaped = [], False, False
    for i, c in enumerate(raw):
        if not quoted and c == "," and raw[i+1:].lstrip().startswith(("}", "]")):
            continue
        out.append(c)
        if escaped:
            escaped = False
        elif quoted and c == "\\":
            escaped = True
        elif c == '"':
            quoted = not quoted
    return json.loads("".join(out))


def score(query, title, keywords=""):
    """Prefer whole words; allow only short gaps within a closely matching word."""
    q, name = query.casefold().strip(), title.casefold()
    if not q:
        return 1
    if q == name:
        return 120
    terms = re.findall(r"\w+", q)
    words = re.findall(r"\w+", name)
    if not terms:
        return 0
    if len(terms) == 1:
        for index, word in enumerate(words):
            if word == q:
                return 112 - min(index, 3)
        prefixes = [100 + 10 * len(q) / len(w) - min(i, 3)
                    for i, w in enumerate(words) if w.startswith(q)]
        if prefixes:
            return max(prefixes)
    if all(any(w.startswith(t) for w in words) for t in terms):
        return 95
    if len(q) >= 3 and q in name:
        return 78
    metadata = re.findall(r"\w+", keywords.casefold())
    if all(any(w.startswith(t) for w in words + metadata) for t in terms):
        return 60
    if len(terms) == 1 and len(q) >= 3:
        for word in words:
            if not word.startswith(q[0]) or len(q) / len(word) < .65:
                continue
            pos, gaps = -1, 0
            for c in q:
                nxt = word.find(c, pos + 1)
                if nxt < 0:
                    break
                gaps += nxt - pos - 1
                pos = nxt
            else:
                if gaps <= 2:
                    return 45 - gaps * 5
    return 0
