import QtQuick
import Quickshell
import Quickshell.Io
import "core/TOTP.js" as TOTPModel

// TOTP: Time-Based One-Time Password extension for the Keystroke command palette.
//
// Generates 6-8 digit authenticator codes, searches saved accounts,
// supports quick one-off OTPs, adding/editing accounts from Base32 secrets or
// otpauth:// URIs, and exporting/importing backups.
QtObject {
  id: root
  property var shell: null
  property var extension: null
  property string omarchyPath: Quickshell.env("OMARCHY_PATH")
  readonly property string home: Quickshell.env("HOME")
  property var host: null
  property var settings: ({ notifyOnCopy: true, searchInRoot: false, autoBackup: false, showBackupPassphrase: false, defaultDigits: 6, defaultPeriod: 30 })
  property double now: Date.now()
  readonly property string key: extension && extension.id ? String(extension.id) : "totp"
  readonly property string stateDir: (Quickshell.env("XDG_STATE_HOME") || root.home + "/.local/state") + "/keystroke/totp"
  readonly property string accountsPath: root.stateDir + "/accounts.json"
  readonly property string backupPath: root.stateDir + "/backup.json"

  property var accounts: []
  property bool loaded: false

  readonly property var provider: ({
    apiVersion: 1,
    name: TOTPModel.NAME,
    icon: TOTPModel.ICON,
    iconSource: String(Qt.resolvedUrl("assets/icon.svg")),
    color: TOTPModel.COLOR,
    description: "Generate and copy time-based one-time passwords: totp",
    prefix: "totp",
    patterns: TOTPModel.PATTERNS,
    settings: TOTPModel.SETTINGS,
    view: root.view,
    query: function(ctx) { return root.query(ctx) },
    activate: function(row, ctx) { return root.activate(row, ctx) },
    opened: function() {
      root.now = Date.now()
      accFile.reload()
    }
  })

  readonly property Component view: Component { AccountFormView { service: root } }
  property var editingAccount: null

  // Ensure state directory exists on load
  readonly property Process dirEnsurer: Process {
    command: ["mkdir", "-p", root.stateDir]
  }

  // Persistent storage of TOTP accounts
  readonly property FileView accountsFile: FileView {
    id: accFile
    path: root.accountsPath
    printErrors: false
    watchChanges: true
    atomicWrites: true
    onLoaded: {
      root.accounts = TOTPModel.readAccounts(text())
      root.loaded = true
    }
    onLoadFailed: {
      root.accounts = []
      root.loaded = true
    }
    onFileChanged: reload()
  }

  readonly property string helperCli: decodeURIComponent(String(Qt.resolvedUrl("bin/totp-cli")).replace(/^file:\/\//, ""))

  readonly property Process backupWorker: Process {
    onExited: function(code) {
      if (code === 0 && root.host && root.host.opened) {
        root.host.requery({ catalog: false, provider: root.key })
      }
    }
  }

  function triggerAutoBackup() {
    var s = root.settings || {}
    var dir = String(s.backupDirectory || "").trim()
    var pass = String(s.backupPassphrase || "").trim()
    if (!dir && !pass) return
    if (!dir || !pass || pass.length < 8) return
    var targetPath = TOTPModel.resolveBackupPath(dir, root.home)
    backupWorker.command = [root.helperCli, "export", targetPath, "--passphrase", pass]
    backupWorker.running = true
  }

  function save(list) {
    root.accounts = list
    accountsFile.setText(TOTPModel.serializeAccounts(list))
    root.triggerAutoBackup()
  }

  function saveAccount(acc) {
    var list = root.accounts || []
    var exists = false
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === acc.id) {
        exists = true
        break
      }
    }
    var updated = exists ? TOTPModel.updateAccount(list, acc) : TOTPModel.addAccount(list, acc)
    root.save(updated)
    root.editingAccount = null
    if (root.host) {
      root.host.statusMessage = exists ? "Updated " + acc.name : "Added " + acc.name
      root.host.goBack()
      if (root.host.opened) root.host.requery({ catalog: false, provider: root.key })
    }
  }

  // 1-second clock updates live remaining seconds and OTP codes when palette is opened
  readonly property Timer clock: Timer {
    interval: 1000
    repeat: true
    running: true
    onTriggered: {
      root.now = Date.now()
      var h = root.host
      if (!h || !h.opened) return
      var inScope = h.scope === root.key || (h.scope && h.scope.indexOf(root.key) === 0)
      var hasTotpRows = false
      if (h.rows && h.rows.length) {
        for (var i = 0; i < h.rows.length; i++) {
          if (h.rows[i].providerKey === root.key) {
            hasTotpRows = true
            break
          }
        }
      }
      if (inScope || hasTotpRows) {
        h.requery({ catalog: false, provider: root.key })
      }
    }
  }

  readonly property Connections hostWatch: Connections {
    target: root.host
    ignoreUnknownSignals: true
    function onConfigChanged() {
      var h = root.host
      if (!h || typeof h.providerSettings !== "function") return
      root.settings = h.providerSettings(root.key)
    }
  }

  function attach(ctx) {
    if (ctx && ctx.host) root.host = ctx.host
    if (ctx && ctx.settings) root.settings = ctx.settings
  }

  function query(ctx) {
    root.attach(ctx)
    root.now = Date.now()
    var scoped = ctx.scope === root.key ? root.key : (ctx.scope && ctx.scope.indexOf(root.key) === 0 ? ctx.scope : "")
    if (ctx.scope && !scoped) return []
    var viaCommand = !!ctx.command
    var q = viaCommand ? ctx.command.rest : ctx.query
    return TOTPModel.rows(q, root.accounts, ctx.settings, root.now, scoped, root.key, viaCommand, ctx.patterns)
  }

  function activate(row, ctx) {
    root.attach(ctx)
    var effect = ctx.alternate && row.altAction ? row.altAction : row.action
    if (!effect) return effect

    if (effect.type === "totp-open-edit") {
      root.editingAccount = effect.account
      return { type: "provider-view", provider: root.key }
    }

    if (effect.type === "totp-open-add") {
      root.editingAccount = null
      return { type: "provider-view", provider: root.key }
    }

    if (effect.type === "totp-add") {
      var updated = TOTPModel.addAccount(root.accounts, effect.account)
      root.save(updated)
      if (root.host && root.host.opened) root.host.requery({ catalog: false, provider: root.key })
      return {
        type: "compound",
        actions: [
          {
            type: "notify",
            glyph: "󰌆",
            headline: "Account added",
            body: effect.account.name + (effect.account.issuer ? " (" + effect.account.issuer + ")" : "")
          },
          { type: "noop" }
        ]
      }
    }

    if (effect.type === "totp-remove") {
      var removed = TOTPModel.removeAccount(root.accounts, effect.id)
      root.save(removed)
      if (root.host) {
        if (root.host.scope && root.host.scope.indexOf(root.key + "/account/" + effect.id) === 0) {
          root.host.goBack()
        }
        root.host.statusMessage = "Account deleted"
        if (root.host.opened) root.host.requery({ catalog: false, provider: root.key })
      }
      return {
        type: "compound",
        actions: [
          {
            type: "notify",
            glyph: "󰌆",
            headline: "Account deleted",
            body: "Account has been permanently deleted"
          },
          { type: "noop" }
        ]
      }
    }

    if (effect.type === "totp-export") {
      var s = root.settings || {}
      var pass = String(s.backupPassphrase || "").trim()
      var dir = String(s.backupDirectory || "").trim()
      var targetPath = dir ? TOTPModel.resolveBackupPath(dir, root.home) : root.backupPath
      if (pass && pass.length >= 8) {
        backupWorker.command = [root.helperCli, "export", targetPath, "--passphrase", pass]
        backupWorker.running = true
        return {
          type: "compound",
          actions: [
            {
              type: "notify",
              glyph: "󰌆",
              headline: "Encrypted backup exported",
              body: "Saved to " + targetPath
            },
            { type: "noop" }
          ]
        }
      } else {
        backupWorker.command = [root.helperCli, "export", targetPath]
        backupWorker.running = true
        return {
          type: "compound",
          actions: [
            {
              type: "notify",
              glyph: "󰌆",
              headline: "Backup exported",
              body: "Saved to " + targetPath
            },
            { type: "noop" }
          ]
        }
      }
    }

    if (effect.type === "totp-import") {
      var s = root.settings || {}
      var pass = String(s.backupPassphrase || "").trim()
      var dir = String(s.backupDirectory || "").trim()
      var targetPath = dir ? TOTPModel.resolveBackupPath(dir, root.home) : root.backupPath
      var cmd = [root.helperCli, "import", targetPath]
      if (pass) cmd.push("--passphrase", pass)
      backupWorker.command = cmd
      backupWorker.running = true
      return {
        type: "compound",
        actions: [
          {
            type: "notify",
            glyph: "󰌆",
            headline: "Backup imported",
            body: "Importing accounts from " + targetPath
          },
          { type: "noop" }
        ]
      }
    }

    return effect
  }

  Component.onCompleted: {
    dirEnsurer.running = true
  }
}
