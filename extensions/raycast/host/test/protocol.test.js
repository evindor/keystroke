"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { spawn } = require("node:child_process");
const path = require("path");
const store = require("../store");

const cli = path.join(__dirname, "..", "cli.js");
const fixture = path.join(__dirname, "fixture");

function start(args, env) {
  const child = spawn(process.execPath, [cli, ...args], {
    env: Object.assign({}, process.env, env || {}),
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = [];
  let buf = "";
  let cursor = 0;
  child.stdout.on("data", (chunk) => {
    buf += chunk.toString();
    let idx;
    while ((idx = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, idx).trim();
      buf = buf.slice(idx + 1);
      if (line) lines.push(JSON.parse(line));
    }
  });
  const stderr = [];
  child.stderr.on("data", (chunk) => stderr.push(chunk.toString()));
  return {
    child,
    lines,
    stderr,
    send(msg) {
      child.stdin.write(JSON.stringify(msg) + "\n");
    },
    async waitFor(pred, timeout = 5000) {
      const start = Date.now();
      while (Date.now() - start < timeout) {
        for (let i = cursor; i < lines.length; i += 1) {
          if (pred(lines[i])) {
            cursor = i + 1;
            return lines[i];
          }
        }
        await new Promise((resolve) => setTimeout(resolve, 20));
      }
      throw new Error("timeout. got " + JSON.stringify(lines) + " stderr " + stderr.join(""));
    },
  };
}

test("download URLs stay on Raycast hosts", () => {
  assert.equal(store.allowedDownload("https://extensions.raycast-releases.com/abc?verify=1"), true);
  assert.equal(store.allowedDownload("https://backend.raycast.com/api/v1/store_listings"), true);
  assert.equal(store.allowedDownload("http://extensions.raycast-releases.com/abc"), false);
  assert.equal(store.allowedDownload("https://evil.example/zip"), false);
  assert.equal(store.safeName("../dad"), "");
  assert.equal(store.extensionId("dad-jokes"), "store.raycast.dad-jokes");
});

test("a list command renders, filters, and copies", async () => {
  const runtime = process.env.KEYSTROKE_RAYCAST_RUNTIME;
  assert.ok(runtime, "KEYSTROKE_RAYCAST_RUNTIME must point at the runtime node_modules");
  const host = start(["run", fixture, "hello"], { NODE_PATH: runtime });
  const rendered = await host.waitFor((msg) => msg.type === "render" && msg.view && msg.view.kind === "list");
  const titles = rendered.view.sections.flatMap((section) => section.items.map((item) => item.title));
  assert.deepEqual(titles, ["Alpha", "Beta"]);
  host.send({ type: "search", text: "bet" });
  const filtered = await host.waitFor((msg) => {
    if (msg.type !== "render") return false;
    const items = msg.view.sections.flatMap((section) => section.items);
    return items.length === 1 && items[0].title === "Beta";
  });
  assert.equal(filtered.view.sections[0].items[0].title, "Beta");
  host.send({ type: "search", text: "" });
  const restored = await host.waitFor((msg) => {
    if (msg.type !== "render") return false;
    return msg.view.sections.flatMap((section) => section.items).length === 2;
  });
  const copy = restored.view.sections.flatMap((section) => section.items).find((item) => item.title === "Alpha");
  host.send({ type: "action", id: copy.actions[0].id });
  const copied = await host.waitFor((msg) => msg.type === "copy");
  assert.equal(copied.text, "alpha");
  host.child.kill();
});
