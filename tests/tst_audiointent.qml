import QtQuick
import QtTest
import "../core/AudioIntent.js" as AudioIntent
import "../voice"
TestCase {
  name: "AudioIntent"
  IntentSession { id: session }
  function test_audio_result_cannot_override_an_edit_or_cancel() {
    session.begin({items:[{title:"Browser"}], rows:[{title:"Browser"}]})
    session.update("Open the browser", false)
    session.acceptAudio(1, "Open the browser", 230)
    compare(session.pick.title, "Browser")
    session.update("Do not open the browser", false)
    session.acceptAudio(1, "Open the browser", 230)
    compare(session.pick, null)
    session.acceptAudio(0, "Do not open the browser", 250)
    compare(session.pick, null)
    session.cancel()
    session.acceptAudio(1, "Do not open the browser", 250)
    compare(session.pick, null)
  }
  function test_prompt_prefix_is_identical_for_warm_and_audio() {
    var items = [{title:"Browser",detail:"Web"}]
    compare(AudioIntent.warmBody(items).messages[0].content, AudioIntent.prompt(items))
    verify(AudioIntent.prompt(items).indexOf("negated actions") >= 0)
    verify(AudioIntent.validIndex(1,1))
    verify(!AudioIntent.validIndex(1.5,2))
    verify(!AudioIntent.validIndex("1",2))
  }
}
