"use strict";

const { Icon, Color, Image } = require("./icons");
const { environment, getPreferenceValues } = require("./environment");
const { LocalStorage, Cache } = require("./storage");
const {
  Toast,
  showToast,
  showHUD,
  confirmAlert,
  openExtensionPreferences,
  openCommandPreferences,
  launchCommand,
  updateCommandMetadata,
  AI,
  OAuth,
  notSupported,
} = require("./toast");
const {
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
} = require("./clipboard");
const { useNavigation } = require("./navigation");
const { List, Grid, Detail, Form, ActionPanel, Action } = require("./components");

const LaunchType = {
  UserInitiated: "userInitiated",
  Background: "background",
};

function MenuBarExtra() {
  throw notSupported("MenuBarExtra");
}

function missing(name) {
  const fn = function missingApi() {
    throw notSupported(name);
  };
  fn.displayName = name;
  return new Proxy(fn, {
    get(_t, prop) {
      if (prop === "prototype" || prop === "name" || prop === "length" || typeof prop === "symbol") {
        return fn[prop];
      }
      if (prop === "then") return undefined;
      return missing(name + "." + String(prop));
    },
    apply() {
      throw notSupported(name);
    },
    construct() {
      throw notSupported(name);
    },
  });
}

const api = {
  List,
  Grid,
  Detail,
  Form,
  ActionPanel,
  Action,
  Icon,
  Color,
  Image,
  Keyboard,
  Application,
  Toast,
  Cache,
  LocalStorage,
  Clipboard,
  environment: environment(),
  LaunchType,
  getPreferenceValues,
  showToast,
  showHUD,
  confirmAlert,
  open,
  closeMainWindow,
  popToRoot,
  useNavigation,
  openExtensionPreferences,
  openCommandPreferences,
  launchCommand,
  updateCommandMetadata,
  getApplications,
  getFrontmostApplication,
  getSelectedText,
  getSelectedFinderItems,
  trash,
  showInFinder,
  AI,
  OAuth,
  MenuBarExtra,
};

// The older names @raycast/api still exports (its index.d.ts), and the
// rest of its top-level functions.
const AlertActionStyle = { Default: "default", Cancel: "cancel", Destructive: "destructive" };
Object.assign(api, {
  ActionPanelItem: Action,
  ActionPanelSection: ActionPanel.Section,
  ActionPanelSubmenu: ActionPanel.Submenu,
  CopyToClipboardAction: Action.CopyToClipboard,
  FormCheckbox: Form.Checkbox,
  FormDatePicker: Form.DatePicker,
  FormDropdown: Form.Dropdown,
  FormDropdownItem: Form.Dropdown.Item,
  FormDropdownSection: Form.Dropdown.Section,
  FormSeparator: Form.Separator,
  FormTagPicker: Form.TagPicker,
  FormTagPickerItem: Form.TagPicker.Item,
  FormTextArea: Form.TextArea,
  FormTextField: Form.TextField,
  ImageMask: Image.Mask,
  Alert: { ActionStyle: AlertActionStyle },
  AlertActionStyle,
  BrowserExtension: missing("BrowserExtension"),
  allLocalStorageItems: () => LocalStorage.allItems(),
  getLocalStorageItem: (k) => LocalStorage.getItem(k),
  setLocalStorageItem: (k, v) => LocalStorage.setItem(k, v),
  removeLocalStorageItem: (k) => LocalStorage.removeItem(k),
  clearLocalStorage: () => LocalStorage.clear(),
  copyTextToClipboard: (t) => Clipboard.copy(t),
  clearClipboard: () => Clipboard.clear(),
  clearSearchBar: async () => {},
  captureException: (e) => console.error(e),
  captureMemorySnapshot: async () => {},
  getDefaultApplication: async () => {
    throw notSupported("getDefaultApplication");
  },
});

function refreshEnvironment() {
  const next = environment();
  Object.keys(api.environment).forEach((key) => {
    if (!(key in next)) delete api.environment[key];
  });
  Object.assign(api.environment, next);
}

const proxy = new Proxy(api, {
  get(target, prop) {
    if (prop in target) return target[prop];
    if (typeof prop === "symbol") return undefined;
    if (prop === "then" || prop === "__esModule" || prop === "default") return undefined;
    return missing(String(prop));
  },
});

module.exports = proxy;
module.exports.refreshEnvironment = refreshEnvironment;
module.exports.__internal = { api, refreshEnvironment };
