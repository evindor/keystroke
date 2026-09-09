import QtQuick
import QtTest
import "../core/Extensions.js" as Extensions
import "../core/Match.js" as Match

TestCase {
    name: "Extensions"
    property string omarchy: "/usr/share/omarchy"
    property string timerId: "io.github.evindor.keystroke-timer"
    property string dir: "/home/me/.config/omarchy/plugins/"
    property var plugins: ({
        "io.github.evindor.keystroke-timer": { id: "io.github.evindor.keystroke-timer", name: "Timer", version: "1.0.0", author: "A", description: "Countdown timers",
                                               homepage: "https://github.com/evindor/keystroke-timer", kinds: ["service"], entryPoints: { service: "Service.qml" },
                                               "x-keystroke": { apiVersion: 1 }, __sourceDir: "/home/me/.config/omarchy/plugins/io.github.evindor.keystroke-timer" },
        "example.keystroke-hello": { id: "example.keystroke-hello", name: "Hello", version: "1.0.0", kinds: ["service"], entryPoints: { service: "Service.qml" },
                                     "x-keystroke": { apiVersion: 1 }, __sourceDir: "/home/me/.config/omarchy/plugins/example.keystroke-hello" },
        "jankeesvw.workspace-name": { id: "jankeesvw.workspace-name", name: "Workspace name", kinds: ["bar-widget"] },
        "omarchy.clock": { id: "omarchy.clock", name: "Clock", kinds: ["bar-widget"] }
    })
    function on(id) { return id === timerId }
    function installed(git, problems) { return Extensions.installed(plugins, on, git || {}, problems || []) }
    function record(folder, body) { return dir + folder + "/manifest.json\n" + body + "\u0000" }
    // The check script prints tab-separated lines; build them here so the file itself stays tab-free.
    function line(parts) { return parts.join("\t") + "\n" }
    function ranked(rows, q) {
        var out = []
        for (var i = 0; i < rows.length; i++) {
            var r = rows[i]
            if (typeof r.score !== "number") r.score = Match.match(q, r.title, r.keywords || "", r.path || "", r.description || "")
            if (!q || r.score > 0) out.push(r)
        }
        return Match.rank(out, null)
    }
    function titles(rows) { return rows.map(function(r) { return r.title }) }
    function names(list) { return list.map(function(e) { return e.name }) }

    function test_git_urls_are_accepted_shorthands_expanded_and_options_refused() {
        compare(Extensions.gitUrl("https://github.com/evindor/keystroke-timer.git"), "https://github.com/evindor/keystroke-timer.git")
        compare(Extensions.gitUrl("https://codeberg.org/x/y"), "https://codeberg.org/x/y")
        compare(Extensions.gitUrl("git@github.com:evindor/keystroke-timer.git"), "git@github.com:evindor/keystroke-timer.git")
        compare(Extensions.gitUrl("evindor/keystroke-timer"), "https://github.com/evindor/keystroke-timer.git")
        compare(Extensions.gitUrl("file:///home/me/keystroke-calpad.git"), "file:///home/me/keystroke-calpad.git")
        compare(Extensions.gitUrl("file://relative/path"), "")
        compare(Extensions.gitUrl("file:///home/me/../etc"), "")
        compare(Extensions.gitUrl("/home/me/keystroke-calpad.git"), "")
        compare(Extensions.gitUrl("  evindor/keystroke-timer.git "), "https://github.com/evindor/keystroke-timer.git")
        compare(Extensions.gitUrl("--upload-pack=touch /tmp/x"), "")
        compare(Extensions.gitUrl("-oProxyCommand=x"), "")
        compare(Extensions.gitUrl("http://github.com/x/y"), "")
        compare(Extensions.gitUrl("ext::sh -c x"), "")
        compare(Extensions.gitUrl("timer 10m"), "")
        compare(Extensions.gitUrl("chrome"), "")
        compare(Extensions.repoSlug("https://github.com/Evindor/Keystroke-Timer.git"), "evindor/keystroke-timer")
        compare(Extensions.repoSlug("git@github.com:evindor/keystroke-timer.git"), "evindor/keystroke-timer")
    }

    function test_index_and_catalog_are_parsed_defensively() {
        compare(Extensions.parseIndex("not json"), [])
        compare(Extensions.parseIndex(JSON.stringify({ version: 2, extensions: [] })), [])
        var idx = Extensions.parseIndex(JSON.stringify({ version: 1, extensions: [
            { id: "IO.GitHub.Evindor.Keystroke-Timer", name: "Timer", description: "Countdown  timers", author: "A", repo: "evindor/keystroke-timer", tags: ["timer", 3] },
            { id: "bad", name: "No repo" },
            { id: "evil", name: "Evil", repo: "--upload-pack=x" },
            "junk"
        ] }))
        compare(idx.length, 1)
        compare(idx[0].id, "io.github.evindor.keystroke-timer")
        compare(idx[0].repo, "https://github.com/evindor/keystroke-timer.git")
        compare(idx[0].description, "Countdown  timers")
        compare(idx[0].tags, ["timer", "3"])
        compare(idx[0].source, "index")

        var cat = Extensions.parseCatalog(JSON.stringify({ plugins: [
            { id: "x.keystroke-spotify", name: "Spotify", description: "Spotify for Keystroke", author: "X", repo: "https://github.com/x/keystroke-spotify", tags: ["launcher"], installAvailable: true, verificationStatus: "verified" },
            { id: "y.clock", name: "Clock", description: "A clock", repo: "https://github.com/y/clock", tags: ["bar"], installAvailable: true },
            { id: "z.translate", name: "Translate", description: "Google Translate provider for Keystroke", repo: "https://github.com/z/t", installAvailable: false },
            { id: "b.thing", name: "Keystroke thing", sourceType: "builtin", repo: "https://github.com/omacom/omarchy" },
            { id: "a.clickup", name: "ClickUp", description: "Tasks in the bar, with one keystroke to move a task forward.", repo: "https://github.com/a/clickup" },
            { id: "b.switchboard", name: "Switchboard", description: "Every window on every workspace, one keystroke away.", repo: "https://github.com/b/s" },
            { id: "c.clean", name: "Clean Keyboard", description: "Wipe the keyboard without triggering keystrokes.", repo: "https://github.com/c/clean" },
            { id: "d.dict", name: "Dictionary", description: "Look words up inside Keystroke.", repo: "https://github.com/d/dict" },
            { id: "e.gh", name: "GitHub", description: "A Keystroke extension for GitHub issues", repo: "https://github.com/e/gh" },
            { id: "f.tagged", name: "Tagged", description: "Something", tags: ["keystroke"], repo: "https://github.com/f/t" }
        ] }))
        compare(names(cat), ["Spotify", "Dictionary", "GitHub", "Tagged"])
        compare(cat[0].source, "marketplace")
        verify(cat[0].verified)
        compare(Extensions.parseCatalog("{}"), [])
    }

    function test_discover_merges_by_id_and_repository() {
        var index = Extensions.parseIndex(JSON.stringify({ version: 1, extensions: [{ id: "a.one", name: "One", repo: "a/one" }, { id: "a.two", name: "Two", repo: "a/two" }] }))
        var catalog = Extensions.parseCatalog(JSON.stringify({ plugins: [
            { id: "a.one", name: "One (marketplace)", description: "for Keystroke", repo: "https://github.com/other/one" },
            { id: "other.two", name: "Two (marketplace)", description: "for Keystroke", repo: "https://github.com/A/Two.git" },
            { id: "c.three", name: "Three", description: "for Keystroke", repo: "https://github.com/c/three" }
        ] }))
        compare(names(Extensions.discover(index, catalog)), ["One", "Two", "Three"])
    }

    function test_scan_output_is_parsed_into_marked_manifests_and_problems() {
        var argv = Extensions.scanArgv("/home/me")
        compare(argv.slice(0, 2), ["bash", "-c"])
        compare(argv.slice(-1), ["/home/me/.config/omarchy/plugins"])
        var text = record(timerId, JSON.stringify({ id: timerId, name: "Timer", kinds: ["service"], entryPoints: { service: "Service.qml" }, "x-keystroke": { apiVersion: 1 } }))
                 + record("omarchy.clock", JSON.stringify({ id: "omarchy.clock", name: "Clock", kinds: ["bar-widget"] }))
                 + record("broken.keystroke-thing", '{ "id": "broken.keystroke-thing", "x-keystroke": { "apiVersion": 1 }, oops')
                 + record("wrong-folder", JSON.stringify({ id: "x.keystroke-misnamed", kinds: ["service"], "x-keystroke": { apiVersion: 1 } }))
                 + record("plain.broken", '{ not json')
                 + record("no.id", JSON.stringify({ kinds: ["service"], "x-keystroke": { apiVersion: 1 } }))
        var found = Extensions.parseScan(text)
        compare(Object.keys(found.manifests), [timerId])
        compare(found.manifests[timerId].__sourceDir, dir + timerId)
        compare(found.manifests[timerId].name, "Timer")
        compare(found.problems, [
            { pluginId: "broken.keystroke-thing", message: "manifest.json is not valid JSON" },
            { pluginId: "wrong-folder", message: "Folder name must equal the plugin id (x.keystroke-misnamed)" },
            { pluginId: "no.id", message: "Folder name must equal the plugin id (missing)" }
        ])
        compare(Extensions.parseScan(""), { manifests: {}, problems: [] })
        compare(Extensions.parseScan("garbage without newline"), { manifests: {}, problems: [] })

        compare(Extensions.serviceUrl(found.manifests[timerId]), "file://" + dir + timerId + "/Service.qml")
        compare(Extensions.serviceUrl({ __sourceDir: "/d", kinds: ["service"], entryPoints: { service: "sub/Main.qml" } }), "file:///d/sub/Main.qml")
        compare(Extensions.serviceUrl({ __sourceDir: "/d", kinds: ["bar-widget"], entryPoints: { service: "Service.qml" } }), "")
        compare(Extensions.serviceUrl({ __sourceDir: "/d", kinds: ["service"], entryPoints: {} }), "")
        compare(Extensions.serviceUrl({ __sourceDir: "/d", kinds: ["service"], entryPoints: { service: "../other/Service.qml" } }), "")
        compare(Extensions.serviceUrl({ __sourceDir: "/d", kinds: ["service"], entryPoints: { service: "/etc/Service.qml" } }), "")
        compare(Extensions.serviceUrl({ kinds: ["service"], entryPoints: { service: "Service.qml" } }), "")

        var pub = Extensions.publicManifest(found.manifests[timerId])
        compare(pub.id, timerId)
        verify(!("__sourceDir" in pub))
        verify("__sourceDir" in found.manifests[timerId])
    }

    function test_installed_lists_marked_plugins_with_keystrokes_switch_and_problems() {
        var list = installed()
        compare(list.map(function(e) { return e.id }), ["example.keystroke-hello", timerId])
        var timer = list[1]
        verify(timer.enabled); verify(timer.git); verify(!timer.checked); verify(!timer.updateAvailable); compare(timer.problem, "")
        compare(timer.homepage, "https://github.com/evindor/keystroke-timer")
        var hello = list[0]
        verify(!hello.enabled)
        // Everything on disk is on unless the user said otherwise.
        verify(Extensions.installed(plugins, null, {}, [])[0].enabled)
        var sick = installed({}, [{ pluginId: timerId, message: "Service.qml:3:1 Syntax error" }, { pluginId: timerId, message: "later" }])
        compare(sick[1].problem, "Service.qml:3:1 Syntax error")
        compare(sick[0].problem, "")

        var git = Extensions.parseCheck(line([timerId, "aaaa", "bbbb", "https://github.com/evindor/keystroke-timer.git"]) + line(["example.keystroke-hello", "", "", ""]) + "\ngarbage line\n")
        var after = installed(git)
        verify(after[1].updateAvailable); verify(after[1].checked)
        compare(after[1].remote, "https://github.com/evindor/keystroke-timer.git")
        verify(!after[0].git)
        var same = installed(Extensions.parseCheck(line([timerId, "aaaa", "aaaa", "x"])))
        verify(!same[1].updateAvailable); verify(same[1].checked)
        var offline = installed(Extensions.parseCheck(line([timerId, "aaaa", "", "x"])))
        verify(!offline[1].updateAvailable); verify(!offline[1].checked); verify(offline[1].git)
    }

    function test_commands_are_literal_argv_through_omarchy_scripts() {
        compare(Extensions.installArgv(omarchy, "https://github.com/evindor/keystroke-timer.git"), ["/usr/share/omarchy/bin/omarchy-plugin-add", "https://github.com/evindor/keystroke-timer.git", "--yes"])
        compare(Extensions.updateArgv(omarchy, "a.b"), ["/usr/share/omarchy/bin/omarchy-plugin-update", "a.b", "--yes"])
        compare(Extensions.updatedText("Timer"), "Updated Timer · omarchy-restart-shell loads its new code")
        compare(Extensions.removeArgv(omarchy, "a.b"), ["/usr/share/omarchy/bin/omarchy-plugin-remove", "a.b", "--yes"])
        var check = Extensions.checkArgv("/home/me", ["a.b", "c.d; rm -rf /"])
        compare(check.slice(0, 5), ["env", "GIT_TERMINAL_PROMPT=0", "GIT_SSH_COMMAND=ssh -oBatchMode=yes", "bash", "-c"])
        compare(check.slice(-3), ["/home/me/.config/omarchy/plugins", "a.b", "c.d; rm -rf /"])
        verify(check[5].indexOf("fetch --quiet origin HEAD") > 0)
        verify(check[5].indexOf("merge") < 0)
        compare(Extensions.fetchArgv("https://x/y.json"), ["curl", "-fsSL", "--max-time", "20", "--", "https://x/y.json"])
        compare(Extensions.parseAdded("Cloning into '/x'...\nAdded io.github.evindor.keystroke-timer into /home/me/.config/omarchy/plugins/io.github.evindor.keystroke-timer\nEnabled io.github.evindor.keystroke-timer\n"), "io.github.evindor.keystroke-timer")
        compare(Extensions.parseAdded("omarchy-plugin-add: refusing to add: validation failed"), "")
        var job = { kind: "install", id: "", name: "Timer", label: "Installing Timer", done: "Installed Timer", url: "u", startedAt: 5 }
        var argv = Extensions.jobArgv("/run/user/1000/keystroke/extensions", job, omarchy, ["/usr/share/omarchy/bin/omarchy-plugin-add", "u", "--yes"])
        compare(argv.slice(0, 2), ["bash", "-c"])
        compare(argv.slice(3, 5), ["keystroke-extension-job", "/run/user/1000/keystroke/extensions"])
        compare(JSON.parse(argv[5]), job)
        compare(argv.slice(6), ["/usr/share/omarchy/bin/omarchy-notification-send", "Installed Timer", "/usr/share/omarchy/bin/omarchy-plugin-add", "u", "--yes"])
        compare(Extensions.jobArgv("/d", { kind: "check", label: "Checking" }, omarchy, ["git"])[7], "")   // checks stay silent
        compare(Extensions.parseResult("junk"), null)
        compare(Extensions.parseResult(JSON.stringify({ code: 0 })), null)
        compare(Extensions.parseResult(JSON.stringify({ job: job, code: "1", output: "boom" })), { job: job, code: 1, output: "boom" })
    }

    function test_screen_lists_installed_actions_and_discoveries() {
        var discover = Extensions.parseIndex(JSON.stringify({ version: 1, extensions: [
            { id: timerId, name: "Timer", repo: "evindor/keystroke-timer" },
            { id: "x.keystroke-spotify", name: "Spotify", description: "Control Spotify", author: "X", repo: "x/keystroke-spotify" }
        ] }))
        var state = { installed: installed(), discover: discover, job: null, fetching: false, checked: "", error: "", marketplace: true }
        var rows = ranked(Extensions.screenRows("", state), "")
        compare(titles(rows), ["Hello", "Timer", "Check for updates", "Refresh catalog", "Spotify"])
        compare(rows[0].accessory, "Off")
        compare(rows[1].accessory, "On")
        compare(rows[1].action.scope, "extensions/" + timerId)
        compare(rows[1].altAction.type, "setting"); compare(rows[1].altAction.value, false); compare(rows[1].altAction.path, ["providers", timerId])
        compare(rows[0].altAction.value, true)
        state.installed = installed({}, [{ pluginId: timerId, message: "Service.qml:3:1 Syntax error" }])
        var sick = ranked(Extensions.screenRows("", state), "")
        compare(sick[1].accessory, "Needs attention")
        verify(sick[1].subtitle.indexOf("Syntax error") > 0)
        compare(rows[4].verb, "Install")
        compare(rows[4].action, { type: "ext", op: "install", id: "x.keystroke-spotify", name: "Spotify", url: "https://github.com/x/keystroke-spotify.git" })
        verify(rows[4].confirm.indexOf("unsandboxed") > 0)
        compare(rows[4].altAction.type, "url")
        compare(rows[4].badge, "index")

        var found = ranked(Extensions.screenRows("spot", state), "spot")
        compare(titles(found), ["Spotify"])
        var updates = ranked(Extensions.screenRows("upd", state), "upd")
        compare(titles(updates)[0], "Check for updates")

        state.installed = installed(Extensions.parseCheck(line([timerId, "a", "b", "r"])))
        var pending = ranked(Extensions.screenRows("", state), "")
        compare(pending[1].accessory, "Update available")
        compare(pending[2].title, "Update all (1)")
        compare(pending[2].action.op, "update-all")

        state.job = { kind: "install", id: "", label: "Installing Spotify", detail: "…" }
        var busy = ranked(Extensions.screenRows("", state), "")
        compare(busy[0].title, "Installing Spotify"); verify(busy[0].disabled)
    }

    function test_typed_git_url_offers_an_install_row() {
        var state = { installed: [], discover: [], job: null }
        var rows = ranked(Extensions.screenRows("evindor/keystroke-timer", state), "evindor/keystroke-timer")
        compare(rows[0].title, "Install from https://github.com/evindor/keystroke-timer.git")
        compare(rows[0].tier, "answer")
        compare(rows[0].action.url, "https://github.com/evindor/keystroke-timer.git")
        verify(rows[0].confirm.length > 0)
        var none = Extensions.screenRows("chrome", state).filter(function(r) { return r.id === "install-url" })
        compare(none.length, 0)
        var empty = ranked(Extensions.screenRows("", state), "")
        compare(empty[0].title, "No extensions installed")
    }

    function test_detail_screen_covers_enable_problem_update_repo_and_remove() {
        var e = installed(Extensions.parseCheck(line([timerId, "a", "b", "https://github.com/evindor/keystroke-timer.git"])))[1]
        var rows = ranked(Extensions.detailRows("", e, { job: null }), "")
        compare(titles(rows), ["Enabled", "Settings", "Update now", "Open repository", "Remove", "Timer v1.0.0"])
        compare(rows[0].action, { type: "setting", path: ["providers", e.id], key: "enabled", value: false, schema: { key: "enabled", type: "boolean" } })
        compare(rows[0].subtitle, "Include this extension's results in Keystroke")
        compare(rows[1].action.scope, "settings/" + timerId)
        compare(rows[2].action, { type: "ext", op: "update", id: e.id, name: "Timer" })
        compare(rows[3].action, { type: "url", url: "https://github.com/evindor/keystroke-timer" })
        compare(rows[4].action, { type: "ext", op: "remove", id: e.id, name: "Timer" })
        verify(rows[4].confirm.indexOf("Remove Timer") === 0)
        verify(rows[4].subtitle.indexOf("Stops the extension") === 0)
        var fresh = installed()[1]
        var rows2 = Extensions.detailRows("", fresh, {})
        compare(rows2[2].title, "Check for updates")
        compare(rows2[2].action, { type: "ext", op: "check", id: fresh.id })
        var hello = installed(Extensions.parseCheck(line(["example.keystroke-hello", "", "", ""])))[0]
        var rows3 = Extensions.detailRows("", hello, {})
        compare(rows3[0].action.value, true)
        compare(rows3[2].title, "Not git-managed")
        var sick = installed({}, [{ pluginId: timerId, message: "Service.qml:3:1 Syntax error" }])[1]
        var rows4 = ranked(Extensions.detailRows("", sick, {}), "")
        compare(titles(rows4).slice(0, 3), ["Enabled", "Needs attention", "Settings"])
        compare(rows4[1].subtitle, "Service.qml:3:1 Syntax error"); verify(rows4[1].disabled)
        compare(ranked(Extensions.detailRows("rem", e, {}), "rem")[0].title, "Remove")
    }

    function test_scope_ids() {
        compare(Extensions.scopeId(""), null)
        compare(Extensions.scopeId("extensions"), "")
        compare(Extensions.scopeId("extensions/a.b"), "a.b")
        compare(Extensions.scopeId("settings/a"), null)
    }

    function test_loaded_provider_decorates_its_rows_with_its_own_icon_and_examples() {
        var e = installed()[1]
        compare(e.name, "Timer")
        var plain = Extensions.installedRow(e, true)
        compare(plain.icon, Extensions.ICON)
        compare(plain.iconSource, "")
        Extensions.decorate(e, { icon: "C", iconSource: "file:///plugins/calpad/assets/calpad.svg", color: "#26a269" }, ["price = 10", "$120 - 30%"])
        var row = Extensions.installedRow(e, true)
        compare(row.icon, "C")
        compare(row.iconSource, "file:///plugins/calpad/assets/calpad.svg")
        compare(row.tint, "#26a269")
        var detail = Extensions.detailRows("", e, null)
        var about = detail.filter(function(r) { return r.id === timerId + "/about" })[0]
        compare(about.iconSource, "file:///plugins/calpad/assets/calpad.svg")
        var patterns = detail.filter(function(r) { return r.id === timerId + "/patterns" })[0]
        verify(patterns && patterns.disabled)
        compare(patterns.title, "Answers queries like price = 10 · $120 - 30%")
        // Nothing declared: no examples row, generic icon kept for the glyph.
        var bare = installed()[0]
        Extensions.decorate(bare, { icon: "" }, [])
        compare(Extensions.installedRow(bare, true).icon, Extensions.ICON)
        compare(Extensions.detailRows("", bare, null).filter(function(r) { return r.id.indexOf("/patterns") > 0 }).length, 0)
    }
}
