from __future__ import annotations

import asyncio
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Iterator

from ..atspi_runtime import atspi_cancel_checkpoint
from ..commands import CommandError
from ..model import Thing, process_birth, stable_id
from .base import ProviderResult, ScanContext, normalized_address
from .hyprland import focus_address

try:
    import gi

    gi.require_version("Atspi", "2.0")
    gi.require_version("Gio", "2.0")
    gi.require_version("GLib", "2.0")
    from gi.repository import Atspi, Gio, GLib
except (ImportError, ValueError):  # Covered as an isolated provider warning.
    Atspi = None  # type: ignore[assignment]
    Gio = None  # type: ignore[assignment]
    GLib = None  # type: ignore[assignment]


DOCUMENT_ROLES = (
    frozenset(
        {
            Atspi.Role.DOCUMENT_EMAIL,
            Atspi.Role.DOCUMENT_FRAME,
            Atspi.Role.DOCUMENT_PRESENTATION,
            Atspi.Role.DOCUMENT_SPREADSHEET,
            Atspi.Role.DOCUMENT_TEXT,
            Atspi.Role.DOCUMENT_WEB,
        }
    )
    if Atspi is not None
    else frozenset()
)
BROWSER_CLASS = re.compile(
    r"(?:^|[._-])(?:chromium|google-chrome|chrome|brave(?:-browser)?|microsoft-edge|"
    r"firefox|zen|vivaldi|helium|librewolf)(?=$|[._-])",
    re.IGNORECASE,
)
BROWSER_APP_MODE_CLASS = re.compile(
    r"^(?:chromium|google-chrome|chrome|brave(?:-browser)?|microsoft-edge|firefox|"
    r"zen|vivaldi(?:-stable)?|helium|librewolf)-.+-Default$",
    re.IGNORECASE,
)
BROWSER_APP_MODE_TITLE = re.compile(
    r"^[a-z0-9.-]+(?::[0-9]+)?_/.*$",
    re.IGNORECASE,
)
GHOSTTY_CLASS = re.compile(r"(?:com\.mitchellh\.ghostty|ghostty)", re.IGNORECASE)
REJECTED_STRIP_NAME = re.compile(
    r"(?:dock|tool|sidebar|side panel|developer tools|inspector)",
    re.IGNORECASE,
)
NATIVE_TAB_SETTLE_DELAYS = (0.1, 0.2, 0.4, 0.8)
PREFERRED_TAB_ACTIONS = ("activate", "click", "press", "select", "dodefault")
GTK_ACTION_INTERFACE = "org.gtk.Actions"
GTK_ACTION_APPLICATION_CLASSES = frozenset(
    {"com.github.pintaproject.pinta", "org.gnome.nautilus"}
)
DBUS_INTERFACE = "org.freedesktop.DBus"
DBUS_DESTINATION = "org.freedesktop.DBus"
DBUS_PATH = "/org/freedesktop/DBus"
GTK_ACTION_TIMEOUT_MS = 500
GTK_ACTION_STATE_DELAYS = (0.0, 0.05, 0.1, 0.2, 0.4)
NAUTILUS_WINDOW_PATH = re.compile(r"/org/gnome/Nautilus/window/[1-9][0-9]{0,9}$")
NAUTILUS_WINDOW_NODE = re.compile(r'<node\s+name=["\']([1-9][0-9]{0,9})["\'](?:\s|/|>)')


def clean_text(value: Any) -> str:
    text = str(value or "").replace("\x00", " ")
    return " ".join(text.split()).strip()


def folded(value: Any) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", clean_text(value).lower())
        if not unicodedata.combining(character)
    )


def is_browser_app_mode(client: dict[str, Any]) -> bool:
    classes = [
        clean_text(client.get("class")),
        clean_text(client.get("initialClass")),
    ]
    if not any(BROWSER_CLASS.search(value) for value in classes if value):
        return False
    if any(BROWSER_APP_MODE_CLASS.fullmatch(value) for value in classes if value):
        return True
    initial_title = clean_text(client.get("initialTitle"))
    return bool(initial_title and BROWSER_APP_MODE_TITLE.fullmatch(initial_title))


def safe_call(default: Any, function: Callable[..., Any], *args: Any) -> Any:
    atspi_cancel_checkpoint()
    try:
        result = function(*args)
    except Exception:
        return default
    atspi_cancel_checkpoint()
    return result


def role(accessible: Any) -> Any:
    return safe_call(None, accessible.get_role)


def states(accessible: Any) -> Any:
    return safe_call(None, accessible.get_state_set)


def has_state(accessible: Any, state: Any) -> bool:
    current = states(accessible)
    return bool(current and safe_call(False, current.contains, state))


def children(accessible: Any, limit: int = 10000) -> list[Any]:
    count = int(safe_call(0, accessible.get_child_count) or 0)
    return [
        child
        for index in range(min(count, limit))
        if (child := safe_call(None, accessible.get_child_at_index, index)) is not None
    ]


@dataclass(slots=True)
class Node:
    accessible: Any
    path: tuple[int, ...]
    depth: int
    role_value: Any = None


def walk(root: Any, *, max_nodes: int = 6000, max_depth: int = 24) -> Iterator[Node]:
    if Atspi is None:
        return
    stack: list[Node] = [Node(root, (), 0)]
    visited = 0
    while stack and visited < max_nodes:
        node = stack.pop()
        visited += 1
        node.role_value = role(node.accessible)
        yield node
        if node.depth >= max_depth or has_state(node.accessible, Atspi.StateType.DEFUNCT):
            continue
        # Native controls cannot live inside document content. Do not merely
        # mark those descendants as ineligible: crossing a large web page or
        # spreadsheet can consume the entire walk budget and several seconds
        # of synchronous AT-SPI calls before any native strip is published.
        if node.role_value in DOCUMENT_ROLES:
            continue
        descendants = children(node.accessible)
        for index in range(len(descendants) - 1, -1, -1):
            stack.append(
                Node(
                    descendants[index],
                    node.path + (index,),
                    node.depth + 1,
                )
            )


def action_names(accessible: Any) -> list[str]:
    getter = getattr(accessible, "get_action_iface", None)
    action = safe_call(None, getter) if callable(getter) else None
    if not action:
        return []
    count = int(safe_call(0, action.get_n_actions) or 0)
    return [
        clean_text(safe_call("", action.get_action_name, index)).lower()
        for index in range(count)
    ]


def component_iface(accessible: Any) -> Any:
    getter = getattr(accessible, "get_component_iface", None)
    return safe_call(None, getter) if callable(getter) else None


def preferred_action_index(
    accessible: Any,
    preferred: Iterable[str] = PREFERRED_TAB_ACTIONS,
) -> tuple[Any, int] | None:
    getter = getattr(accessible, "get_action_iface", None)
    action = safe_call(None, getter) if callable(getter) else None
    if not action:
        return None
    names = action_names(accessible)
    for wanted in preferred:
        for index, name in enumerate(names):
            if wanted == name or wanted in name:
                return action, index
    return None


def invoke_accessible_action(
    accessible: Any,
    preferred: Iterable[str] = PREFERRED_TAB_ACTIONS,
) -> bool:
    target = preferred_action_index(accessible, preferred)
    return bool(target and safe_call(False, target[0].do_action, target[1]))


def invoke_accessible(
    accessible: Any,
    preferred: Iterable[str] = PREFERRED_TAB_ACTIONS,
) -> bool:
    if invoke_accessible_action(accessible, preferred):
        return True
    component = component_iface(accessible)
    return bool(component and safe_call(False, component.grab_focus))


def accessible_id(accessible: Any, fallback: str) -> str:
    value = clean_text(safe_call("", accessible.get_accessible_id))
    path = clean_text(getattr(accessible, "path", ""))
    location = path or fallback
    if value:
        # GTK 4/libadwaita exposes the same type-like id (for example
        # ``AdwTab``) for every tab. Pair it with the unique remote object path
        # or structural fallback instead of treating it as a native key alone.
        return value + "@" + location
    return location


@dataclass(slots=True)
class TopLevel:
    application: Any
    accessible: Any
    pid: int
    index: int
    name: str
    client: dict[str, Any]


@dataclass(slots=True)
class NativeTab:
    accessible: Any
    top: TopLevel
    strip_path: tuple[int, ...]
    tab_path: tuple[int, ...]
    index: int
    title: str
    selected: bool
    native_id: str


class GtkActionBus:
    """Capability-test and invoke exact integer GTK tab actions."""

    def __init__(self) -> None:
        if Gio is None or GLib is None:
            raise CommandError("GIO D-Bus bindings are unavailable")
        atspi_cancel_checkpoint()
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        atspi_cancel_checkpoint()
        self.pid_destinations: dict[int, list[str]] = {}

    def _call(
        self,
        destination: str,
        object_path: str,
        interface: str,
        method: str,
        parameters: Any,
    ) -> Any:
        atspi_cancel_checkpoint()
        result = self.connection.call_sync(
            destination,
            object_path,
            interface,
            method,
            parameters,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            GTK_ACTION_TIMEOUT_MS,
            None,
        )
        atspi_cancel_checkpoint()
        return result

    def _connection_pid(self, destination: str) -> int:
        result = self._call(
            DBUS_DESTINATION,
            DBUS_PATH,
            DBUS_INTERFACE,
            "GetConnectionUnixProcessID",
            GLib.Variant("(s)", (destination,)),
        )
        values = result.unpack()
        return int(values[0]) if values else 0

    def _pid_destinations(self, pid: int) -> list[str]:
        if pid in self.pid_destinations:
            return list(self.pid_destinations[pid])
        result = self._call(
            DBUS_DESTINATION,
            DBUS_PATH,
            DBUS_INTERFACE,
            "ListNames",
            None,
        )
        values = result.unpack()
        names = values[0] if values and isinstance(values[0], list) else []
        matches: list[str] = []
        for name in names[:512]:
            value = str(name)
            if not re.fullmatch(r":[0-9]{1,10}\.[0-9]{1,10}", value):
                continue
            try:
                owner_pid = self._connection_pid(value)
            except Exception:
                continue
            if owner_pid == pid:
                matches.append(value)
        self.pid_destinations[pid] = matches
        return list(matches)

    def _describe(
        self,
        destination: str,
        object_path: str,
        action: str,
    ) -> tuple[bool, str, int]:
        result = self._call(
            destination,
            object_path,
            GTK_ACTION_INTERFACE,
            "Describe",
            GLib.Variant("(s)", (action,)),
        )
        values = result.unpack()
        details = values[0] if values and isinstance(values[0], tuple) else ()
        if len(details) != 3:
            return False, "", -1
        enabled, parameter_type, state_values = details
        state = (
            state_values[0]
            if isinstance(state_values, list) and len(state_values) == 1
            else -1
        )
        if not isinstance(state, int) or isinstance(state, bool):
            state = -1
        return bool(enabled), str(parameter_type), int(state)

    def _window_paths(self, destination: str, root: str) -> list[str]:
        result = self._call(
            destination,
            root,
            "org.freedesktop.DBus.Introspectable",
            "Introspect",
            None,
        )
        values = result.unpack()
        xml = str(values[0]) if values else ""
        if not xml or len(xml) > 65536:
            return []
        names = list(dict.fromkeys(NAUTILUS_WINDOW_NODE.findall(xml)))[:64]
        return [root.rstrip("/") + "/" + name for name in names]

    @staticmethod
    def _state_matches_top(tabs: list[NativeTab], state: int, top_name: str) -> bool:
        if state < 0 or state >= len(tabs):
            return False
        title = folded(tabs[state].title)
        current = re.sub(r"\s+-\s+pinta$", "", folded(top_name)).strip()
        return bool(title and current and title == current)

    @staticmethod
    def _routes(
        adapter: str,
        destination: str,
        object_path: str,
        action: str,
        tabs: list[NativeTab],
    ) -> list[dict[str, Any]]:
        return [
            {
                "kind": "gtk-action",
                "adapter": adapter,
                "destination": destination,
                "object_path": object_path,
                "action": action,
                "index": index,
                "count": len(tabs),
            }
            for index in range(len(tabs))
        ]

    def routes(
        self,
        app_class: str,
        pid: int,
        top_name: str,
        tabs: list[NativeTab],
    ) -> list[dict[str, Any]] | None:
        if not tabs or len(tabs) > 256:
            return None
        value = app_class.lower()
        try:
            if value == "com.github.pintaproject.pinta":
                candidates: list[tuple[str, str]] = []
                object_path = "/com/github/PintaProject/Pinta"
                for destination in self._pid_destinations(pid):
                    enabled, signature, state = self._describe(
                        destination, object_path, "active_document"
                    )
                    if (
                        enabled
                        and signature == "i"
                        and self._state_matches_top(tabs, state, top_name)
                    ):
                        candidates.append((destination, object_path))
                if len(candidates) == 1:
                    return self._routes(
                        "pinta",
                        candidates[0][0],
                        candidates[0][1],
                        "active_document",
                        tabs,
                    )
                return None

            if value == "org.gnome.nautilus":
                destination = "org.gnome.Nautilus"
                if self._connection_pid(destination) != pid:
                    return None
                candidates: list[str] = []
                root = "/org/gnome/Nautilus/window"
                for object_path in self._window_paths(destination, root):
                    enabled, signature, _state = self._describe(
                        destination, object_path, "go-to-tab"
                    )
                    # Nautilus exports a constant initial action state rather
                    # than tracking the selected page. A single same-process
                    # window action group is therefore the only unambiguous
                    # route; multiple exported windows fail closed.
                    if enabled and signature == "i":
                        candidates.append(object_path)
                if len(candidates) == 1:
                    return self._routes(
                        "nautilus",
                        destination,
                        candidates[0],
                        "go-to-tab",
                        tabs,
                    )
        except Exception:
            return None
        return None

    @staticmethod
    def _validate_route(
        route: dict[str, Any],
    ) -> tuple[str, str, str, str, int, int]:
        adapter = str(route.get("adapter") or "")
        destination = str(route.get("destination") or "")
        object_path = str(route.get("object_path") or "")
        action = str(route.get("action") or "")
        index = route.get("index")
        count = route.get("count")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not isinstance(count, int)
            or isinstance(count, bool)
        ):
            raise CommandError("native application tab index is invalid")
        if (
            index < 0
            or count <= 0
            or count > 256
            or index >= count
        ):
            raise CommandError("native application tab index is invalid")
        if adapter == "pinta":
            if (
                not re.fullmatch(r":[0-9]{1,10}\.[0-9]{1,10}", destination)
                or object_path != "/com/github/PintaProject/Pinta"
                or action != "active_document"
            ):
                raise CommandError("Pinta tab route is invalid")
        elif adapter == "nautilus":
            if (
                destination != "org.gnome.Nautilus"
                or not NAUTILUS_WINDOW_PATH.fullmatch(object_path)
                or action != "go-to-tab"
            ):
                raise CommandError("Nautilus tab route is invalid")
        else:
            raise CommandError("native application tab route is unsupported")
        return adapter, destination, object_path, action, index, count

    def activate(self, route: dict[str, Any], pid: int) -> None:
        adapter, destination, object_path, action, index, count = self._validate_route(
            route
        )
        try:
            if self._connection_pid(destination) != pid:
                raise CommandError("native application action owner changed")
            enabled, signature, state = self._describe(destination, object_path, action)
            if not enabled or signature != "i":
                raise CommandError("native application tab action changed")
            if adapter == "nautilus":
                self._call(
                    destination,
                    object_path,
                    GTK_ACTION_INTERFACE,
                    "Activate",
                    GLib.Variant(
                        "(sava{sv})",
                        (action, [GLib.Variant("i", index)], {}),
                    ),
                )
                return
            if state < 0 or state >= count:
                raise CommandError("native application tab action changed")
            if state == index:
                return
            self._call(
                destination,
                object_path,
                GTK_ACTION_INTERFACE,
                "Activate",
                GLib.Variant(
                    "(sava{sv})",
                    (action, [GLib.Variant("i", index)], {}),
                ),
            )
            for delay in GTK_ACTION_STATE_DELAYS:
                atspi_cancel_checkpoint()
                if delay:
                    time.sleep(delay)
                atspi_cancel_checkpoint()
                enabled, signature, state = self._describe(
                    destination,
                    object_path,
                    action,
                )
                if enabled and signature == "i" and state == index:
                    return
        except CommandError:
            raise
        except Exception as error:
            raise CommandError("native application tab action failed") from error
        raise CommandError("native application did not select the requested tab")


class AtspiTree:
    def __init__(self) -> None:
        if Atspi is None:
            raise CommandError("PyGObject AT-SPI bindings are unavailable")
        result = safe_call(-1, Atspi.init)
        # libatspi may return a positive value when the process-local singleton
        # is already initialized; only a negative value fails.
        if isinstance(result, int) and result < 0:
            raise CommandError("AT-SPI initialization failed")

    def applications(self) -> list[Any]:
        desktop = safe_call(None, Atspi.get_desktop, 0)
        return children(desktop) if desktop else []

    def top_levels(self, context: ScanContext, *, include_ghostty: bool = False) -> list[TopLevel]:
        out: list[TopLevel] = []
        for application in self.applications():
            pid = int(safe_call(0, application.get_process_id) or 0)
            candidates = context.matching_clients_for_pid(pid)
            if not candidates:
                # Some toolkits expose an app-side helper PID. Match only when
                # it has exactly one managed ancestor, never by a loose title.
                ancestors = context.processes.ancestors(pid)
                managed_pids = {
                    int(client.get("pid") or 0) for client in context.hypr_clients
                }
                ancestor = next(
                    (process.pid for process in ancestors if process.pid in managed_pids),
                    None,
                )
                candidates = context.matching_clients_for_pid(ancestor or 0)
            if not candidates:
                continue
            matched_tops: list[tuple[int, Any, str, dict[str, Any], str]] = []
            for top_index, top in enumerate(children(application)):
                top_name = clean_text(safe_call("", top.get_name))
                matched = self._match_client(top_name, candidates)
                if not matched:
                    continue
                address = normalized_address(matched.get("address"))
                if address:
                    matched_tops.append((top_index, top, top_name, matched, address))

            address_counts: dict[str, int] = {}
            for _index, _top, _name, _client, address in matched_tops:
                address_counts[address] = address_counts.get(address, 0) + 1
            for top_index, top, top_name, matched, address in matched_tops:
                # Unmapped records participate in matching only. If the stale
                # top resolves to one, reject it rather than removing that
                # evidence and rebinding it to a live same-PID client. Multiple
                # tops claiming one address are equally ambiguous and all fail
                # closed instead of accepting whichever the toolkit lists first.
                if matched.get("mapped") is False or address_counts[address] != 1:
                    continue
                if not include_ghostty and GHOSTTY_CLASS.search(
                    str(matched.get("class") or "")
                ):
                    continue
                out.append(TopLevel(application, top, pid, top_index, top_name, matched))
        return out

    @staticmethod
    def _match_client(
        top_name: str,
        clients: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        wanted = folded(top_name)
        exact = [
            client
            for client in clients
            if folded(client.get("title")) == wanted and wanted
        ]
        if len(exact) == 1:
            return exact[0]
        contained = [
            client
            for client in clients
            if wanted
            and (
                wanted in folded(client.get("title"))
                or folded(client.get("title")) in wanted
            )
        ]
        return contained[0] if len(contained) == 1 else None

    @staticmethod
    def _tab_children(tab_list: Any) -> list[tuple[tuple[int, ...], Any]]:
        """Return direct tabs plus the one transparent wrapper used by GTK 4."""

        tabs: list[tuple[tuple[int, ...], Any]] = []
        for index, child in enumerate(children(tab_list)):
            if role(child) == Atspi.Role.PAGE_TAB:
                tabs.append(((index,), child))
                continue
            if role(child) != Atspi.Role.GROUPING:
                continue
            wrapped = children(child)
            if len(wrapped) == 1 and role(wrapped[0]) == Atspi.Role.PAGE_TAB:
                tabs.append(((index, 0), wrapped[0]))
        return tabs

    @classmethod
    def _actionable_tab_children(
        cls, tab_list: Any
    ) -> list[tuple[tuple[int, ...], Any]]:
        tabs = cls._tab_children(tab_list)
        if not tabs:
            return []
        actionable = sum(
            1
            for _path, tab in tabs
            if action_names(tab) or component_iface(tab) is not None
        )
        return tabs if actionable == len(tabs) else []

    @staticmethod
    def _native_tabs_from_strip(
        top: TopLevel,
        strip_path: tuple[int, ...],
        tabs: list[tuple[tuple[int, ...], Any]],
    ) -> list[NativeTab]:
        result: list[NativeTab] = []
        occurrences: dict[str, int] = {}
        for ordinal, (relative_path, accessible) in enumerate(tabs):
            title = clean_text(safe_call("", accessible.get_name)) or "Untitled tab"
            key = folded(title)
            occurrences[key] = occurrences.get(key, 0) + 1
            occurrence = occurrences[key]
            tab_path = strip_path + relative_path
            native = accessible_id(accessible, ".".join(map(str, tab_path)))
            result.append(
                NativeTab(
                    accessible=accessible,
                    top=top,
                    strip_path=strip_path,
                    tab_path=tab_path,
                    index=ordinal,
                    title=title,
                    selected=has_state(accessible, Atspi.StateType.SELECTED),
                    native_id=native + f":{occurrence}",
                )
            )
        return result

    def native_tabs_at_path(
        self, top: TopLevel, strip_path: tuple[int, ...]
    ) -> list[NativeTab]:
        """Revalidate one previously discovered strip without a broad walk."""

        if Atspi is None:
            return []
        current = top.accessible
        for index in strip_path:
            if (
                not isinstance(index, int)
                or index < 0
                or has_state(current, Atspi.StateType.DEFUNCT)
                or role(current) in DOCUMENT_ROLES
            ):
                return []
            current = safe_call(None, current.get_child_at_index, index)
            if current is None:
                return []
        if (
            has_state(current, Atspi.StateType.DEFUNCT)
            or role(current) != Atspi.Role.PAGE_TAB_LIST
        ):
            return []
        strip_name = clean_text(safe_call("", current.get_name))
        if REJECTED_STRIP_NAME.search(strip_name):
            return []
        tabs = self._actionable_tab_children(current)
        return self._native_tabs_from_strip(top, strip_path, tabs) if tabs else []

    def native_tabs(self, top: TopLevel, *, browser: bool) -> list[NativeTab]:
        candidates: list[tuple[Node, list[tuple[tuple[int, ...], Any]]]] = []
        for node in walk(top.accessible):
            if node.role_value != Atspi.Role.PAGE_TAB_LIST:
                continue
            strip_name = clean_text(safe_call("", node.accessible.get_name))
            if REJECTED_STRIP_NAME.search(strip_name):
                continue
            tabs = self._actionable_tab_children(node.accessible)
            if not tabs:
                continue
            candidates.append((node, tabs))
        if not candidates:
            return []

        # A browser's primary strip has the most real page tabs. Depth is only
        # the tie-breaker, preserving vertical/custom tab-strip layouts.
        candidates.sort(
            key=lambda candidate: (
                -len(candidate[1]),
                candidate[0].depth,
                candidate[0].path,
            )
        )
        node, tabs = candidates[0]
        return self._native_tabs_from_strip(top, node.path, tabs)


class AtspiProvider:
    name = "atspi"

    def __init__(self) -> None:
        self.objects: dict[str, NativeTab] = {}
        self.settled_browser_clients: set[tuple[str, int, str]] = set()
        self.settled_application_clients: set[tuple[str, int, str]] = set()
        self.published_priority_clients: set[tuple[str, int, str]] | None = None
        self.gtk_actions: GtkActionBus | None = None

    def _gtk_action_routes(
        self,
        app_class: str,
        pid: int,
        top_name: str,
        tabs: list[NativeTab],
    ) -> list[dict[str, Any]] | None:
        if self.gtk_actions is None:
            try:
                self.gtk_actions = GtkActionBus()
            except Exception:
                return None
        return self.gtk_actions.routes(app_class, pid, top_name, tabs)

    async def scan(self, context: ScanContext) -> ProviderResult:
        # Discovery dispatches this entire coroutine to the single AT-SPI
        # executor. Its asyncio sleeps are cancellable there, while the helper's
        # protocol loop and unrelated providers remain independently runnable.
        expected_browsers = self._browser_clients(context)
        expected_applications = self._application_clients(context)
        browser_identities = set(expected_browsers)
        application_identities = set(expected_applications)
        priority_identities = browser_identities | application_identities
        settled_browsers = self.settled_browser_clients & browser_identities
        settled_applications = (
            self.settled_application_clients & application_identities
        )

        best = self._collect(context, priority=True)
        await asyncio.sleep(0)
        settled_browsers = {
            identity
            for identity in settled_browsers
            if expected_browsers[identity] in best[2]
        }
        unsettled_browsers = browser_identities - settled_browsers
        first_seen_applications = application_identities - settled_applications
        settle_targets = {
            **{
                identity: expected_browsers[identity]
                for identity in unsettled_browsers
            },
            **{
                identity: expected_applications[identity]
                for identity in first_seen_applications
            },
        }
        settle_attempted = False
        # Settle only while no actionable priority row is ready. Never hold an
        # available row back for another empty client; that client still gets
        # an ordinary first pass on every later poll.
        if settle_targets and not best[2]:
            settle_attempted = True
            expected_addresses = set(settle_targets.values())
            best_coverage = len(best[2] & expected_addresses)
            for delay in NATIVE_TAB_SETTLE_DELAYS:
                if best_coverage:
                    break
                # Chromium and current GTK applications can publish their
                # top-level frame before native tabs and exact action routes
                # arrive on AT-SPI/D-Bus. Yield during the bounded settle pass
                # so newer protocol scans can cancel this one and independent
                # non-AT-SPI providers can keep making progress.
                await asyncio.sleep(delay)
                candidate = self._collect(context, priority=True)
                await asyncio.sleep(0)
                coverage = len(candidate[2] & expected_addresses)
                if coverage > best_coverage or (
                    coverage == best_coverage and len(candidate[0]) > len(best[0])
                ):
                    best = candidate
                    best_coverage = coverage

        covered_addresses = best[2]
        settled_browsers.update(
            identity
            for identity in unsettled_browsers
            if expected_browsers[identity] in covered_addresses
        )
        settled_applications.update(
            identity
            for identity in first_seen_applications
            if expected_applications[identity] in covered_addresses
        )
        if settle_attempted:
            # A browser always has a native tab, so an uncovered browser stays
            # eligible on later polls. Pinta and Nautilus may legitimately
            # expose no tab yet; settle each new window only once and let later
            # ordinary polls discover tabs without delaying every generation.
            settled_applications.update(first_seen_applications)

        # Publish a fast generation before traversing arbitrary toolkit trees.
        # Some otherwise unrelated applications take several seconds to answer
        # synchronous AT-SPI calls. They must not hold back a newly started
        # provider or a newly opened browser, Pinta, or Nautilus window. Once
        # the current priority-client set has been published, probe generic
        # applications on a later ordinary poll and merge those rows.
        if self.published_priority_clients == priority_identities:
            generic_items, generic_objects, generic_coverage = self._collect(
                context, priority=False
            )
            best = (
                best[0] + generic_items,
                {**best[1], **generic_objects},
                best[2] | generic_coverage,
            )

        items, objects, _covered_addresses = best
        self.settled_browser_clients = settled_browsers
        self.settled_application_clients = settled_applications
        self.published_priority_clients = priority_identities
        self.objects = objects
        return ProviderResult(self.name, items)

    @staticmethod
    def _browser_clients(context: ScanContext) -> dict[tuple[str, int, str], str]:
        out: dict[tuple[str, int, str], str] = {}
        births: dict[int, str] = {}
        for client in context.hypr_clients:
            app_class = str(client.get("class") or client.get("initialClass") or "")
            if not BROWSER_CLASS.search(app_class) or is_browser_app_mode(client):
                continue
            address = normalized_address(client.get("address"))
            pid = int(client.get("pid") or 0)
            if not address or pid <= 0:
                continue
            if pid not in births:
                births[pid] = process_birth(pid)
            out[(address, pid, births[pid])] = address
        return out

    @staticmethod
    def _application_clients(context: ScanContext) -> dict[tuple[str, int, str], str]:
        out: dict[tuple[str, int, str], str] = {}
        births: dict[int, str] = {}
        for client in context.hypr_clients:
            app_class = str(
                client.get("class") or client.get("initialClass") or ""
            ).lower()
            if app_class not in GTK_ACTION_APPLICATION_CLASSES:
                continue
            address = normalized_address(client.get("address"))
            pid = int(client.get("pid") or 0)
            if not address or pid <= 0:
                continue
            if pid not in births:
                births[pid] = process_birth(pid)
            out[(address, pid, births[pid])] = address
        return out

    def _collect(
        self, context: ScanContext, *, priority: bool
    ) -> tuple[list[Thing], dict[str, NativeTab], set[str]]:
        tree = AtspiTree()
        objects: dict[str, NativeTab] = {}
        items: list[Thing] = []
        covered_addresses: set[str] = set()
        top_levels = tree.top_levels(context)
        candidates: list[tuple[TopLevel, str, bool, int, list[NativeTab], bool]] = []
        fallback_top_counts: dict[tuple[str, int], int] = {}
        for top in top_levels:
            app_class = str(top.client.get("class") or top.client.get("initialClass") or "")
            # Browser app-mode windows are already actionable as exact managed
            # windows. Their synthetic one-tab strip adds no distinct target,
            # and must not leak into either browser or generic application tabs.
            if is_browser_app_mode(top.client):
                continue
            is_browser = bool(BROWSER_CLASS.search(app_class))
            is_priority = (
                is_browser or app_class.lower() in GTK_ACTION_APPLICATION_CLASSES
            )
            if priority != is_priority:
                continue
            tabs = tree.native_tabs(top, browser=is_browser)
            if not tabs:
                continue
            pid = int(top.client.get("pid") or top.pid)
            has_atspi_route = all(
                preferred_action_index(tab.accessible) is not None for tab in tabs
            )
            if is_browser and not has_atspi_route:
                continue
            candidates.append((top, app_class, is_browser, pid, tabs, has_atspi_route))
            if not is_browser and not has_atspi_route:
                key = (app_class.lower(), pid)
                fallback_top_counts[key] = fallback_top_counts.get(key, 0) + 1

        for top, app_class, is_browser, pid, tabs, has_atspi_route in candidates:
            address = normalized_address(top.client.get("address"))
            parent = self._window_parent_id(context, address)
            # Native tabs are subordinate to an exact managed window. A stale
            # toolkit application/tree can outlive that window, but it must not
            # remain independently actionable or visible in the panel.
            if not parent:
                continue
            if has_atspi_route:
                tab_routes = [{"kind": "atspi-action"} for _tab in tabs]
            else:
                if fallback_top_counts.get((app_class.lower(), pid)) != 1:
                    continue
                tab_routes = self._gtk_action_routes(app_class, pid, top.name, tabs)
                if not tab_routes or len(tab_routes) != len(tabs):
                    continue
            covered_addresses.add(address)
            birth = process_birth(pid)
            active_window = int(top.client.get("focusHistoryID") or 0) == 0
            kind = "browser-tab" if is_browser else "app-tab"
            provider_name = self._provider_name(app_class, is_browser)
            for tab, tab_route in zip(tabs, tab_routes):
                item_id = stable_id(self.name, pid, birth, address, tab.native_id)
                objects[item_id] = tab
                items.append(
                    Thing(
                        id=item_id,
                        kind=kind,
                        provider=provider_name,
                        title=tab.title,
                        context=f"{top.name or app_class} · native tab",
                        search_terms=[app_class, top.name],
                        parent_id=parent,
                        badges=["Tab", "Title only" if is_browser else "Native"],
                        active=active_window and tab.selected,
                        recency=3500 if active_window and tab.selected else 0,
                        activation={
                            "address": address,
                            "pid": pid,
                            "birth": birth,
                            "native_id": tab.native_id,
                            "tab_route": tab_route,
                        },
                    )
                )
        return items, objects, covered_addresses

    @staticmethod
    def _provider_name(app_class: str, browser: bool) -> str:
        value = app_class.lower()
        if not browser:
            identity = clean_text(app_class)
            if identity.lower().endswith(".desktop"):
                identity = identity[:-8]
            return identity.rsplit(".", 1)[-1] or "Application"
        for needle, label in (
            ("librewolf", "LibreWolf"),
            ("firefox", "Firefox"),
            ("zen", "Zen"),
            ("brave", "Brave"),
            ("edge", "Edge"),
            ("vivaldi", "Vivaldi"),
            ("helium", "Helium"),
            ("chrome", "Chrome"),
            ("chromium", "Chromium"),
        ):
            if needle in value:
                return label
        return "Browser"

    @staticmethod
    def _window_parent_id(context: ScanContext, address: str) -> str:
        for client in context.provider_metadata.get("hyprland", {}).get("clients", []):
            if normalized_address(client.get("address")) == address:
                return str(client.get("item_id") or "")
        return ""

    @staticmethod
    def _validated_gtk_tab(
        tab: NativeTab,
        native_id: str,
        route: dict[str, Any],
    ) -> NativeTab:
        index = route.get("index")
        count = route.get("count")
        if (
            not isinstance(index, int)
            or isinstance(index, bool)
            or not isinstance(count, int)
            or isinstance(count, bool)
        ):
            raise CommandError("native application tab index is invalid")
        current_tabs = AtspiTree.__new__(AtspiTree).native_tabs_at_path(
            tab.top, tab.strip_path
        )
        if (
            count <= 0
            or index < 0
            or index >= count
            or len(current_tabs) != count
            or index >= len(current_tabs)
            or current_tabs[index].native_id != native_id
        ):
            raise CommandError("native application tab no longer matches its scan identity")
        return current_tabs[index]

    async def activate(self, activation: dict[str, Any], context: ScanContext) -> None:
        item_id = str(activation.get("item_id") or "")
        tab = self.objects.get(item_id)
        if not tab:
            # Discovery stores item_id only in the registry activation wrapper;
            # callers normally inject it before dispatch. Fall back to the
            # stable native fingerprint for a just-refreshed provider.
            native_id = str(activation.get("native_id") or "")
            tab = next(
                (value for value in self.objects.values() if value.native_id == native_id),
                None,
            )
        if not tab or has_state(tab.accessible, Atspi.StateType.DEFUNCT):
            raise CommandError("native tab is no longer available")
        native_id = str(activation.get("native_id") or "")
        if not native_id or tab.native_id != native_id:
            raise CommandError("native tab no longer matches its scan identity")
        pid = int(activation.get("pid") or 0)
        if process_birth(pid) != str(activation.get("birth")):
            raise CommandError("native tab process was replaced")
        address = str(activation.get("address") or "")
        client = context.client_by_address(address)
        if not client or int(client.get("pid") or 0) != pid:
            raise CommandError("native tab window is no longer managed")
        tab_route = activation.get("tab_route")
        route = dict(tab_route) if isinstance(tab_route, dict) else {}
        route_kind = str(route.get("kind") or "")
        if route_kind == "atspi-action":
            if not invoke_accessible_action(tab.accessible):
                raise CommandError("native tab activation action failed")
        elif route_kind == "gtk-action":
            if self.gtk_actions is None:
                raise CommandError("native application tab action is unavailable")
            self._validated_gtk_tab(tab, native_id, route)
            self.gtk_actions.activate(route, pid)
            self._validated_gtk_tab(tab, native_id, route)
        else:
            raise CommandError("native tab activation route is invalid")
        await focus_address(context, address)
