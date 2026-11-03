"use strict";

const fs = require("fs");
const path = require("path");
const Module = require("module");
const React = require("react");
const { send, log, listen } = require("./protocol");
const env = require("./environment");
const api = require("./api");
const nav = require("./navigation");
const reconciler = require("./reconciler");

const reactEntry = require("react");
const jsxRuntime = require("react/jsx-runtime");
const jsxDevRuntime = require("react/jsx-dev-runtime");

const RAYCAST_API = "@" + "raycast/api";
const aliases = new Map([
  [RAYCAST_API, api],
  ["react", reactEntry],
  ["react/jsx-runtime", jsxRuntime],
  ["react/jsx-dev-runtime", jsxDevRuntime],
]);

global.__KEYSTROKE_RAYCAST_ALIASES = Object.fromEntries(aliases);

function aliased(request) {
  const table = global.__KEYSTROKE_RAYCAST_ALIASES || {};
  return Object.prototype.hasOwnProperty.call(table, request) ? table[request] : undefined;
}

const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (request, parent, isMain, options) {
  if (aliased(request) !== undefined) return request;
  return originalResolve.call(this, request, parent, isMain, options);
};

const originalLoad = Module._load;
Module._load = function (request, parent, isMain) {
  const hit = aliased(request);
  if (hit !== undefined) return hit;
  return originalLoad.apply(this, arguments);
};

if (typeof Module.registerHooks === "function") {
  Module.registerHooks({
    resolve(specifier, context, nextResolve) {
      if (aliases.has(specifier)) return { url: "raycast-host:" + specifier, shortCircuit: true };
      return nextResolve(specifier, context);
    },
    load(url, context, nextLoad) {
      if (typeof url === "string" && url.startsWith("raycast-host:")) {
        return { format: "commonjs", source: "module.exports = global.__KEYSTROKE_RAYCAST_ALIASES[decodeURIComponent(" + JSON.stringify(url.slice("raycast-host:".length)) + ")];", shortCircuit: true };
      }
      return nextLoad(url, context);
    },
  });
}

require.cache[RAYCAST_API] = { id: RAYCAST_API, filename: RAYCAST_API, loaded: true, exports: api };

function loadCommand(dir, name) {
  // Store zips ship <command>.js beside package.json (the layout Vicinae
  // runs). commands/<name>.js is the built-from-source layout.
  const candidates = [path.join(dir, name + ".js"), path.join(dir, "commands", name + ".js")];
  const file = candidates.find((candidate) => fs.existsSync(candidate));
  if (!file) throw new Error("Command bundle not found: " + candidates[0]);
  delete require.cache[require.resolve(file)];
  return require(file);
}

function renderError(message) {
  const el = React.createElement(api.Detail, {
    markdown: "# Error\n\n" + message,
    navigationTitle: "Error",
  });
  nav.reset(el);
  reconciler.mount(el);
}

async function runCommand(dir, name) {
  const abs = path.resolve(dir);
  const { command } = env.init(abs, name);
  api.__internal.refreshEnvironment();
  const mode = command.mode || "view";
  let mod;
  try {
    mod = loadCommand(abs, name);
  } catch (err) {
    log(err && err.stack ? err.stack : err);
    send({ type: "error", message: err && err.message ? err.message : String(err) });
    if (mode !== "no-view") renderError(err && err.message ? err.message : String(err));
    else send({ type: "exit" });
    return;
  }
  const exported = mod && mod.__esModule ? mod.default || mod : mod.default || mod;
  if (mode === "no-view") {
    try {
      await Promise.resolve(typeof exported === "function" ? exported() : exported);
    } catch (err) {
      log(err && err.stack ? err.stack : err);
      send({ type: "error", message: err && err.message ? err.message : String(err) });
    }
    send({ type: "exit" });
    setTimeout(() => process.exit(0), 30);
    return;
  }
  if (typeof exported !== "function") {
    const message = "Command default export is not a component";
    send({ type: "error", message });
    renderError(message);
    return;
  }
  mountView(React.createElement(exported));
}

/// A view's element on screen, kept up, and the panel's keys taken.
function mountView(element) {
  process.stdin.resume();
  setInterval(() => {}, 1e9);
  nav.reset(element);
  reconciler.mount(element);
  setTimeout(() => {
    const node = reconciler.getRoot && reconciler.getRoot();
    if (node) reconciler.initDropdown(node);
  }, 50);
  listen((msg) => {
    if (!msg || !msg.type) return;
    if (msg.type === "search") reconciler.setSearch(msg.text || "");
    else if (msg.type === "select") reconciler.setSelected(msg.id);
    else if (msg.type === "action") reconciler.runActionById(msg.id);
    else if (msg.type === "field") reconciler.setField(msg.id, msg.value);
    else if (msg.type === "pop") {
      const popped = nav.pop();
      if (!popped) send({ type: "pop_to_root" });
      else {
        const top = nav.top();
        if (top) reconciler.update(top);
      }
    }
  });
}

module.exports = { runCommand, loadCommand };
