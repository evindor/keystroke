"use strict";

const React = require("react");
const { List, ActionPanel, Action } = require("@raycast/api");

module.exports = function Command() {
  return React.createElement(
    List,
    { searchBarPlaceholder: "Filter" },
    React.createElement(List.Item, {
      id: "one",
      title: "Alpha",
      subtitle: "first",
      actions: React.createElement(
        ActionPanel,
        null,
        React.createElement(Action.CopyToClipboard, { title: "Copy", content: "alpha" })
      ),
    }),
    React.createElement(List.Item, { id: "two", title: "Beta", subtitle: "second" })
  );
};
