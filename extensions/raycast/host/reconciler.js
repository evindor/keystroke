"use strict";

const ReactReconciler = require("react-reconciler");
const { resolveIcon, accessoryText } = require("./icons");
const { shortcutString, runAction } = require("./components");
const nav = require("./navigation");
const hostConfig = require("./host-config");

const Reconciler = ReactReconciler(hostConfig);

const session = {
  container: null,
  root: null,
  scheduled: false,
  lastJson: "",
  currentView: null,
  searchText: "",
  selectedId: null,
  formValues: {},
  dropdownValue: null,
  dropdownFired: false,
};
let container = null;
let root = null;
let scheduled = false;
let lastJson = "";
let currentView = null;
let searchText = "";
let selectedId = null;
let formValues = session.formValues;
let dropdownValue = null;
let dropdownFired = false;
const actionRegistry = new Map();
let actionSeq = 0;

function scheduleRender() {
  if (session.scheduled) return;
  session.scheduled = true;
  setTimeout(() => {
    session.scheduled = false;
    container = session.container;
    root = session.root;
    if (container && !container.root && session.tree) container.root = session.tree;
    flushRender();
  }, 16);
}

function childrenOf(node) {
  if (!node) return [];
  return (node.children || []).filter((c) => c && c.type !== "#text");
}

function findAll(node, type, out) {
  if (!node) return out;
  if (node.type === type) out.push(node);
  for (const child of node.children || []) findAll(child, type, out);
  return out;
}

function actionId(prefix, index, title) {
  const slug = String(title || "Action")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return prefix + ":" + index + ":" + (slug || "action");
}

function collectActions(node, prefix) {
  const actions = [];
  if (!node) return actions;
  let index = 0;
  const walk = (n) => {
    if (!n || n.type === "#text") return;
    if (n.type === "Action") {
      const props = n.props || {};
      const id = actionId(prefix || "actions", index, props.title);
      index += 1;
      actionRegistry.set(id, props);
      actions.push({
        id,
        title: props.title || "Action",
        shortcut: shortcutString(props.shortcut),
      });
      return;
    }
    for (const child of n.children || []) walk(child);
  };
  walk(node);
  return actions;
}

function itemFrom(node, index) {
  const props = node.props || {};
  const id = props.id != null ? String(props.id) : "item-" + index + "-" + String(props.title || index);
  const actionsNode = (node.children || []).find((c) => c.type === "ActionPanel");
  const actions = actionsNode ? collectActions(actionsNode, "item-" + id) : actionsFromElement(props.actions, "item-" + id);
  const accessories = Array.isArray(props.accessories) ? props.accessories.map(accessoryText).filter(Boolean) : [];
  return {
    id,
    title: props.title != null ? String(props.title) : "",
    subtitle: props.subtitle != null ? String(props.subtitle) : "",
    icon: resolveIcon(props.icon || props.content),
    accessories,
    keywords: props.keywords || [],
    actions,
  };
}

function actionsFromElement(element, prefix) {
  if (!element || typeof element !== "object") return [];
  const scratch = { root: null, onCommit() {} };
  const fiberRoot = Reconciler.createContainer(scratch, 0, null, false, null, "", () => {}, null);
  Reconciler.updateContainerSync(element, fiberRoot, null);
  Reconciler.flushSyncWork();
  Reconciler.flushPassiveEffects();
  return scratch.root ? collectActions(scratch.root, prefix || "actions") : [];
}

function serializeList(node, kind) {
  const props = node.props || {};
  const sections = [];
  const loose = [];
  let empty = null;
  for (const child of childrenOf(node)) {
    if (child.type === "List.Section" || child.type === "Grid.Section") {
      const items = [];
      let i = 0;
      for (const item of childrenOf(child)) {
        if (item.type === "List.Item" || item.type === "Grid.Item") {
          items.push(itemFrom(item, i));
          i += 1;
        }
      }
      sections.push({ title: (child.props && child.props.title) || "", items });
    } else if (child.type === "List.Item" || child.type === "Grid.Item") {
      loose.push(itemFrom(child, loose.length));
    } else if (child.type === "List.EmptyView" || child.type === "Grid.EmptyView") {
      empty = {
        title: (child.props && child.props.title) || "",
        description: (child.props && child.props.description) || "",
      };
    }
  }
  if (loose.length) sections.unshift({ title: "", items: loose });
  if (!sections.length) sections.push({ title: "", items: [] });
  const listActions = actionsFromElement(props.actions, "list");
  return {
    kind: kind === "Grid" ? "list" : "list",
    title: props.navigationTitle || props.title || "",
    placeholder: props.searchBarPlaceholder || "",
    loading: !!props.isLoading,
    sections,
    empty,
    selected: selectedId,
    actions: listActions,
    filtering: props.filtering !== false,
    hasSearchHandler: typeof props.onSearchTextChange === "function",
    _node: node,
  };
}

function metadataOf(node) {
  const labels = [];
  const walk = (n) => {
    if (!n) return;
    if (n.type === "Detail.Metadata.Label" || n.type === "Detail.Metadata.Link") {
      labels.push({
        label: (n.props && (n.props.title || n.props.label)) || "",
        text: (n.props && (n.props.text || n.props.title || n.props.target)) || "",
      });
    }
    for (const c of n.children || []) walk(c);
  };
  walk(node);
  return labels;
}

function serializeDetail(node) {
  const props = node.props || {};
  let metaNode = (node.children || []).find((c) => c.type === "Detail.Metadata");
  return {
    kind: "detail",
    title: props.navigationTitle || "",
    markdown: props.markdown != null ? String(props.markdown) : "",
    loading: !!props.isLoading,
    metadata: metaNode ? metadataOf(metaNode) : [],
    actions: actionsFromElement(props.actions, "detail"),
    _node: node,
  };
}

function fieldType(type) {
  if (type === "Form.TextArea") return "textarea";
  if (type === "Form.PasswordField") return "password";
  if (type === "Form.Checkbox") return "checkbox";
  if (type === "Form.Dropdown" || type === "Form.TagPicker") return "dropdown";
  if (type === "Form.DatePicker") return "date";
  if (type === "Form.Separator") return "separator";
  if (type === "Form.Description") return "description";
  return "text";
}

function serializeForm(node) {
  const props = node.props || {};
  const fields = [];
  const walk = (n) => {
    if (!n || n.type === "#text") return;
    const t = fieldType(n.type);
    if (n.type && n.type.startsWith("Form.") && n.type !== "Form") {
      const p = n.props || {};
      const id = p.id != null ? String(p.id) : "field-" + fields.length;
      const options = [];
      for (const c of childrenOf(n)) {
        if (c.type.endsWith(".Item")) {
          options.push({ value: String(c.props.value ?? ""), title: String(c.props.title ?? c.props.value ?? "") });
        }
      }
      const stored = Object.prototype.hasOwnProperty.call(formValues, id) ? formValues[id] : undefined;
      let value = stored !== undefined ? stored : p.value !== undefined ? p.value : p.defaultValue;
      if (value === undefined) value = t === "checkbox" ? false : "";
      fields.push({
        id,
        type: t,
        title: p.title || p.label || "",
        value,
        placeholder: p.placeholder || "",
        options,
      });
      return;
    }
    for (const c of n.children || []) walk(c);
  };
  for (const c of node.children || []) walk(c);
  return {
    kind: "form",
    title: props.navigationTitle || "",
    loading: !!props.isLoading,
    fields,
    actions: actionsFromElement(props.actions, "form"),
    _node: node,
  };
}

function serialize(node) {
  if (!node) return { kind: "list", title: "", placeholder: "", loading: false, sections: [{ title: "", items: [] }], empty: null, selected: null, actions: [] };
  if (node.type === "List" || node.type === "Grid") return serializeList(node, node.type);
  if (node.type === "Detail") return serializeDetail(node);
  if (node.type === "Form") return serializeForm(node);
  const nested = childrenOf(node);
  if (nested.length === 1) return serialize(nested[0]);
  const found = [];
  const scan = (n) => {
    if (!n) return;
    if (n.type === "List" || n.type === "Grid" || n.type === "Detail" || n.type === "Form") found.push(n);
    else for (const c of n.children || []) scan(c);
  };
  scan(node);
  if (found[0]) return serialize(found[0]);
  return {
    kind: "detail",
    title: "",
    markdown: node.type === "#text" ? node.text : "Unsupported view: " + (node.type || "unknown"),
    loading: false,
    metadata: [],
    actions: [],
  };
}

function applySearch(view) {
  if (view.kind !== "list") return strip(view);
  const node = view._node;
  const props = (node && node.props) || {};
  if (typeof props.onSearchTextChange === "function" || props.filtering === false) {
    return strip(view);
  }
  const q = (searchText || "").trim().toLowerCase();
  if (!q) return strip(view);
  const sections = view.sections.map((section) => ({
    title: section.title,
    items: section.items.filter((item) => {
      const hay = [item.title, item.subtitle, ...(item.keywords || []), ...(item.accessories || [])]
        .join(" ")
        .toLowerCase();
      return hay.includes(q) || fuzzy(hay, q);
    }),
  }));
  return strip({ ...view, sections });
}

function fuzzy(hay, q) {
  let i = 0;
  for (const ch of hay) {
    if (ch === q[i]) i += 1;
    if (i >= q.length) return true;
  }
  return false;
}

function strip(view) {
  const out = { ...view };
  delete out._node;
  delete out._actionsElement;
  delete out.filtering;
  delete out.hasSearchHandler;
  if (out.sections) {
    out.sections = out.sections.map((s) => ({
      title: s.title,
      items: s.items.map((item) => ({
        id: item.id,
        title: item.title,
        subtitle: item.subtitle || "",
        icon: item.icon || null,
        accessories: item.accessories || [],
        actions: item.actions || [],
      })),
    }));
  }
  return out;
}

function wireActions(view) {
  if (view.kind === "list" && selectedId) {
    for (const section of view.sections) {
      const item = section.items.find((it) => it.id === selectedId);
      if (item && item.actions && item.actions.length) view.actions = item.actions;
    }
  }
  return view;
}

function flushRender() {
  container = session.container;
  root = session.root;
  actionSeq = 0;
  actionRegistry.clear();
  const hostNode = container && container.root;
  if (!hostNode) return;
  let view = serialize(hostNode);
  view = wireActions(view);
  view = applySearch(view);
  if (!view.selected && view.kind === "list") {
    const first = view.sections.flatMap((s) => s.items)[0];
    view.selected = first ? first.id : null;
  }
  currentView = view;
  const json = JSON.stringify(view);
  if (json === lastJson) return;
  lastJson = json;
  const { send } = require("./protocol");
  send({ type: "render", view });
}

function mount(element) {
  container = { root: null, onCommit: scheduleRender };
  session.container = container;
  root = Reconciler.createContainer(container, 1, null, false, null, "nl", () => {}, null);
  session.root = root;
  nav.setNavigator(() => {
    const topEl = nav.top();
    if (topEl) update(topEl);
  });
  update(element);
}

function update(element) {
  Reconciler.updateContainer(element, root, null, () => {
    if (session.container && session.container.root) session.tree = session.container.root;
  });
}

function reportRenderError(error) {
  const { log, send } = require("./protocol");
  log("render error", error && error.stack ? error.stack : error);
  send({ type: "error", message: error && error.message ? error.message : String(error) });
}

function force() {
  lastJson = "";
  flushRender();
}

function setSearch(text) {
  searchText = text == null ? "" : String(text);
  const node = container && container.root;
  const props = findSearchProps(node);
  if (props && typeof props.onSearchTextChange === "function") {
    props.onSearchTextChange(searchText);
  }
  lastJson = "";
  scheduleRender();
}

function findSearchProps(node) {
  if (!node) return null;
  if (node.type === "List" || node.type === "Grid") return node.props;
  for (const c of node.children || []) {
    const found = findSearchProps(c);
    if (found) return found;
  }
  return null;
}

function setSelected(id) {
  selectedId = id;
  const node = container && container.root;
  const props = findSearchProps(node);
  if (props && typeof props.onSelectionChange === "function") {
    props.onSelectionChange(id);
  }
  lastJson = "";
  scheduleRender();
}

function setField(id, value) {
  formValues[id] = value;
  const node = container && container.root;
  const field = findField(node, id);
  if (field && field.props) {
    if (typeof field.props.onChange === "function") field.props.onChange(value);
  }
  lastJson = "";
  scheduleRender();
}

function findField(node, id) {
  if (!node) return null;
  if (node.props && node.props.id === id) return node;
  for (const c of node.children || []) {
    const found = findField(c, id);
    if (found) return found;
  }
  return null;
}

function runActionById(id) {
  const props = actionRegistry.get(id);
  if (!props) return;
  if (props.__action === "Action.SubmitForm") {
    const node = container && container.root;
    const form = findForm(node);
    const values = { ...formValues };
    if (form && form.props && typeof form.props.onSubmit === "function") {
      Promise.resolve(form.props.onSubmit(values)).catch((err) => {
        const { send } = require("./protocol");
        send({ type: "error", message: err && err.message ? err.message : String(err) });
      });
    } else if (typeof props.onSubmit === "function") {
      props.onSubmit(values);
    }
    return;
  }
  runAction(props);
  lastJson = "";
  scheduleRender();
}

function findForm(node) {
  if (!node) return null;
  if (node.type === "Form") return node;
  for (const c of node.children || []) {
    const found = findForm(c);
    if (found) return found;
  }
  return null;
}

function initDropdown(node) {
  if (!node || dropdownFired) return;
  const props = node.props || {};
  const accessory = props.searchBarAccessory;
  if (accessory && accessory.props && !dropdownFired) {
    if (accessory.props.defaultValue != null && typeof accessory.props.onChange === "function") {
      dropdownValue = accessory.props.defaultValue;
      dropdownFired = true;
      queueMicrotask(() => accessory.props.onChange(dropdownValue));
      return;
    }
  }
  if (node.type === "List.Dropdown" || node.type === "Grid.Dropdown") {
    const props = node.props || {};
    if (props.defaultValue != null) {
      dropdownValue = props.defaultValue;
      dropdownFired = true;
      if (typeof props.onChange === "function") {
        const { log } = require("./protocol");
        log("dropdown", dropdownValue);
        queueMicrotask(() => {
          try {
            props.onChange(dropdownValue);
          } catch (err) {
            const { send, log } = require("./protocol");
            log(err && err.stack ? err.stack : err);
            send({ type: "error", message: err && err.message ? err.message : String(err) });
          }
        });
      }
      return;
    }
  }
  for (const c of node.children || []) initDropdown(c);
}

module.exports = {
  mount,
  update,
  force,
  setSearch,
  setSelected,
  setField,
  runActionById,
  scheduleRender,
  initDropdown,
  getView: () => currentView,
  getRoot: () => (container ? container.root : null),
};
