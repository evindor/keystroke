"use strict";

// Fetch and install Raycast store extensions the way Vicinae does:
// GET https://backend.raycast.com/api/v1/store_listings (or /extensions/<handle>/<name>),
// download the signed zip from download_url, and extract it with the top
// folder removed. The bundle is already built; @raycast/api and react are
// supplied by the host at run time.

const fs = require("fs");
const path = require("path");
const https = require("https");
const { spawn } = require("child_process");

const API = "https://backend.raycast.com/api/v1";
const COMPAT_URL = "https://api.vicinae.com/v1/raycast/get-compat";
const UA = "keystroke-raycast";
const MAX_BYTES = 80 * 1024 * 1024;
const NAME = /^[A-Za-z0-9._-]+$/;

function paths(env) {
  const source = env || process.env;
  const home = source.HOME || "";
  const base = source.XDG_DATA_HOME || (home ? path.join(home, ".local", "share") : "");
  const root = path.join(base, "keystroke", "raycast");
  return {
    root,
    extensions: path.join(root, "extensions"),
    runtime: path.join(root, "runtime"),
    compat: path.join(root, "compat.json"),
  };
}

function safeName(value) {
  const name = String(value || "");
  return NAME.test(name) ? name : "";
}

function extensionId(name) {
  return "store.raycast." + name;
}

function allowedDownload(url) {
  let parsed;
  try {
    parsed = new URL(String(url || ""));
  } catch {
    return false;
  }
  if (parsed.protocol !== "https:") return false;
  const host = parsed.hostname.toLowerCase();
  return host === "backend.raycast.com" || host.endsWith(".raycast.com") || host.endsWith(".raycast-releases.com");
}

function request(url, redirects) {
  const left = redirects == null ? 4 : redirects;
  if (!allowedDownload(url) && !String(url).startsWith(API) && url !== COMPAT_URL) {
    return Promise.reject(new Error("Refusing " + url));
  }
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { "User-Agent": UA, Accept: "application/json" } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        res.resume();
        if (left <= 0) return reject(new Error("Too many redirects"));
        const next = new URL(res.headers.location, url).toString();
        return resolve(request(next, left - 1));
      }
      const chunks = [];
      let size = 0;
      res.on("data", (chunk) => {
        size += chunk.length;
        if (size > MAX_BYTES) {
          req.destroy(new Error("Download is larger than 80 MB"));
          return;
        }
        chunks.push(chunk);
      });
      res.on("end", () => {
        const body = Buffer.concat(chunks);
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const err = new Error("Raycast store " + res.statusCode + ": " + body.toString("utf8").slice(0, 240));
          err.status = res.statusCode;
          return reject(err);
        }
        resolve(body);
      });
    });
    req.setTimeout(30000, () => req.destroy(new Error("Raycast store timed out")));
    req.on("error", reject);
  });
}

async function getJson(url) {
  const body = await request(url);
  return JSON.parse(body.toString("utf8"));
}

function authorHandle(ext) {
  const author = ext && ext.author;
  const owner = ext && ext.owner;
  return safeName((author && (author.handle || author.username)) || (owner && (owner.handle || owner.username)) || "");
}

function mapExtension(ext, installed, compat) {
  const name = safeName(ext && ext.name);
  const handle = authorHandle(ext);
  if (!name || !handle || (ext && ext.kill_listed_at)) return null;
  const info = compat && compat[name];
  return {
    name,
    title: (ext && ext.title) || name,
    description: (ext && ext.description) || "",
    handle,
    downloads: (ext && ext.download_count) || 0,
    installed: !!(installed && installed.has(name)),
    compat: info && info.status ? String(info.status) : "",
    commands: ((ext && ext.commands) || []).map((cmd) => ({
      name: cmd.name,
      title: cmd.title || cmd.name,
      mode: cmd.mode || "view",
    })),
  };
}

function installedNames(extensionsDir) {
  const names = new Set();
  for (const ext of list(extensionsDir)) names.add(ext.name);
  return names;
}

async function search(query, extensionsDir, compat) {
  const q = String(query || "").trim();
  const url = q
    ? API + "/store_listings/search?q=" + encodeURIComponent(q).replace(/%20/g, "+")
    : API + "/store_listings?page=1&per_page=50";
  const payload = await getJson(url);
  const data = Array.isArray(payload) ? payload : payload.data || [];
  const installed = installedNames(extensionsDir);
  const extensions = [];
  for (const ext of data) {
    const mapped = mapExtension(ext, installed, compat);
    if (mapped) extensions.push(mapped);
  }
  return extensions;
}

async function fetchExtension(handle, name) {
  if (!safeName(handle) || !safeName(name)) throw new Error("Invalid extension name");
  const payload = await getJson(API + "/extensions/" + encodeURIComponent(handle) + "/" + encodeURIComponent(name));
  const ext = payload && payload.data && payload.name === undefined ? payload.data : payload;
  if (!ext || !ext.download_url) throw new Error("Raycast store returned no download for " + name);
  if (ext.kill_listed_at) throw new Error(name + " is no longer available from the store");
  return ext;
}

function run(cmd, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { cwd, stdio: ["ignore", "pipe", "pipe"] });
    let stderr = "";
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(stderr);
      else reject(new Error(cmd + " failed (" + code + "): " + stderr.slice(-800)));
    });
  });
}

async function installExtras(dir, pkg) {
  const extras = {};
  for (const [name, version] of Object.entries(pkg.dependencies || {})) {
    if (name === "@raycast/api" || name === "@raycast/utils") continue;
    extras[name] = version;
  }
  const names = Object.keys(extras);
  if (!names.length) return;
  const staging = path.join(dir, ".npm");
  fs.mkdirSync(staging, { recursive: true });
  fs.writeFileSync(path.join(staging, "package.json"), JSON.stringify({ private: true, dependencies: extras }));
  await run("npm", ["install", "--omit=dev", "--ignore-scripts", "--no-fund", "--no-audit"], staging);
  fs.cpSync(path.join(staging, "node_modules"), path.join(dir, "node_modules"), { recursive: true });
  fs.rmSync(staging, { recursive: true, force: true });
}

async function install(handle, name, extensionsDir) {
  const ext = await fetchExtension(handle, name);
  if (!allowedDownload(ext.download_url)) throw new Error("Store download URL is not a Raycast host");
  const id = extensionId(safeName(ext.name || name));
  const root = path.resolve(extensionsDir);
  fs.mkdirSync(root, { recursive: true });
  const finalDir = path.join(root, id);
  const staging = path.join(root, ".staging-" + id);
  const zipPath = path.join(root, ".download-" + id + ".zip");
  fs.rmSync(staging, { recursive: true, force: true });
  try {
    const bytes = await request(ext.download_url);
    fs.writeFileSync(zipPath, bytes);
    await run("python3", [path.join(__dirname, "unzip.py"), zipPath, staging], root);
    const pkgPath = path.join(staging, "package.json");
    if (!fs.existsSync(pkgPath)) throw new Error("Downloaded bundle has no package.json");
    const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
    await installExtras(staging, pkg);
    fs.rmSync(finalDir, { recursive: true, force: true });
    fs.renameSync(staging, finalDir);
    return {
      ok: true,
      id,
      name: pkg.name || name,
      title: pkg.title || name,
      commands: commandEntry(pkg),
    };
  } finally {
    fs.rmSync(staging, { recursive: true, force: true });
    fs.rmSync(zipPath, { force: true });
  }
}

function commandEntry(pkg) {
  return (pkg.commands || []).map((cmd) => ({
    name: cmd.name,
    title: cmd.title || cmd.name,
    subtitle: cmd.subtitle || "",
    description: cmd.description || "",
    mode: cmd.mode || "view",
  }));
}

function list(extensionsDir) {
  const dir = path.resolve(extensionsDir);
  if (!fs.existsSync(dir)) return [];
  const out = [];
  for (const id of fs.readdirSync(dir)) {
    if (id.startsWith(".")) continue;
    const folder = path.join(dir, id);
    const pkgPath = path.join(folder, "package.json");
    if (!fs.existsSync(pkgPath)) continue;
    let pkg;
    try {
      pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
    } catch {
      continue;
    }
    const name = pkg.name || id.replace(/^store\.raycast\./, "");
    out.push({
      id,
      name,
      title: pkg.title || name,
      dir: folder,
      commands: commandEntry(pkg),
    });
  }
  return out;
}

function remove(id, extensionsDir) {
  const clean = safeName(id) || (safeName(String(id || "").replace(/^store\.raycast\./, "")) ? extensionId(safeName(String(id).replace(/^store\.raycast\./, ""))) : "");
  if (!clean || clean.indexOf("..") !== -1) return { ok: false, error: "Invalid extension id" };
  const dest = path.join(path.resolve(extensionsDir), clean.startsWith("store.raycast.") ? clean : extensionId(clean));
  const root = path.resolve(extensionsDir);
  if (path.dirname(dest) !== root) return { ok: false, error: "Invalid extension id" };
  if (!fs.existsSync(dest)) return { ok: false, error: "Not installed: " + clean };
  fs.rmSync(dest, { recursive: true, force: true });
  return { ok: true, id: path.basename(dest) };
}

function runtimeReady(runtimeDir) {
  return fs.existsSync(path.join(runtimeDir, "node_modules", "react", "package.json"))
    && fs.existsSync(path.join(runtimeDir, "node_modules", "react-reconciler", "package.json"));
}

async function loadCompat(cacheFile) {
  let cached = null;
  try {
    cached = JSON.parse(fs.readFileSync(cacheFile, "utf8"));
  } catch {
    cached = null;
  }
  const fresh = cached && cached.fetchedAt && Date.now() - cached.fetchedAt < 24 * 60 * 60 * 1000;
  if (fresh) return cached.map || {};
  try {
    const map = await getJson(COMPAT_URL);
    fs.mkdirSync(path.dirname(cacheFile), { recursive: true });
    fs.writeFileSync(cacheFile, JSON.stringify({ fetchedAt: Date.now(), map }));
    return map || {};
  } catch (err) {
    console.error("compat:", err.message);
    return (cached && cached.map) || {};
  }
}

async function status(extensionsDir, cacheFile, runtimeDir) {
  return {
    ok: true,
    node: process.version,
    runtime: runtimeReady(runtimeDir),
    extensions: list(extensionsDir),
    compat: await loadCompat(cacheFile),
  };
}

module.exports = {
  paths,
  safeName,
  extensionId,
  allowedDownload,
  mapExtension,
  search,
  install,
  list,
  remove,
  runtimeReady,
  loadCompat,
  status,
};
