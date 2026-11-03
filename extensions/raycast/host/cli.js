"use strict";

const { runCommand } = require("./host");
const store = require("./store");
const { send, log } = require("./protocol");

function out(value) {
  process.stdout.write(JSON.stringify(value) + "\n");
}

async function main(argv) {
  const [cmd, a, b, c] = argv;
  const dirs = store.paths();
  if (cmd === "run") {
    if (!a || !b) throw new Error("Usage: cli.js run <extension-dir> <command>");
    await runCommand(a, b);
    return;
  }
  if (cmd === "search") {
    const compat = await store.loadCompat(dirs.compat);
    const extensions = await store.search(a || "", b || dirs.extensions, compat);
    out({ ok: true, extensions });
    return;
  }
  if (cmd === "install") {
    if (!a || !b) throw new Error("Usage: cli.js install <handle> <name> [extensions-dir]");
    out(await store.install(a, b, c || dirs.extensions));
    return;
  }
  if (cmd === "remove") {
    if (!a) throw new Error("Usage: cli.js remove <id> [extensions-dir]");
    out(store.remove(a, b || dirs.extensions));
    return;
  }
  if (cmd === "list") {
    out({ ok: true, extensions: store.list(a || dirs.extensions) });
    return;
  }
  if (cmd === "status") {
    out(await store.status(a || dirs.extensions, dirs.compat, dirs.runtime));
    return;
  }
  throw new Error("Unknown command. Use run, search, install, remove, list, or status.");
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((err) => {
    const message = err && err.message ? err.message : String(err);
    log(err && err.stack ? err.stack : message);
    if (process.argv[2] === "run") send({ type: "error", message });
    else out({ ok: false, error: message });
    process.exit(1);
  });
}

module.exports = { main };
