"""Exercise only Flint UI and temporary picker replies. No system actions."""
import json
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IPC = ["quickshell", "ipc", "-p", str(ROOT), "call", "flint"]


def call(*args):
    return subprocess.check_output(IPC + list(args), text=True).strip()


def opened(payload):
    call("open", json.dumps(payload))
    return settled()


def settled():
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        state = json.loads(call("inspect"))
        if state["ready"] and not state["busy"]:
            assert not state["error"], state
            return state
        time.sleep(.05)
    raise AssertionError("UI did not settle")


def main():
    results = []
    try:
        state = opened({})
        assert state["count"] == 8, state
        call("activate")  # Applications is the first, navigation-only result.
        time.sleep(.2)
        state = json.loads(call("inspect"))
        assert state["scope"] == "flint.applications" and state["count"] > 0, state
        results.append("Home and native application index")
        call("back")
        state = opened({})
        call("select", "7")
        call("activate")
        time.sleep(.1)
        state = settled()
        assert state["scope"] == "flint.settings" and state["selected"] == 0, state
        call("back")
        state = settled()
        assert state["scope"] == "" and state["selected"] == 0, state
        results.append("Submenu entry and back navigation reset selection")
        state = opened({"query": "22"})
        assert state["titles"][0] == "22", state
        creations = state["rowCreations"]
        for query, expected in [("22+", "22+ …"), ("22+1", "23"), ("22+12", "34"), ("22+123", "145")]:
            call("query", query)
            state = json.loads(call("inspect"))
            assert state["count"] > 0 and state["modelCount"] > 0 and not state["loadingVisible"], state
            state = settled()
            assert state["titles"][0] == expected and state["rowCreations"] == creations, state
        results.append("Typing preserves rows and delegates, including incomplete arithmetic")
        state = opened({"query": "chrome"})
        assert state["titles"][0] == "Google Chrome", state
        assert "Flint Settings" not in state["titles"], state
        results.append("Installed Chrome outranks menu configuration matches")
        for query, expected in [("2m in feet", "6.56167979 feet"), ("sqrt(144)", "12"), ("#ff6644", "#FF6644")]:
            state = opened({"query": query})
            assert state["titles"][0] == expected, state
        results.append("Calculator, converter and color previews")
        state = opened({"query": "a completely unmatched question about orbital teapots"})
        assert state["count"] == 3, state
        results.append("Three AI and web fallbacks")
        state = opened({"scope": "flint.settings/flint.ai", "title": "AI & Web Search"})
        assert state["count"] == 3, state
        call("select", "1")
        call("activate")
        time.sleep(.15)
        state = json.loads(call("inspect"))
        assert set(state["titles"]) == {"Browser", "Cli", "Desktop"}, state
        results.append("Schema-generated AI settings and navigation")
        state = opened({"scope": "flint.omarchy/root", "title": "Omarchy"})
        assert "System" in state["titles"] and "Style" in state["titles"], state
        state = opened({"scope": "flint.omarchy/style.font", "title": "Fonts"})
        assert state["count"] > 0, state
        results.append("Omarchy root and dynamic font provider")
        with tempfile.TemporaryDirectory() as tmp:
            selection, done = Path(tmp)/"selection", Path(tmp)/"done"
            payload = dict(mode="select", prompt="Smoke test", options=["◆\tChoice\tstable key"], selectionFile=str(selection), doneFile=str(done))
            opened(payload)
            call("activate")
            deadline = time.monotonic() + 2
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert done.exists() and selection.read_text() == "Choice\tstable key\n"
            done.unlink()
            payload.update(mode="input", query="literal $() `id` text")
            opened(payload)
            call("activate")
            deadline = time.monotonic() + 2
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert selection.read_text() == "literal $() `id` text\n"
            done.unlink()
            opened(payload)
            call("close")
            deadline = time.monotonic() + 2
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(.02)
            assert done.exists() and selection.read_text() == ""
        results.append("Omarchy select/input/cancel reply protocol")
    finally:
        call("close")
    for result in results:
        print("PASS " + result)


if __name__ == "__main__":
    main()
