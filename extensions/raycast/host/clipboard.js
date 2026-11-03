"use strict";

const { send, request } = require("./protocol");

function stringify(content) {
  if (content == null) return "";
  if (typeof content === "string") return content;
  if (typeof content === "number" || typeof content === "boolean") return String(content);
  if (content instanceof Date) return content.toISOString();
  try {
    return JSON.stringify(content);
  } catch {
    return String(content);
  }
}

const Clipboard = {
  async copy(content, _options) {
    const text = stringify(content);
    send({ type: "copy", text });
  },
  async paste(content) {
    const text = stringify(content);
    send({ type: "paste", text });
  },
  async readText() {
    const result = await request("clipboard.readText", {});
    if (result == null) return "";
    if (typeof result === "string") return result;
    if (typeof result === "object" && result.text != null) return String(result.text);
    return String(result);
  },
  async read() {
    const text = await Clipboard.readText();
    return { text };
  },
  async clear() {
    send({ type: "copy", text: "" });
  },
};

function open(target, _options) {
  let value = target;
  if (target && typeof target === "object") {
    value = target.target || target.path || target.name || target.url || "";
  }
  send({ type: "open", target: String(value || "") });
  return Promise.resolve();
}

function closeMainWindow(_options) {
  send({ type: "close" });
  return Promise.resolve();
}

function popToRoot(_options) {
  send({ type: "pop_to_root" });
  return Promise.resolve();
}

async function getApplications() {
  return [];
}

async function getFrontmostApplication() {
  return { name: "", path: "", bundleId: "" };
}

async function getSelectedText() {
  return "";
}

async function getSelectedFinderItems() {
  return [];
}

function trash(_path) {
  return Promise.resolve();
}

function showInFinder(target) {
  return open(target);
}

const Keyboard = {
  Shortcut: {},
};

const Application = {};

module.exports = {
  Clipboard,
  open,
  closeMainWindow,
  popToRoot,
  getApplications,
  getFrontmostApplication,
  getSelectedText,
  getSelectedFinderItems,
  trash,
  showInFinder,
  Keyboard,
  Application,
  stringify,
};
