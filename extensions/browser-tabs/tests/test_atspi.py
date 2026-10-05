from __future__ import annotations

import asyncio
import threading
import unittest
from unittest.mock import AsyncMock, patch

from everything.atspi_runtime import AtspiExecutor
from everything.commands import CommandError, CommandRunner
from everything.model import Thing
from everything.processes import ProcTable
from everything.providers.atspi import (
    Atspi,
    AtspiProvider,
    AtspiTree,
    BROWSER_CLASS,
    GtkActionBus,
    NativeTab,
    TopLevel,
    is_browser_app_mode,
    invoke_accessible,
)
from everything.providers.base import ScanContext


class FakeStateSet:
    def __init__(self, selected: bool = False) -> None:
        self.selected = selected

    def contains(self, value) -> bool:
        return bool(Atspi and value == Atspi.StateType.SELECTED and self.selected)


class FakeAction:
    def __init__(self, names: tuple[str, ...] = ("activate",)) -> None:
        self.names = names
        self.invoked: list[int] = []

    def get_n_actions(self) -> int:
        return len(self.names)

    def get_action_name(self, index: int) -> str:
        return self.names[index]

    def do_action(self, index: int) -> bool:
        self.invoked.append(index)
        return True


class FakeAccessible:
    def __init__(
        self,
        role_value,
        name: str,
        *children,
        selected: bool = False,
        actionable: bool = False,
        component: object | None = None,
        accessible_id: str = "",
    ) -> None:
        self.role_value = role_value
        self.name = name
        self.children = list(children)
        self.state = FakeStateSet(selected)
        self.action = FakeAction() if actionable else None
        self.component = component
        self.accessible_id = accessible_id
        self.child_count_reads = 0

    def get_role(self):
        return self.role_value

    def get_name(self) -> str:
        return self.name

    def get_description(self) -> str:
        return ""

    def get_child_count(self) -> int:
        self.child_count_reads += 1
        return len(self.children)

    def get_child_at_index(self, index: int):
        return self.children[index]

    def get_state_set(self):
        return self.state

    def get_action_iface(self):
        return self.action

    def get_component_iface(self):
        return self.component

    def get_accessible_id(self) -> str:
        return self.accessible_id


@unittest.skipIf(Atspi is None, "PyGObject AT-SPI is unavailable")
class NativeTabTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def tab(name: str, identifier: str, selected: bool = False) -> FakeAccessible:
        return FakeAccessible(
            Atspi.Role.PAGE_TAB,
            name,
            selected=selected,
            actionable=True,
            accessible_id=identifier,
        )

    @staticmethod
    def component_tab(name: str, identifier: str, selected: bool = False) -> FakeAccessible:
        return FakeAccessible(
            Atspi.Role.PAGE_TAB,
            name,
            selected=selected,
            component=object(),
            accessible_id=identifier,
        )

    def test_document_and_tool_tabs_are_rejected(self) -> None:
        authored = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Web page tabs",
            self.tab("ARIA one", "aria-1"),
            self.tab("ARIA two", "aria-2"),
        )
        document = FakeAccessible(Atspi.Role.DOCUMENT_WEB, "Page", authored)
        tools = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Developer Tools",
            self.tab("Elements", "tool-1"),
        )
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            self.tab("First", "native-1", selected=True),
            self.tab("Second", "native-2"),
        )
        root = FakeAccessible(Atspi.Role.FRAME, "Browser", document, tools, native)
        top = TopLevel(None, root, 10, 0, "Browser", {"address": "0xabc"})
        tree = AtspiTree.__new__(AtspiTree)

        tabs = tree.native_tabs(top, browser=True)

        self.assertEqual([tab.title for tab in tabs], ["First", "Second"])
        self.assertTrue(tabs[0].selected)
        self.assertEqual(document.child_count_reads, 0)
        self.assertEqual(tree.native_tabs_at_path(top, (0, 0)), [])

    def test_deep_group_wrapped_native_application_tabs_are_accepted(self) -> None:
        first = self.tab("Home", "native-1", selected=True)
        second = self.tab("Downloads", "native-2")
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            FakeAccessible(Atspi.Role.GROUPING, "", first),
            FakeAccessible(Atspi.Role.BUTTON, "New tab", actionable=True),
            FakeAccessible(Atspi.Role.GROUPING, "", second),
        )
        nested = native
        for _index in range(12):
            nested = FakeAccessible(Atspi.Role.PANEL, "", nested)
        root = FakeAccessible(Atspi.Role.FRAME, "Application", nested)
        top = TopLevel(None, root, 10, 0, "Application", {"address": "0xabc"})
        tree = AtspiTree.__new__(AtspiTree)

        tabs = tree.native_tabs(top, browser=False)

        self.assertEqual([tab.title for tab in tabs], ["Home", "Downloads"])
        self.assertEqual([tab.index for tab in tabs], [0, 1])
        self.assertEqual(tabs[0].tab_path[-2:], (0, 0))
        self.assertEqual(tabs[1].tab_path[-2:], (2, 0))
        self.assertTrue(tabs[0].selected)

    def test_repeated_toolkit_accessible_ids_use_their_structural_identity(self) -> None:
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            self.tab("First", "AdwTab"),
            self.tab("Second", "AdwTab"),
        )
        root = FakeAccessible(Atspi.Role.FRAME, "Application", native)
        top = TopLevel(None, root, 10, 0, "Application", {"address": "0xabc"})
        tree = AtspiTree.__new__(AtspiTree)

        tabs = tree.native_tabs(top, browser=False)

        self.assertEqual(len({tab.native_id for tab in tabs}), 2)
        self.assertTrue(all(tab.native_id.startswith("AdwTab@") for tab in tabs))

    def test_current_browser_families_are_recognized(self) -> None:
        classes = (
            "chromium",
            "google-chrome",
            "Brave-browser-beta",
            "microsoft-edge",
            "firefox",
            "zen-alpha",
            "vivaldi-stable",
            "helium",
            "librewolf",
        )
        self.assertTrue(all(BROWSER_CLASS.search(value) for value in classes))
        self.assertFalse(
            any(BROWSER_CLASS.search(value) for value in ("Citizen", "ledger", "frozen-app"))
        )

    def test_browser_app_mode_is_distinct_from_normal_and_private_windows(self) -> None:
        app_mode_clients = (
            {
                "class": "chrome-github.com__-Default",
                "initialClass": "chrome-github.com__-Default",
                "initialTitle": "github.com_/",
            },
            {
                "class": "chromium-app.example.test__dashboard-Default",
                "initialTitle": "app.example.test_/dashboard",
            },
            {
                "class": "com.google.Chrome",
                "initialTitle": "mail.example.test_/inbox",
            },
        )
        normal_clients = (
            {"class": "chromium", "initialTitle": "New tab - Chromium"},
            {"class": "google-chrome", "initialTitle": "New Incognito Tab - Google Chrome"},
            {"class": "firefox", "initialTitle": "Mozilla Firefox Private Browsing"},
        )

        self.assertTrue(all(is_browser_app_mode(client) for client in app_mode_clients))
        self.assertFalse(any(is_browser_app_mode(client) for client in normal_clients))

    async def test_provider_scan_runs_on_the_dedicated_atspi_owner_thread(self) -> None:
        protocol_thread = threading.get_ident()
        observed: list[int] = []

        class RecordingTree:
            def __init__(self):
                observed.append(threading.get_ident())

            def top_levels(self, _context):
                observed.append(threading.get_ident())
                return []

        context = ScanContext(CommandRunner(), ProcTable({}))
        executor = AtspiExecutor()
        try:
            with patch("everything.providers.atspi.AtspiTree", RecordingTree):
                result = await executor.run(lambda: AtspiProvider().scan(context))
        finally:
            await executor.close()

        self.assertEqual(result.items, [])
        self.assertNotEqual(executor.thread_id, protocol_thread)
        self.assertEqual(observed, [executor.thread_id, executor.thread_id])

    def test_unmapped_same_pid_client_is_matching_only_evidence(self) -> None:
        live = {
            "address": "0xlive",
            "pid": 42,
            "class": "org.example.Editor",
            "title": "Live document",
            "mapped": True,
        }
        closed = {
            "address": "0xclosed",
            "pid": 42,
            "class": "org.example.Editor",
            "title": "Closed document",
            "mapped": False,
        }
        live_top = FakeAccessible(Atspi.Role.FRAME, "Live document")
        closed_top = FakeAccessible(Atspi.Role.FRAME, "Closed document")

        class Application(FakeAccessible):
            def get_process_id(self):
                return 42

        application = Application(
            Atspi.Role.APPLICATION,
            "Editor",
            closed_top,
            live_top,
        )
        tree = AtspiTree.__new__(AtspiTree)
        tree.applications = lambda: [application]  # type: ignore[method-assign]
        context = ScanContext(
            CommandRunner(),
            ProcTable({}),
            hypr_clients=[live],
            hypr_matching_clients=[live, closed],
        )

        tops = tree.top_levels(context)

        self.assertEqual([top.name for top in tops], ["Live document"])
        self.assertEqual(tops[0].client["address"], "0xlive")
        self.assertIsNone(AtspiTree._match_client("Unrelated", [live]))

        duplicate_application = Application(
            Atspi.Role.APPLICATION,
            "Editor",
            FakeAccessible(Atspi.Role.FRAME, "Live document"),
            FakeAccessible(Atspi.Role.FRAME, "Live document"),
        )
        tree.applications = lambda: [duplicate_application]  # type: ignore[method-assign]
        context.hypr_matching_clients = [live]
        self.assertEqual(tree.top_levels(context), [])

    async def test_cancelled_settle_scan_does_not_publish_partial_state(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "chromium",
            "title": "Loading - Chromium",
        }
        started = asyncio.Event()

        class UncoveredTree:
            def top_levels(self, _context):
                started.set()
                return []

        context = ScanContext(
            CommandRunner(),
            ProcTable({}),
            hypr_clients=[client],
        )
        provider = AtspiProvider()
        old_objects = {"old": object()}
        old_settled = {("0xold", 7, "old-birth")}
        old_priority = {("0xold", 7, "old-birth")}
        provider.objects = old_objects  # type: ignore[assignment]
        provider.settled_browser_clients = old_settled
        provider.published_priority_clients = old_priority

        with patch("everything.providers.atspi.AtspiTree", UncoveredTree), patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (60,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            task = asyncio.create_task(provider.scan(context))
            await started.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task

        self.assertIs(provider.objects, old_objects)
        self.assertIs(provider.settled_browser_clients, old_settled)
        self.assertIs(provider.published_priority_clients, old_priority)

    def test_chromium_default_action_activates_a_tab(self) -> None:
        tab = FakeAccessible(
            Atspi.Role.PAGE_TAB,
            "Native tab",
            actionable=True,
        )
        tab.action = FakeAction(("dodefault", "showcontextmenu"))

        self.assertTrue(invoke_accessible(tab))
        self.assertEqual(tab.action.invoked, [0])

    def test_component_only_native_tab_activates_through_focus(self) -> None:
        class FakeComponent:
            focused = False

            def grab_focus(self):
                self.focused = True
                return True

        component = FakeComponent()
        tab = FakeAccessible(Atspi.Role.PAGE_TAB, "Native tab")
        tab.get_component_iface = lambda: component  # type: ignore[method-assign]

        self.assertTrue(invoke_accessible(tab))
        self.assertTrue(component.focused)

    def test_pinta_routes_use_direct_atspi_indexes_for_matching_action(self) -> None:
        top = TopLevel(None, object(), 42, 0, "Second - Pinta", {})
        tabs = [
            NativeTab(object(), top, (0,), (0, index), index, title, False, f"tab-{index}")
            for index, title in enumerate(("First", "Second"))
        ]
        bus = GtkActionBus.__new__(GtkActionBus)
        bus._pid_destinations = lambda pid: [":1.7"]  # type: ignore[method-assign]
        bus._describe = lambda *_args: (True, "i", 1)  # type: ignore[method-assign]

        routes = bus.routes(
            "com.github.PintaProject.Pinta",
            42,
            "Second - Pinta",
            tabs,
        )

        self.assertIsNotNone(routes)
        assert routes is not None
        self.assertEqual(routes[0]["adapter"], "pinta")
        self.assertEqual(routes[0]["destination"], ":1.7")
        self.assertEqual([route["index"] for route in routes], [0, 1])

    def test_pinta_routes_reject_a_prefix_only_state_match(self) -> None:
        top = TopLevel(None, object(), 42, 0, "Second draft - Pinta", {})
        tabs = [
            NativeTab(object(), top, (0,), (0, index), index, title, False, f"tab-{index}")
            for index, title in enumerate(("Second", "Second draft"))
        ]
        bus = GtkActionBus.__new__(GtkActionBus)
        bus._pid_destinations = lambda pid: [":1.7"]  # type: ignore[method-assign]
        bus._describe = lambda *_args: (True, "i", 0)  # type: ignore[method-assign]

        self.assertIsNone(
            bus.routes("com.github.PintaProject.Pinta", 42, top.name, tabs)
        )

    def test_nautilus_routes_fail_closed_with_multiple_window_action_groups(self) -> None:
        top = TopLevel(None, object(), 42, 0, "Home", {})
        tabs = [NativeTab(object(), top, (0,), (0, 0), 0, "Home", False, "tab-0")]
        bus = GtkActionBus.__new__(GtkActionBus)
        bus._connection_pid = lambda _destination: 42  # type: ignore[method-assign]
        bus._window_paths = lambda *_args: [  # type: ignore[method-assign]
            "/org/gnome/Nautilus/window/1",
            "/org/gnome/Nautilus/window/2",
        ]
        bus._describe = lambda *_args: (True, "i", 0)  # type: ignore[method-assign]

        routes = bus.routes("org.gnome.Nautilus", 42, "Home", tabs)

        self.assertIsNone(routes)

    def test_pinta_action_changes_and_verifies_exact_integer_state(self) -> None:
        bus = GtkActionBus.__new__(GtkActionBus)
        states = iter(((True, "i", 0), (True, "i", 1)))
        calls = []
        bus._connection_pid = lambda _destination: 42  # type: ignore[method-assign]
        bus._describe = lambda *_args: next(states)  # type: ignore[method-assign]
        bus._call = lambda *args: calls.append(args)  # type: ignore[method-assign]
        route = {
            "adapter": "pinta",
            "destination": ":1.7",
            "object_path": "/com/github/PintaProject/Pinta",
            "action": "active_document",
            "index": 1,
            "count": 2,
        }

        with patch("everything.providers.atspi.GTK_ACTION_STATE_DELAYS", (0,)):
            bus.activate(route, 42)

        self.assertEqual(calls[0][3], "Activate")
        self.assertEqual(calls[0][4].unpack(), ("active_document", [1], {}))

    def test_nautilus_action_activates_exact_integer_parameter(self) -> None:
        bus = GtkActionBus.__new__(GtkActionBus)
        calls = []
        bus._connection_pid = lambda _destination: 42  # type: ignore[method-assign]
        bus._describe = lambda *_args: (True, "i", 0)  # type: ignore[method-assign]
        bus._call = lambda *args: calls.append(args)  # type: ignore[method-assign]
        route = {
            "adapter": "nautilus",
            "destination": "org.gnome.Nautilus",
            "object_path": "/org/gnome/Nautilus/window/1",
            "action": "go-to-tab",
            "index": 1,
            "count": 2,
        }

        bus.activate(route, 42)

        self.assertEqual(calls[0][3], "Activate")
        self.assertEqual(calls[0][4].unpack(), ("go-to-tab", [1], {}))

    def test_native_application_action_rejects_owner_and_route_changes(self) -> None:
        bus = GtkActionBus.__new__(GtkActionBus)
        bus._connection_pid = lambda _destination: 99  # type: ignore[method-assign]
        route = {
            "adapter": "pinta",
            "destination": ":1.7",
            "object_path": "/com/github/PintaProject/Pinta",
            "action": "active_document",
            "index": 0,
            "count": 2,
        }

        with self.assertRaisesRegex(CommandError, "owner changed"):
            bus.activate(route, 42)
        bus._connection_pid = lambda _destination: 42  # type: ignore[method-assign]
        bus._describe = lambda *_args: (True, "s", 0)  # type: ignore[method-assign]
        with self.assertRaisesRegex(CommandError, "action changed"):
            bus.activate(route, 42)
        route["action"] = "other"
        with self.assertRaisesRegex(CommandError, "route is invalid"):
            bus.activate(route, 42)
        route["action"] = "active_document"
        route["index"] = "not-an-index"
        with self.assertRaisesRegex(CommandError, "index is invalid"):
            bus.activate(route, 42)

    async def test_provider_retries_first_seen_browser_until_tabs_are_available(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "chromium",
            "title": "Current page - Chromium",
            "focusHistoryID": 0,
        }
        top = TopLevel(None, object(), 42, 0, client["title"], client)
        accessible = self.tab("Current page", "native-tab-1", selected=True)
        tab = NativeTab(
            accessible=accessible,
            top=top,
            strip_path=(0,),
            tab_path=(0, 0),
            index=0,
            title="Current page",
            selected=True,
            native_id="native-tab-1",
        )

        class DelayedTree:
            scans = 0

            def top_levels(self, _context):
                return [top]

            def native_tabs(self, _top, *, browser):
                self.__class__.scans += 1
                return [tab] if browser and self.__class__.scans >= 2 else []

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
            provider_metadata={
                "hyprland": {
                    "clients": [{"address": "0xabc", "item_id": "hyprland:window"}]
                }
            },
        )
        provider = AtspiProvider()

        with patch("everything.providers.atspi.AtspiTree", DelayedTree), patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (0,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            result = await provider.scan(context)

        self.assertEqual(DelayedTree.scans, 2)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].kind, "browser-tab")
        self.assertEqual(result.items[0].title, "Current page")
        self.assertEqual(result.items[0].parent_id, "hyprland:window")
        self.assertEqual(result.items[0].activation["address"], "0xabc")
        self.assertEqual(result.items[0].activation["tab_route"], {"kind": "atspi-action"})

    async def test_available_tabs_are_not_delayed_by_an_uncovered_browser(self) -> None:
        clients = [
            {
                "address": "0xnautilus",
                "pid": 42,
                "class": "org.gnome.Nautilus",
                "title": "Home",
            },
            {
                "address": "0xbrowser",
                "pid": 43,
                "class": "chromium",
                "title": "Loading - Chromium",
            },
        ]
        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=clients,
        )
        item = Thing("atspi:nautilus", "app-tab", "Nautilus", "Home")
        provider = AtspiProvider()

        with patch.object(
            provider,
            "_collect",
            return_value=([item], {}, {"0xnautilus"}),
        ) as collect, patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (0,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            result = await provider.scan(context)

        self.assertEqual(result.items, [item])
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(provider.settled_browser_clients, set())
        self.assertEqual(
            provider.settled_application_clients,
            {("0xnautilus", 42, "birth")},
        )

    async def test_provider_keeps_uncovered_browser_eligible_for_later_settling(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "chromium",
            "title": "Current page - Chromium",
            "focusHistoryID": 0,
        }
        top = TopLevel(None, object(), 42, 0, client["title"], client)
        accessible = self.tab("Current page", "native-tab-1", selected=True)
        tab = NativeTab(
            accessible=accessible,
            top=top,
            strip_path=(0,),
            tab_path=(0, 0),
            index=0,
            title="Current page",
            selected=True,
            native_id="native-tab-1",
        )

        class DelayedAcrossScansTree:
            scans = 0

            def top_levels(self, _context):
                return [top]

            def native_tabs(self, _top, *, browser):
                self.__class__.scans += 1
                return [tab] if browser and self.__class__.scans >= 4 else []

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
            provider_metadata={
                "hyprland": {
                    "clients": [{"address": "0xabc", "item_id": "hyprland:window"}]
                }
            },
        )
        provider = AtspiProvider()

        with patch("everything.providers.atspi.AtspiTree", DelayedAcrossScansTree), patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (0,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            first = await provider.scan(context)
            self.assertEqual(first.items, [])
            self.assertEqual(provider.settled_browser_clients, set())

            second = await provider.scan(context)

        self.assertEqual(DelayedAcrossScansTree.scans, 4)
        self.assertEqual([item.title for item in second.items], ["Current page"])
        self.assertEqual(
            provider.settled_browser_clients,
            {("0xabc", 42, "birth")},
        )

    async def test_provider_retries_when_a_settled_browser_temporarily_loses_coverage(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "chromium",
            "title": "Current page - Chromium",
            "focusHistoryID": 0,
        }
        top = TopLevel(None, object(), 42, 0, client["title"], client)
        accessible = self.tab("Current page", "native-tab-1", selected=True)
        tab = NativeTab(
            accessible=accessible,
            top=top,
            strip_path=(0,),
            tab_path=(0, 0),
            index=0,
            title="Current page",
            selected=True,
            native_id="native-tab-1",
        )

        class IntermittentTree:
            scans = 0

            def top_levels(self, _context):
                return [top]

            def native_tabs(self, _top, *, browser):
                self.__class__.scans += 1
                return [tab] if browser and self.__class__.scans != 2 else []

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
            provider_metadata={
                "hyprland": {
                    "clients": [{"address": "0xabc", "item_id": "hyprland:window"}]
                }
            },
        )
        provider = AtspiProvider()

        with patch("everything.providers.atspi.AtspiTree", IntermittentTree), patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (0,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            first = await provider.scan(context)
            second = await provider.scan(context)

        self.assertEqual([item.title for item in first.items], ["Current page"])
        self.assertEqual([item.title for item in second.items], ["Current page"])
        self.assertEqual(IntermittentTree.scans, 3)

    async def test_provider_settles_first_seen_nautilus_tabs(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "org.gnome.Nautilus",
            "title": "Home",
            "focusHistoryID": 0,
        }
        top = TopLevel(None, object(), 42, 0, client["title"], client)
        tabs = [
            NativeTab(
                accessible=self.component_tab("Home", "tab-1", selected=True),
                top=top,
                strip_path=(0,),
                tab_path=(0, index),
                index=index,
                title=title,
                selected=index == 0,
                native_id=f"tab-{index + 1}",
            )
            for index, title in enumerate(("Home", "Downloads"))
        ]

        class DelayedNautilusTree:
            scans = 0

            def top_levels(self, _context):
                return [top]

            def native_tabs(self, _top, *, browser):
                self.__class__.scans += 1
                return tabs if not browser and self.__class__.scans >= 2 else []

        class NautilusRoutes:
            def routes(self, *_args):
                return [{"kind": "gtk-action"} for _tab in tabs]

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
            provider_metadata={
                "hyprland": {
                    "clients": [{"address": "0xabc", "item_id": "hyprland:window"}]
                }
            },
        )
        provider = AtspiProvider()
        provider.gtk_actions = NautilusRoutes()  # type: ignore[assignment]

        with patch("everything.providers.atspi.AtspiTree", DelayedNautilusTree), patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (0,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            result = await provider.scan(context)

        self.assertEqual(DelayedNautilusTree.scans, 2)
        self.assertEqual([item.title for item in result.items], ["Home", "Downloads"])
        self.assertEqual(
            provider.settled_application_clients,
            {("0xabc", 42, "birth")},
        )

    async def test_provider_does_not_repeatedly_settle_empty_nautilus_window(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "org.gnome.Nautilus",
            "title": "Home",
        }
        top = TopLevel(None, object(), 42, 0, client["title"], client)

        class EmptyNautilusTree:
            scans = 0

            def top_levels(self, _context):
                return [top]

            def native_tabs(self, _top, *, browser):
                self.__class__.scans += 1
                return []

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
        )
        provider = AtspiProvider()

        with patch("everything.providers.atspi.AtspiTree", EmptyNautilusTree), patch(
            "everything.providers.atspi.NATIVE_TAB_SETTLE_DELAYS", (0,)
        ), patch("everything.providers.atspi.process_birth", return_value="birth"):
            first = await provider.scan(context)
            second = await provider.scan(context)

        self.assertEqual(first.items, [])
        self.assertEqual(second.items, [])
        self.assertEqual(EmptyNautilusTree.scans, 3)
        self.assertEqual(
            provider.settled_application_clients,
            {("0xabc", 42, "birth")},
        )

    async def test_provider_publishes_priority_tabs_before_generic_application_tabs(
        self,
    ) -> None:
        nautilus_client = {
            "address": "0xnautilus",
            "pid": 42,
            "class": "org.gnome.Nautilus",
            "title": "Home",
            "focusHistoryID": 0,
        }
        editor_client = {
            "address": "0xeditor",
            "pid": 43,
            "class": "org.example.Editor",
            "title": "Draft",
            "focusHistoryID": 1,
        }
        nautilus_top = TopLevel(
            None, object(), 42, 0, nautilus_client["title"], nautilus_client
        )
        editor_top = TopLevel(
            None, object(), 43, 0, editor_client["title"], editor_client
        )
        nautilus_tab = NativeTab(
            accessible=self.component_tab("Home", "nautilus-tab", selected=True),
            top=nautilus_top,
            strip_path=(0,),
            tab_path=(0, 0),
            index=0,
            title="Home",
            selected=True,
            native_id="nautilus-tab",
        )
        editor_tab = NativeTab(
            accessible=self.tab("Draft", "editor-tab", selected=True),
            top=editor_top,
            strip_path=(0,),
            tab_path=(0, 0),
            index=0,
            title="Draft",
            selected=True,
            native_id="editor-tab",
        )

        class PriorityTree:
            calls: list[str] = []

            def top_levels(self, _context):
                return [nautilus_top, editor_top]

            def native_tabs(self, top, *, browser):
                self.__class__.calls.append(top.client["address"])
                if top is nautilus_top:
                    return [nautilus_tab]
                return [editor_tab]

        class NautilusRoutes:
            def routes(self, *_args):
                return [{"kind": "gtk-action"}]

        clients = [nautilus_client, editor_client]
        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=clients,
            provider_metadata={
                "hyprland": {
                    "clients": [
                        {
                            "address": client["address"],
                            "item_id": f"hyprland:{client['address']}",
                        }
                        for client in clients
                    ]
                }
            },
        )
        provider = AtspiProvider()
        # Model a running provider that already published an empty priority
        # client set before Nautilus opened.
        provider.published_priority_clients = set()
        provider.gtk_actions = NautilusRoutes()  # type: ignore[assignment]

        with patch("everything.providers.atspi.AtspiTree", PriorityTree), patch(
            "everything.providers.atspi.process_birth", return_value="birth"
        ):
            first = await provider.scan(context)
            first_calls = list(PriorityTree.calls)
            second = await provider.scan(context)

        self.assertEqual(first_calls, ["0xnautilus"])
        self.assertEqual([item.title for item in first.items], ["Home"])
        self.assertEqual(
            PriorityTree.calls,
            ["0xnautilus", "0xnautilus", "0xeditor"],
        )
        self.assertEqual([item.title for item in second.items], ["Home", "Draft"])
        self.assertEqual(
            provider.published_priority_clients,
            {("0xnautilus", 42, "birth")},
        )

    async def test_provider_drops_application_tabs_without_their_mapped_parent(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "org.example.Editor",
            "title": "Draft",
            "focusHistoryID": 0,
        }
        top = TopLevel(None, object(), 42, 0, "Draft", client)
        tab = NativeTab(
            accessible=self.tab("Draft", "native-tab-1", selected=True),
            top=top,
            strip_path=(0,),
            tab_path=(0, 0),
            index=0,
            title="Draft",
            selected=True,
            native_id="native-tab-1",
        )

        class LingeringTree:
            def top_levels(self, _context):
                return [top]

            def native_tabs(self, _top, *, browser):
                return [] if browser else [tab]

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            # Model the toolkit tree/client lingering after Hyprland has
            # removed the mapped parent from its public metadata.
            hypr_clients=[client],
            provider_metadata={"hyprland": {"clients": []}},
        )
        provider = AtspiProvider()
        provider.published_priority_clients = set()

        with patch("everything.providers.atspi.AtspiTree", LingeringTree), patch(
            "everything.providers.atspi.process_birth", return_value="birth"
        ):
            result = await provider.scan(context)

        self.assertEqual(result.items, [])
        self.assertEqual(provider.objects, {})

    async def test_provider_emits_distinct_deep_wrapped_application_tabs(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "org.gnome.Nautilus",
            "title": "Home",
            "focusHistoryID": 0,
        }
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            FakeAccessible(
                Atspi.Role.GROUPING,
                "",
                self.component_tab("Home", "AdwTab", selected=True),
            ),
            FakeAccessible(
                Atspi.Role.GROUPING,
                "",
                self.component_tab("Downloads", "AdwTab"),
            ),
        )
        nested = native
        for _index in range(12):
            nested = FakeAccessible(Atspi.Role.PANEL, "", nested)
        root = FakeAccessible(Atspi.Role.FRAME, "Home", nested)
        top = TopLevel(None, root, 42, 0, "Home", client)
        tree = AtspiTree.__new__(AtspiTree)
        tree.top_levels = lambda _context: [top]  # type: ignore[method-assign]
        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
            provider_metadata={
                "hyprland": {
                    "clients": [{"address": "0xabc", "item_id": "hyprland:window"}]
                }
            },
        )
        provider = AtspiProvider()

        class FakeGtkActions:
            def routes(self, app_class, pid, top_name, tabs):
                self.observed = (app_class, pid, top_name)
                return GtkActionBus._routes(
                    "nautilus",
                    "org.gnome.Nautilus",
                    "/org/gnome/Nautilus/window/1",
                    "go-to-tab",
                    tabs,
                )

        actions = FakeGtkActions()
        provider.gtk_actions = actions  # type: ignore[assignment]

        with patch("everything.providers.atspi.AtspiTree", return_value=tree), patch(
            "everything.providers.atspi.process_birth", return_value="birth"
        ):
            result = await provider.scan(context)

        self.assertEqual([item.kind for item in result.items], ["app-tab", "app-tab"])
        self.assertEqual([item.title for item in result.items], ["Home", "Downloads"])
        self.assertEqual({item.provider for item in result.items}, {"Nautilus"})
        self.assertEqual({item.parent_id for item in result.items}, {"hyprland:window"})
        self.assertEqual(len({item.id for item in result.items}), 2)
        self.assertEqual(len(provider.objects), 2)
        self.assertEqual(
            result.items[1].activation["tab_route"],
            {
                "kind": "gtk-action",
                "adapter": "nautilus",
                "destination": "org.gnome.Nautilus",
                "object_path": "/org/gnome/Nautilus/window/1",
                "action": "go-to-tab",
                "index": 1,
                "count": 2,
            },
        )
        self.assertEqual(
            actions.observed,
            ("org.gnome.Nautilus", 42, "Home"),
        )

    async def test_provider_omits_component_only_tabs_without_a_native_route(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "org.example.Editor",
            "title": "First",
            "focusHistoryID": 0,
        }
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            self.component_tab("First", "tab-1", selected=True),
            self.component_tab("Second", "tab-2"),
        )
        root = FakeAccessible(Atspi.Role.FRAME, "First", native)
        top = TopLevel(None, root, 42, 0, "First", client)
        tree = AtspiTree.__new__(AtspiTree)
        tree.top_levels = lambda _context: [top]  # type: ignore[method-assign]
        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
            provider_metadata={
                "hyprland": {
                    "clients": [{"address": "0xabc", "item_id": "hyprland:window"}]
                }
            },
        )
        provider = AtspiProvider()
        provider.published_priority_clients = set()

        class NoRoutes:
            def __init__(self):
                self.calls = []

            def routes(self, *_args):
                self.calls.append(_args)
                return None

        routes = NoRoutes()
        provider.gtk_actions = routes  # type: ignore[assignment]
        with patch("everything.providers.atspi.AtspiTree", return_value=tree):
            result = await provider.scan(context)

        self.assertEqual(result.items, [])
        self.assertEqual(provider.objects, {})
        self.assertEqual(len(routes.calls), 1)
        self.assertEqual(routes.calls[0][:3], ("org.example.Editor", 42, "First"))

    async def test_provider_omits_ambiguous_component_routes_for_two_app_windows(self) -> None:
        clients = [
            {
                "address": f"0xabc{index}",
                "pid": 42,
                "class": "org.gnome.Nautilus",
                "title": title,
                "focusHistoryID": index,
            }
            for index, title in enumerate(("Home", "Downloads"))
        ]
        tops = [
            TopLevel(None, object(), 42, index, client["title"], client)
            for index, client in enumerate(clients)
        ]
        tabs = {
            id(top): [
                NativeTab(
                    self.component_tab(top.name, f"tab-{index}"),
                    top,
                    (0,),
                    (0, 0),
                    0,
                    top.name,
                    True,
                    f"tab-{index}",
                )
            ]
            for index, top in enumerate(tops)
        }

        class MultipleTree:
            def top_levels(self, _context):
                return tops

            def native_tabs(self, top, *, browser):
                return tabs[id(top)]

        class UnexpectedRoutes:
            def routes(self, *_args):
                raise AssertionError("ambiguous application windows must not be routed")

        provider = AtspiProvider()
        provider.gtk_actions = UnexpectedRoutes()  # type: ignore[assignment]
        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=clients,
            provider_metadata={
                "hyprland": {
                    "clients": [
                        {
                            "address": client["address"],
                            "item_id": f"hyprland:{client['address']}",
                        }
                        for client in clients
                    ]
                }
            },
        )

        with patch("everything.providers.atspi.AtspiTree", MultipleTree):
            result = await provider.scan(context)

        self.assertEqual(result.items, [])

    async def test_provider_activates_and_revalidates_native_application_tab(self) -> None:
        client = {
            "address": "0xabc",
            "pid": 42,
            "class": "org.gnome.Nautilus",
            "title": "Home",
            "focusHistoryID": 0,
        }
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            self.component_tab("Home", "tab-1", selected=True),
            self.component_tab("Downloads", "tab-2"),
        )
        root = FakeAccessible(Atspi.Role.FRAME, "Home", native)
        top = TopLevel(None, root, 42, 0, "Home", client)
        tabs = AtspiTree.__new__(AtspiTree).native_tabs(top, browser=False)
        target = tabs[1]
        protocol_thread = threading.get_ident()
        events = []

        class FakeGtkActions:
            def activate(self, route, pid):
                events.append(("activate", route["index"], pid, threading.get_ident()))

        async def record_focus(_context, address):
            events.append(("focus", address, threading.get_ident()))

        provider = AtspiProvider()
        provider.objects = {"item": target}
        provider.gtk_actions = FakeGtkActions()  # type: ignore[assignment]
        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[client],
        )
        activation = {
            "item_id": "item",
            "native_id": target.native_id,
            "address": "0xabc",
            "pid": 42,
            "birth": "birth",
            "tab_route": {
                "kind": "gtk-action",
                "adapter": "nautilus",
                "destination": "org.gnome.Nautilus",
                "object_path": "/org/gnome/Nautilus/window/1",
                "action": "go-to-tab",
                "index": 1,
                "count": 2,
            },
        }

        executor = AtspiExecutor()
        try:
            with patch("everything.providers.atspi.process_birth", return_value="birth"), patch(
                "everything.providers.atspi.focus_address",
                new=AsyncMock(side_effect=record_focus),
            ):
                await executor.run(lambda: provider.activate(activation, context))
        finally:
            await executor.close()

        self.assertNotEqual(executor.thread_id, protocol_thread)
        self.assertEqual(
            events,
            [
                ("activate", 1, 42, executor.thread_id),
                ("focus", "0xabc", executor.thread_id),
            ],
        )

    def test_provider_rejects_reordered_native_application_tab(self) -> None:
        first = self.component_tab("First", "tab-1", selected=True)
        second = self.component_tab("Second", "tab-2")
        native = FakeAccessible(Atspi.Role.PAGE_TAB_LIST, "Tab strip", first, second)
        root = FakeAccessible(Atspi.Role.FRAME, "First", native)
        top = TopLevel(None, root, 42, 0, "First", {"address": "0xabc"})
        target = AtspiTree.__new__(AtspiTree).native_tabs(top, browser=False)[1]
        route = {"index": 1, "count": 2}

        native.children.reverse()

        with self.assertRaisesRegex(CommandError, "scan identity"):
            AtspiProvider._validated_gtk_tab(target, target.native_id, route)

    def test_provider_revalidates_only_the_known_application_tab_strip(self) -> None:
        unrelated = FakeAccessible(
            Atspi.Role.PANEL,
            "Unrelated content",
            FakeAccessible(Atspi.Role.BUTTON, "Unrelated button", actionable=True),
        )
        native = FakeAccessible(
            Atspi.Role.PAGE_TAB_LIST,
            "Tab strip",
            self.component_tab("First", "tab-1", selected=True),
            self.component_tab("Second", "tab-2"),
        )
        root = FakeAccessible(Atspi.Role.FRAME, "First", unrelated, native)
        top = TopLevel(None, root, 42, 0, "First", {"address": "0xabc"})
        target = AtspiTree.__new__(AtspiTree).native_tabs(top, browser=False)[1]
        unrelated.child_count_reads = 0

        current = AtspiProvider._validated_gtk_tab(
            target,
            target.native_id,
            {"index": 1, "count": 2},
        )

        self.assertEqual(current.native_id, target.native_id)
        self.assertEqual(unrelated.child_count_reads, 0)

    async def test_provider_omits_app_mode_tabs_without_reclassifying_them(self) -> None:
        normal_client = {
            "address": "0xnormal",
            "pid": 42,
            "class": "chromium",
            "initialClass": "chromium",
            "title": "Current page - Chromium",
            "initialTitle": "New tab - Chromium",
            "focusHistoryID": 0,
        }
        app_client = {
            "address": "0xapp",
            "pid": 42,
            "class": "chrome-app.example.test__-Default",
            "initialClass": "chrome-app.example.test__-Default",
            "title": "Example app",
            "initialTitle": "app.example.test_/",
            "focusHistoryID": 1,
        }
        normal_top = TopLevel(None, object(), 42, 0, normal_client["title"], normal_client)
        app_top = TopLevel(None, object(), 42, 1, app_client["title"], app_client)
        normal_accessible = self.tab("Normal tab", "normal-tab", selected=True)
        app_accessible = self.tab("App-mode tab", "app-tab", selected=True)

        class MixedTree:
            def top_levels(self, _context):
                return [normal_top, app_top]

            def native_tabs(self, top, *, browser):
                return [
                    NativeTab(
                        accessible=(normal_accessible if top is normal_top else app_accessible),
                        top=top,
                        strip_path=(0,),
                        tab_path=(0, 0),
                        index=0,
                        title="Normal tab" if top is normal_top else "App-mode tab",
                        selected=True,
                        native_id="normal-tab" if top is normal_top else "app-tab",
                    )
                ]

        context = ScanContext(
            runner=CommandRunner(),
            processes=ProcTable({}),
            hypr_clients=[normal_client, app_client],
            provider_metadata={
                "hyprland": {
                    "clients": [
                        {"address": "0xnormal", "item_id": "hyprland:normal"},
                        {"address": "0xapp", "item_id": "hyprland:app"},
                    ]
                }
            },
        )
        provider = AtspiProvider()

        with patch("everything.providers.atspi.AtspiTree", MixedTree), patch(
            "everything.providers.atspi.process_birth", return_value="birth"
        ):
            result = await provider.scan(context)

        self.assertEqual([item.title for item in result.items], ["Normal tab"])
        self.assertEqual(result.items[0].kind, "browser-tab")
        self.assertEqual(result.items[0].parent_id, "hyprland:normal")
        self.assertEqual(set(provider._browser_clients(context).values()), {"0xnormal"})


if __name__ == "__main__":
    unittest.main()
