from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote


SUPPORTED_KINDS = frozenset(
    {
        "window",
        "browser-tab",
        "app-tab",
        "terminal-tab",
        "terminal-pane",
        "tmux-session",
        "tmux-window",
        "tmux-pane",
        "herdr-session",
        "herdr-workspace",
        "herdr-tab",
        "herdr-pane",
        "herdr-agent",
        "neovim-buffer",
    }
)

UI_ITEM_NAMESPACE = uuid.UUID("40ad37f5-b488-50bc-b3ad-d310967b3fd2")


def identity_component(value: Any) -> str:
    """Encode one native identity component without permitting ambiguity."""

    if value is None:
        value = ""
    return quote(str(value), safe="-._~")


def stable_id(provider: str, *parts: Any) -> str:
    if not provider or any(character in provider for character in "/%\n\r"):
        raise ValueError("provider must be a non-empty simple name")
    if not parts:
        raise ValueError("an identity needs at least one native component")
    return provider + ":" + "/".join(identity_component(part) for part in parts)


def thing_ui_uuid(provider: str, kind: str, identifier: str) -> str:
    """Create the stable UUID used only for list reconciliation in QML."""

    traits = json.dumps(
        [str(provider), str(kind), str(identifier)],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return str(uuid.uuid5(UI_ITEM_NAMESPACE, traits))


@dataclass(slots=True)
class Thing:
    id: str
    kind: str
    provider: str
    title: str
    icon_hints: list[str] = field(default_factory=list)
    context: str = ""
    search_terms: list[str] = field(default_factory=list)
    parent_id: str = ""
    badges: list[str] = field(default_factory=list)
    active: bool = False
    recency: float = 0.0
    activation: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.id or "\n" in self.id or "\r" in self.id:
            raise ValueError("thing id must be a non-empty single line")
        if self.kind not in SUPPORTED_KINDS:
            raise ValueError(f"unsupported thing kind: {self.kind}")
        if not self.provider:
            raise ValueError("provider is required for every thing")
        self.title = str(self.title or "Untitled").strip() or "Untitled"
        self.icon_hints = _unique_strings(self.icon_hints)
        self.context = str(self.context or "").strip()
        self.search_terms = _unique_strings(self.search_terms)
        self.badges = _unique_strings(self.badges)
        self.parent_id = str(self.parent_id or "")
        self.recency = float(self.recency or 0.0)

    def public(self, activation_token: str) -> dict[str, Any]:
        return {
            "id": self.id,
            "uiUuid": thing_ui_uuid(self.provider, self.kind, self.id),
            "kind": self.kind,
            "provider": self.provider,
            "title": self.title,
            "iconHints": self.icon_hints,
            "context": self.context,
            "searchTerms": self.search_terms,
            "parentId": self.parent_id,
            "badges": self.badges,
            "active": self.active,
            "recency": self.recency,
            "activationToken": activation_token,
        }


def _unique_strings(values: Iterable[Any] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def dedupe_things(items: Iterable[Thing]) -> list[Thing]:
    """Keep native identities unique while preserving genuine duplicates.

    Equal rows are merged. A provider bug that emits the same id for distinct
    targets gets a deterministic collision suffix rather than silently making
    one thing unreachable.
    """

    out: list[Thing] = []
    positions: dict[str, int] = {}
    collision_counts: dict[str, int] = {}
    for item in items:
        position = positions.get(item.id)
        if position is None:
            positions[item.id] = len(out)
            out.append(item)
            continue

        existing = out[position]
        if existing.activation == item.activation and existing.kind == item.kind:
            out[position] = replace(
                existing,
                icon_hints=_unique_strings(existing.icon_hints + item.icon_hints),
                search_terms=_unique_strings(existing.search_terms + item.search_terms),
                badges=_unique_strings(existing.badges + item.badges),
                active=existing.active or item.active,
                recency=max(existing.recency, item.recency),
            )
            continue

        count = collision_counts.get(item.id, 1) + 1
        collision_counts[item.id] = count
        collision_id = stable_id(item.provider, "collision", item.id, count)
        while collision_id in positions:
            count += 1
            collision_counts[item.id] = count
            collision_id = stable_id(item.provider, "collision", item.id, count)
        positions[collision_id] = len(out)
        out.append(replace(item, id=collision_id))
    return out


class TokenError(ValueError):
    pass


class TokenCodec:
    """Process-local authenticated opaque activation tokens."""

    def __init__(self, secret: bytes | None = None) -> None:
        self._secret = secret or secrets.token_bytes(32)

    def encode(self, payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        signature = hmac.new(self._secret, raw, hashlib.sha256).digest()
        return "v1." + _b64(raw) + "." + _b64(signature)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            prefix, body, signature = str(token).split(".", 2)
            if prefix != "v1":
                raise TokenError("unsupported activation token version")
            raw = _unb64(body)
            supplied = _unb64(signature)
        except (ValueError, TypeError) as error:
            raise TokenError("malformed activation token") from error
        expected = hmac.new(self._secret, raw, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied, expected):
            raise TokenError("activation token authentication failed")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TokenError("activation token payload is invalid") from error
        if not isinstance(payload, dict):
            raise TokenError("activation token payload is not an object")
        return payload


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


@dataclass(slots=True)
class PublishedThing:
    thing: Thing
    token: str
    generation: int


class SnapshotRegistry:
    def __init__(self, codec: TokenCodec | None = None) -> None:
        self.codec = codec or TokenCodec()
        self.generations: dict[str, int] = {}
        self.providers: dict[str, dict[str, PublishedThing]] = {}

    def publish(self, provider: str, items: Iterable[Thing]) -> list[dict[str, Any]]:
        generation = self.generations.get(provider, 0) + 1
        self.generations[provider] = generation
        published: dict[str, PublishedThing] = {}
        public: list[dict[str, Any]] = []
        for thing in dedupe_things(items):
            payload = {
                "provider": provider,
                "id": thing.id,
                "generation": generation,
                # The activation body remains opaque to QML and authenticated;
                # keeping it here also makes helper restart tokens invalid.
                "activation": thing.activation,
            }
            token = self.codec.encode(payload)
            row = PublishedThing(thing, token, generation)
            published[thing.id] = row
            public.append(thing.public(token))
        self.providers[provider] = published
        return public

    def decode_reference(self, item_id: str, token: str) -> dict[str, Any]:
        payload = self.codec.decode(token)
        if payload.get("id") != item_id:
            raise TokenError("activation token does not belong to this item")
        provider = payload.get("provider")
        if not isinstance(provider, str) or not provider:
            raise TokenError("activation token has no provider")
        return payload

    def current(self, provider: str, item_id: str) -> PublishedThing | None:
        return self.providers.get(provider, {}).get(item_id)

    def token_is_current(self, payload: dict[str, Any]) -> bool:
        provider = str(payload.get("provider") or "")
        item_id = str(payload.get("id") or "")
        row = self.current(provider, item_id)
        return bool(row and row.generation == payload.get("generation"))

    def all_public(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for provider in sorted(self.providers):
            for published in self.providers[provider].values():
                rows.append(published.thing.public(published.token))
        return rows

    def provider_public(self, provider: str) -> list[dict[str, Any]]:
        return [
            published.thing.public(published.token)
            for published in self.providers.get(provider, {}).values()
        ]


def process_birth(pid: int, proc_root: str = "/proc") -> str:
    """Return Linux's immutable-per-process start tick for reuse-safe ids."""

    try:
        data = Path(proc_root, str(int(pid)), "stat").read_text(encoding="utf-8")
        # comm may contain spaces and parentheses. Everything after the final
        # ')' begins at stat field 3, making starttime field 22 offset 19.
        rest = data[data.rfind(")") + 2 :].split()
        return rest[19]
    except (OSError, ValueError, IndexError):
        return "unknown"
