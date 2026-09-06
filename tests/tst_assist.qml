import QtQuick
import QtTest
import "../voice"

TestCase {
    id: test
    name: "VoiceAssistant"
    property var requests: []
    property var items: [{ title: "Chrome" }, { title: "Lock Screen" }]
    property var rows: [{ uid: "chrome", title: "Chrome" }, { uid: "lock", title: "Lock Screen" }]
    Assist {
        id: client
        createRequest: function() { return test.makeRequest() }
        requestTimeout: 1000
        warmTimeout: 1000
    }
    IntentSession { id: session; assistant: client; partialInterval: 40 }
    SignalSpy { id: answers; target: client; signalName: "answered" }
    SignalSpy { id: failures; target: client; signalName: "failed" }

    function makeRequest() {
        return {
            readyState: 0, status: 0, responseText: "", url: "", body: null, aborted: false,
            onreadystatechange: null,
            open: function(method, url) { this.url = url },
            setRequestHeader: function() {},
            send: function(body) { this.body = body ? JSON.parse(body) : null; test.requests = test.requests.concat([this]) },
            abort: function() { this.aborted = true; this.readyState = 4; this.status = 0; if (this.onreadystatechange) this.onreadystatechange() }
        }
    }
    function reply(xhr, body, status) {
        xhr.responseText = JSON.stringify(body)
        xhr.status = status === undefined ? 200 : status
        xhr.readyState = 4
        xhr.onreadystatechange()
    }
    function answer(xhr, value) { reply(xhr, { choices: [{ message: { content: value } }] }) }
    function init() {
        session.cancel()
        client.enabled = false
        requests = []
        client.requestTimeout = 1000; client.warmTimeout = 1000
        client.enabled = true
        reply(requests[0], { status: "ok" })
        reply(requests[1], { model_path: "test.gguf" })
        requests = []
        answers.clear(); failures.clear()
    }
    function cleanup() { session.cancel(); client.enabled = false }

    function test_warmup_is_deduplicated_and_latest_command_waits_for_its_slot() {
        client.warm(items); client.warm(items)
        compare(requests.length, 1)
        client.ask(items, "old", rows); client.ask(items, "new", rows)
        compare(requests.length, 1)
        answer(requests[0], "1")
        compare(requests.length, 2)
        compare(requests[1].body.messages[1].content, "new")
        answer(requests[1], "2")
        compare(answers.count, 1)
        compare(answers.signalArguments[0][2], "new")
        compare(answers.signalArguments[0][4][1].uid, "lock")
        client.warm(items)
        compare(requests.length, 2)
    }
    function test_partials_coalesce_without_aborting_work() {
        client.ask(items, "a", rows)
        client.ask(items, "b", rows)
        client.ask(items, "c", rows)
        compare(requests.length, 1)
        verify(!requests[0].aborted)
        answer(requests[0], "1")
        compare(requests.length, 2)
        compare(requests[1].body.messages[1].content, "c")
        answer(requests[1], "2")
        verify(!client.busy)
    }
    function test_cancel_blocks_late_callbacks_and_drops_queued_work() {
        client.ask(items, "a", rows); client.ask(items, "b", rows)
        var old = requests[0]
        client.cancel()
        verify(old.aborted)
        answer(old, "2")
        compare(answers.count, 0); compare(failures.count, 0)
        compare(requests.length, 1); verify(!client.busy)
    }
    function test_stale_health_response_cannot_revive_disabled_client() {
        client.check(true)
        var old = requests[0]
        client.enabled = false
        reply(old, { status: "ok" })
        verify(!client.available); compare(client.modelName, "")
    }
    function test_endpoint_change_cancels_old_warmup() {
        client.warm(items)
        var old = requests[0]
        client.endpoint = "http://127.0.0.1:18782"
        answer(old, "1")
        compare(client.warmedStamp, "")
        verify(!client.available)
        client.endpoint = "http://127.0.0.1:18781"
    }
    function test_timeout_unblocks_the_newest_command() {
        client.requestTimeout = 40
        client.ask(items, "old", rows); client.ask(items, "new", rows)
        tryCompare(failures, "count", 1)
        compare(requests.length, 2)
        compare(requests[1].body.messages[1].content, "new")
        answer(requests[1], "1")
        verify(!client.busy)
    }
    function test_warmup_timeout_does_not_stall_commands_forever() {
        client.warmTimeout = 40
        client.warm(items); client.ask(items, "new", rows)
        tryVerify(function() { return requests.length === 2 })
        verify(requests[0].aborted)
        answer(requests[1], "1")
        compare(answers.count, 1)
    }
    function test_session_asks_while_speaking_and_reuses_final_answer() {
        session.begin({ items: items, rows: rows })
        session.update("Open Chrome", false)
        tryVerify(function() { return requests.length === 1 })
        answer(requests[0], "1")
        compare(session.pick.uid, "chrome")
        session.update("Open Chrome.", true)
        compare(requests.length, 1)
        compare(session.pick.uid, "chrome")
        compare(session.query, "Chrome")
    }
    function test_continuous_speech_does_not_restart_debounce_forever() {
        session.begin({ items: items, rows: rows })
        session.update("Open", false)
        wait(25)
        session.update("Open Chrome", false)
        wait(25)
        compare(requests.length, 1)
        compare(requests[0].body.messages[1].content, "Open Chrome")
    }
    function test_old_answer_never_replaces_revised_speech() {
        session.begin({ items: items, rows: rows })
        session.update("Lock screen", true)
        session.update("Open Chrome", true)
        answer(requests[0], "2")
        compare(session.pick, null)
        compare(requests.length, 2)
        answer(requests[1], "1")
        compare(session.pick.uid, "chrome")
    }
    function test_answer_uses_catalog_from_request_not_a_later_catalog() {
        session.begin({ items: items, rows: rows })
        session.update("Chrome", true)
        session.catalog = { items: [{ title: "Suspend" }], rows: [{ uid: "suspend", title: "Suspend" }] }
        answer(requests[0], "1")
        compare(session.pick.uid, "chrome")
    }
    function test_manual_edit_cancels_session_before_late_answer() {
        session.begin({ items: items, rows: rows })
        session.update("Lock screen", true)
        session.cancel()
        answer(requests[0], "2")
        verify(!session.active); compare(session.pick, null)
    }
    function test_disabling_assistant_removes_its_previous_pick() {
        session.begin({ items: items, rows: rows })
        session.update("Chrome", true)
        answer(requests[0], "1")
        compare(session.pick.uid, "chrome")
        client.enabled = false
        compare(session.pick, null)
    }
    function test_server_becoming_ready_warms_then_handles_current_speech() {
        client.available = false
        session.begin({ items: items, rows: rows })
        session.update("Chrome", true)
        compare(requests.length, 0)
        client.check(true)
        reply(requests[0], { status: "ok" })
        compare(requests.length, 2)
        verify(client.warming !== null)
        answer(requests[1], "1")
        compare(requests.length, 3)
        answer(requests[2], "1")
        compare(session.pick.uid, "chrome")
    }
    function test_empty_revision_does_not_leave_a_stale_request_key() {
        session.begin({ items: items, rows: rows })
        session.update("Chrome", true)
        session.update("", false)
        answer(requests[0], "1")
        compare(session.pick, null)
        session.update("Chrome", true)
        compare(requests.length, 2)
        answer(requests[1], "1")
        compare(session.pick.uid, "chrome")
    }
    function test_begin_recording_preserves_in_progress_warmup() {
        client.warm(items)
        session.begin({ items: items, rows: rows })
        verify(!requests[0].aborted)
        session.update("Chrome", true)
        compare(requests.length, 1)
        answer(requests[0], "1")
        compare(requests.length, 2)
    }
}
