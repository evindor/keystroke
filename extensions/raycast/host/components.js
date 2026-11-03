"use strict";

const React = require("react");
const { resolveIcon } = require("./icons");
const { open, trash, stringify } = require("./clipboard");
const { send } = require("./protocol");
const nav = require("./navigation");

function passthrough(type) {
  return function Component(props) {
    return React.createElement(type, props, props && props.children);
  };
}

function List(props) {
  return React.createElement(
    "List",
    props,
    props && props.searchBarAccessory,
    props && props.children
  );
}
List.Item = passthrough("List.Item");
List.Section = passthrough("List.Section");
List.EmptyView = passthrough("List.EmptyView");
List.Dropdown = passthrough("List.Dropdown");
List.Dropdown.Item = passthrough("List.Dropdown.Item");
List.Dropdown.Section = passthrough("List.Dropdown.Section");

function Grid(props) {
  return React.createElement(
    "Grid",
    props,
    props && props.searchBarAccessory,
    props && props.children
  );
}
Grid.Item = passthrough("Grid.Item");
Grid.Section = passthrough("Grid.Section");
Grid.EmptyView = passthrough("Grid.EmptyView");
Grid.Dropdown = List.Dropdown;
Grid.Dropdown.Item = List.Dropdown.Item;
Grid.Dropdown.Section = List.Dropdown.Section;

const Detail = passthrough("Detail");
Detail.Metadata = passthrough("Detail.Metadata");
Detail.Metadata.Label = passthrough("Detail.Metadata.Label");
Detail.Metadata.Link = passthrough("Detail.Metadata.Link");
Detail.Metadata.TagList = passthrough("Detail.Metadata.TagList");
Detail.Metadata.TagList.Item = passthrough("Detail.Metadata.TagList.Item");
Detail.Metadata.Separator = passthrough("Detail.Metadata.Separator");
Detail.Metadata.Label = passthrough("Detail.Metadata.Label");

const Form = passthrough("Form");
Form.TextField = passthrough("Form.TextField");
Form.TextArea = passthrough("Form.TextArea");
Form.PasswordField = passthrough("Form.PasswordField");
Form.Checkbox = passthrough("Form.Checkbox");
Form.Dropdown = passthrough("Form.Dropdown");
Form.Dropdown.Item = passthrough("Form.Dropdown.Item");
Form.Dropdown.Section = passthrough("Form.Dropdown.Section");
Form.DatePicker = passthrough("Form.DatePicker");
Form.Separator = passthrough("Form.Separator");
Form.Description = passthrough("Form.Description");
Form.FilePicker = passthrough("Form.FilePicker");
Form.TagPicker = passthrough("Form.TagPicker");
Form.TagPicker.Item = passthrough("Form.TagPicker.Item");

const ActionPanel = passthrough("ActionPanel");
ActionPanel.Section = passthrough("ActionPanel.Section");
ActionPanel.Submenu = passthrough("ActionPanel.Submenu");

function Action(props) {
  return React.createElement("Action", props);
}

function shortcutString(shortcut) {
  if (!shortcut) return null;
  if (typeof shortcut === "string") return shortcut;
  const mods = (shortcut.modifiers || []).map((m) => String(m).toLowerCase());
  const key = shortcut.key != null ? String(shortcut.key).toLowerCase() : "";
  return (mods.length ? mods.join("+") + "+" : "") + key || null;
}

function runAction(props) {
  if (!props) return;
  const type = props.__action || "Action";
  if (type === "Action.OpenInBrowser" || type === "Action.Open") {
    send({ type: "open", target: String(props.url || props.target || props.path || "") });
    return;
  }
  if (type === "Action.CopyToClipboard") {
    send({ type: "copy", text: stringify(props.content) });
    return;
  }
  if (type === "Action.Paste") {
    send({ type: "paste", text: stringify(props.content) });
    return;
  }
  if (type === "Action.Push") {
    const target = props.__target || props.target;
    if (target) nav.push(target);
    return;
  }
  if (type === "Action.ShowInFinder") {
    open(props.path || props.target || "");
    return;
  }
  if (type === "Action.Trash") {
    trash(props.paths || props.path);
    return;
  }
  if (type === "Action.SubmitForm") {
    return;
  }
  if (typeof props.onAction === "function") {
    Promise.resolve(props.onAction()).catch((err) => {
      send({ type: "error", message: err && err.message ? err.message : String(err) });
    });
  }
}

Action.OpenInBrowser = function OpenInBrowser(props) {
  return React.createElement("Action", { ...props, __action: "Action.OpenInBrowser", title: props.title || "Open in Browser" });
};
Action.CopyToClipboard = function CopyToClipboard(props) {
  return React.createElement("Action", { ...props, __action: "Action.CopyToClipboard", title: props.title || "Copy to Clipboard" });
};
Action.Paste = function Paste(props) {
  return React.createElement("Action", { ...props, __action: "Action.Paste", title: props.title || "Paste" });
};
Action.Push = function Push(props) {
  return React.createElement("Action", {
    ...props,
    __action: "Action.Push",
    __target: props.target,
    title: props.title || "Push",
  });
};
Action.Open = function OpenAction(props) {
  return React.createElement("Action", { ...props, __action: "Action.Open", title: props.title || "Open" });
};
Action.ShowInFinder = function ShowInFinder(props) {
  return React.createElement("Action", { ...props, __action: "Action.ShowInFinder", title: props.title || "Show in Finder" });
};
Action.SubmitForm = function SubmitForm(props) {
  return React.createElement("Action", { ...props, __action: "Action.SubmitForm", title: props.title || "Submit" });
};
Action.Trash = function Trash(props) {
  return React.createElement("Action", { ...props, __action: "Action.Trash", title: props.title || "Move to Trash" });
};
Action.CopyToClipboard = Action.CopyToClipboard;
Action.Style = { Regular: "regular", Destructive: "destructive" };

function ActionStyle() {}

module.exports = {
  List,
  Grid,
  Detail,
  Form,
  ActionPanel,
  Action,
  runAction,
  shortcutString,
  resolveIcon,
  ActionStyle,
};
