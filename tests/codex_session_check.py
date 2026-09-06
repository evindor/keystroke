#!/usr/bin/env python3
"""Exercise production QML transport/session and view against a fake server."""
import os,json,pathlib,tempfile,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-codex-test-') as temp:
 p=pathlib.Path(temp);(p/'.local/state/keystroke/questions').mkdir(parents=True)
 (p/'codex').symlink_to(root/'codex');(p/'qs').symlink_to('/usr/share/omarchy/shell')
 for name in ['ui','voice']: (p/name).symlink_to(root/name)
 for name in ['Commons','Ui']: (p/name).symlink_to('/usr/share/omarchy/shell/'+name)
 (p/'shell.qml').write_text('''import QtQuick
import QtTest
import Quickshell
import "codex"
ShellRoot {
 id: test
 property int stage: 0
 function check(value,message) { if (!value) { console.log("FAIL",message); Qt.quit(); throw Error(message) } }
 CodexSession { id: session; home: %s; server.command: ["python3",%s] }
 Window { visible: true; width: 700; height: 580
   ConversationView { id: view; anchors.fill: parent; session: session; host: stub }
 }
 QtObject { id: stub
   property color foreground: "#eeeeee"; property color muted: "#aaaaaa"; property color accent: "#aabbff"; property color background: "#222222"
   property var voice: ({active:false,phase:"idle",level:0,history:[]})
   function cancel() { session.dismiss() }
   function isModifierKey(key) { return key===Qt.Key_Shift }
   function voiceCancel() { voice = ({active:false,phase:"idle",level:0,history:[]}) }
   function voiceStop() { voice = ({active:true,phase:"transcribing",level:0,history:[]}) }
 }
 TestCase { id: keys; name: "ConversationKeys"; when: false }
 Timer { interval: 100; running: true; onTriggered: {
   session.newQuestion("");view.beginVoice();view.transcript("Open the document, please.",false)
   view.transcript("Open the document, please. Keep two lines!\\nSecond line.",true)
   test.check(session.draft.indexOf("Open the document,")===0 && session.draft.indexOf("Second line.")>0,"voice preserves complete prose")
   var editor=keys.findChild(view,"composer");test.check(!!editor,"composer is reachable")
   view.focusInput();stub.voice=({active:true,phase:"listening",level:0,history:[]})
   keys.keyClick(Qt.Key_Return);test.check(!session.busy && stub.voice.phase==="transcribing","Enter finishes voice without sending")
   keys.keyClick(Qt.Key_A);test.check(!stub.voice.active,"manual correction cancels voice")
   session.draft="first question";view.focusInput();keys.keyClick(Qt.Key_Return);test.stage=1
 } }
 Timer { interval: 50; repeat: true; running: true; onTriggered: {
   if (test.stage===1 && !session.busy && session.messages.length) {
     test.check(session.answer()==="Hello world","early deltas and final reconcile");
     session.handleRequest(900,"item/commandExecution/requestApproval",{threadId:session.threadId,command:"bad"});test.check(!session.approvals.length,"quick mode rejects local tool approvals");
     session.phase="running";session.mode="agent";session.turnId="approval-test";
     session.handleRequest(901,"item/fileChange/requestApproval",{threadId:session.threadId,turnId:"approval-test",reason:"fixture permission"});test.check(session.approvals.length===1,"agent approval routed");
     keys.keyClick(Qt.Key_Return);test.check(!session.approvals.length,"decline resolves approval");session.phase="idle";session.mode="quick";session.turnId="";
     view.grabToImage(function(result) { result.saveToFile("/tmp/keystroke-codex-preview.png") }); test.check(session.recent.length===1,"durable recent index")
     session.draft="slow question";session.submit();test.stage=2
   } else if(test.stage===2 && session.phase==="running") {session.stop();test.stage=3}
   else if(test.stage===3 && !session.busy) {
     test.check(session.activity==="Stopped","stop acknowledged");session.newQuestion("next question");test.stage=4
   } else if(test.stage===4 && !session.busy) {test.stage=5;session.requestHandoff()}
   else if(test.stage===6 && !session.busy && session.error) {
     test.check(session.draft==="crash now","disconnect preserves unsent or uncertain draft");
     test.check(!!session.threadId,"disconnect retains saved conversation");test.stage=7;session.requestHandoff()
   }
 } }
 Connections { target: session
   function onHandoffReady(id) {
     test.check(!session.server.ready,"server releases writer before handoff")
     if(test.stage===5) {test.stage=6;session.newQuestion("crash now");return}
     test.check(test.stage===7,"handoff waits");console.log("PASS Codex stream, voice keys, approvals, cancel, disconnect, writer release and view");Qt.quit()
   }
 }
 Timer { interval: 12000; running: true; onTriggered: {console.log("FAIL timeout",test.stage,session.phase,session.error);Qt.quit()} }
}'''%(json.dumps(str(p)),json.dumps(str(root/'tests/codex_fake_server.py'))))
 env=os.environ.copy();env.pop('DISPLAY',None);env.update(HOME=str(p),XDG_RUNTIME_DIR=str(p),QML_IMPORT_PATH=str(p),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_BACKEND='software')
 r=subprocess.run(['quickshell','-p',str(p/'shell.qml')],env=env,text=True,capture_output=True,timeout=18)
 out=r.stdout+r.stderr
 assert 'PASS Codex' in out and 'FAIL' not in out,out
 assert 'TypeError' not in out and 'ReferenceError' not in out,out
 print(out)
