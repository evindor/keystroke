#!/usr/bin/env python3
"""Load the locale adapter with no Omarchy 4.5 types and a different OS choice."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='keystroke-legacy-i18n-') as temp:
    work = Path(temp)
    shutil.copytree(root/'i18n',work/'i18n')
    # Deliberately no I18n or Translations in the older shell's Commons module.
    (work/'qs/Commons').mkdir(parents=True)
    (work/'qs/Commons/qmldir').write_text('module qs.Commons\n')
    (work/'language').write_text('ar\n')
    (work/'shell.qml').write_text('''import QtQuick
import Quickshell
import "i18n" as Localization
ShellRoot {
  function check(ok, message) { if (!ok) { console.log("FAIL",message); Qt.quit(); throw Error(message) } }
  Localization.Locale {
    id: locale
    directory: Qt.resolvedUrl("i18n")
    omarchyPath: Quickshell.env("HOME") + "/old-omarchy"
    systemLocale: "de_AT.UTF-8"
  }
  Localization.Locale {
    id: environmentLocale
    directory: Qt.resolvedUrl("i18n")
    omarchyPath: Quickshell.env("HOME") + "/old-omarchy"
  }
  Timer { interval:100; running:true; onTriggered: {
    check(!locale.nativeActive, "no new API was loaded")
    check(environmentLocale.language === "de-AT", "LC_MESSAGES takes precedence over LANG")
    check(locale.language === "de-AT", "system locale wins over the Omarchy language file")
    check(locale.t("Appearance") === "Darstellung", "regional locale uses base German catalog")
    check(locale.tn("%1 extension",1) === "%1 Erweiterung", "legacy German singular")
    check(locale.tn("%1 extension",2) === "%1 Erweiterungen", "legacy German plural")
    check(locale.formatNumber(1.5) === "1,5", "legacy number locale")
    check(!locale.rightToLeft, "the unrelated Arabic Omarchy choice was ignored")
    locale.systemLocale = "C.UTF-8"
    check(locale.language === "en" && locale.t("Appearance") === "Appearance", "C locale uses English")
    console.log("PASS legacy locale without Omarchy 4.5 types")
    Qt.quit()
  } }
}
''')
    env = dict(os.environ,LC_ALL="",LC_MESSAGES="de_AT.UTF-8",LANG="en_US.UTF-8",HOME=str(work),XDG_RUNTIME_DIR=str(work),OMARCHY_LANGUAGE_FILE=str(work/'language'),QT_QPA_PLATFORM='offscreen',QT_QPA_PLATFORMTHEME='generic',QT_QUICK_BACKEND='software',QML_IMPORT_PATH=str(work))
    env.pop('DISPLAY',None)
    env.pop('WAYLAND_DISPLAY',None)
    result=subprocess.run(['quickshell','-p',str(work/'shell.qml')],env=env,capture_output=True,text=True,timeout=8)
    output=result.stdout+result.stderr
    assert 'PASS legacy locale without Omarchy 4.5 types' in output and 'FAIL' not in output,output
    assert 'TypeError' not in output and 'ReferenceError' not in output,output
    print('PASS Omarchy 4.x fallback: no new QML types, system locale, regional/English fallback, plurals and number formatting')
