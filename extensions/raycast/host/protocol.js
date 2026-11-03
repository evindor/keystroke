"use strict";

const readline = require("readline");

let seq = 0;

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

function log(...args) {
  console.error(...args);
}

function nextId() {
  seq += 1;
  return seq;
}

const pending = new Map();

function request(method, params) {
  const id = nextId();
  return new Promise((resolve) => {
    pending.set(id, resolve);
    send({ type: "request", id, method, params: params || {} });
  });
}

function handleReply(msg) {
  const resolve = pending.get(msg.id);
  if (resolve) {
    pending.delete(msg.id);
    resolve(msg.result);
  }
}

function listen(onMessage) {
  const rl = readline.createInterface({ input: process.stdin });
  rl.on("line", (line) => {
    const text = String(line || "").trim();
    if (!text) return;
    let msg;
    try {
      msg = JSON.parse(text);
    } catch (err) {
      log("bad stdin json:", err.message);
      return;
    }
    if (msg && msg.type === "reply") {
      handleReply(msg);
      return;
    }
    try {
      const result = onMessage(msg);
      if (result && typeof result.then === "function") {
        result.catch((err) => {
          log("handler error:", err && err.stack ? err.stack : err);
          send({ type: "error", message: err && err.message ? err.message : String(err) });
        });
      }
    } catch (err) {
      log("handler error:", err && err.stack ? err.stack : err);
      send({ type: "error", message: err && err.message ? err.message : String(err) });
    }
  });
  return rl;
}

module.exports = { send, log, request, listen };
