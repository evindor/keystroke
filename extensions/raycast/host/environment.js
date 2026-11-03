"use strict";

const fs = require("fs");
const path = require("path");

const state = {
  extensionDir: "",
  extensionName: "",
  commandName: "",
  assetsPath: "",
  supportPath: "",
  appearance: "dark",
  launchType: "userInitiated",
  packageJson: null,
  command: null,
  preferences: {},
};

function loadPreferences(pkg, command, dir) {
  const prefs = {};
  const all = []
    .concat(Array.isArray(pkg.preferences) ? pkg.preferences : [])
    .concat(command && Array.isArray(command.preferences) ? command.preferences : []);
  for (const pref of all) {
    if (!pref || !pref.name) continue;
    if (pref.default !== undefined) prefs[pref.name] = pref.default;
    else if (pref.type === "checkbox") prefs[pref.name] = false;
    else prefs[pref.name] = "";
  }
  const file = path.join(dir, "preferences.json");
  if (fs.existsSync(file)) {
    try {
      const override = JSON.parse(fs.readFileSync(file, "utf8"));
      Object.assign(prefs, override);
    } catch (err) {
      console.error("preferences.json:", err.message);
    }
  }
  return prefs;
}

function init(extensionDir, commandName) {
  const pkgPath = path.join(extensionDir, "package.json");
  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  const command = (pkg.commands || []).find((c) => c.name === commandName) || { name: commandName, mode: "view" };
  state.extensionDir = extensionDir;
  state.extensionName = pkg.name || path.basename(extensionDir);
  state.commandName = commandName;
  state.assetsPath = path.join(extensionDir, "assets");
  state.supportPath = path.join(extensionDir, "support");
  state.packageJson = pkg;
  state.command = command;
  state.preferences = loadPreferences(pkg, command, extensionDir);
  fs.mkdirSync(state.supportPath, { recursive: true });
  return { pkg, command };
}

function environment() {
  return {
    extensionName: state.extensionName,
    commandName: state.commandName,
    commandMode: (state.command && state.command.mode) || "view",
    assetsPath: state.assetsPath,
    supportPath: state.supportPath,
    isDevelopment: false,
    raycastVersion: "1.104.25",
    appearance: state.appearance,
    textSize: "medium",
    launchType: state.launchType,
    canAccess: () => false,
    theme: state.appearance,
    subscribe(callback) {
      if (typeof callback !== "function") return () => {};
      return () => {};
    },
  };
}

function getPreferenceValues() {
  return { ...state.preferences };
}

function setAppearance(value) {
  if (value) state.appearance = value;
}

module.exports = { state, init, environment, getPreferenceValues, setAppearance, loadPreferences };
