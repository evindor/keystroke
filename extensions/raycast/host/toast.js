"use strict";

const { send, request } = require("./protocol");

const ToastStyle = {
  Success: "success",
  Failure: "failure",
  Animated: "animated",
};

class Toast {
  constructor(options) {
    const opts = options || {};
    this.style = opts.style || ToastStyle.Success;
    this.title = opts.title || "";
    this.message = opts.message || "";
    this.primaryAction = opts.primaryAction;
    this.secondaryAction = opts.secondaryAction;
  }

  show() {
    send({
      type: "toast",
      style: normalizeStyle(this.style),
      title: String(this.title || ""),
      message: this.message != null ? String(this.message) : "",
    });
    return Promise.resolve(this);
  }

  hide() {
    return Promise.resolve();
  }
}

Toast.Style = ToastStyle;

function normalizeStyle(style) {
  if (style === ToastStyle.Failure || style === "failure") return "failure";
  if (style === ToastStyle.Animated || style === "animated") return "animated";
  return "success";
}

async function showToast(styleOrOptions, title, message) {
  let toast;
  if (styleOrOptions && typeof styleOrOptions === "object") {
    toast = new Toast(styleOrOptions);
  } else {
    toast = new Toast({ style: styleOrOptions, title, message });
  }
  await toast.show();
  return toast;
}

function showHUD(title) {
  const text = typeof title === "string" ? title : title && title.title ? title.title : String(title ?? "");
  send({ type: "hud", title: text });
  return Promise.resolve();
}

async function confirmAlert(options) {
  const opts = options || {};
  const result = await request("confirm", {
    title: opts.title || "Confirm",
    message: opts.message || "",
    primaryAction: opts.primaryAction && opts.primaryAction.title,
    dismissAction: opts.dismissAction && opts.dismissAction.title,
  });
  if (typeof result === "boolean") return result;
  if (result && typeof result === "object" && "confirmed" in result) return !!result.confirmed;
  return true;
}

function openExtensionPreferences() {
  return showToast({ style: ToastStyle.Failure, title: "Extension preferences not supported" });
}

function openCommandPreferences() {
  return showToast({ style: ToastStyle.Failure, title: "Command preferences not supported" });
}

function launchCommand() {
  return showToast({ style: ToastStyle.Failure, title: "launchCommand is not supported" });
}

function updateCommandMetadata() {
  return Promise.resolve();
}

function notSupported(name) {
  const err = new Error(name + " is not supported by the Nanolight Raycast host");
  err.code = "NOT_SUPPORTED";
  return err;
}

const AI = new Proxy(
  {},
  {
    get(_t, prop) {
      if (prop === "then") return undefined;
      return () => {
        throw notSupported("AI." + String(prop));
      };
    },
    apply() {
      throw notSupported("AI");
    },
  }
);

function OAuth() {
  throw notSupported("OAuth");
}
OAuth.PKCEClient = class PKCEClient {
  constructor() {
    throw notSupported("OAuth.PKCEClient");
  }
};

module.exports = {
  Toast,
  ToastStyle,
  showToast,
  showHUD,
  confirmAlert,
  openExtensionPreferences,
  openCommandPreferences,
  launchCommand,
  updateCommandMetadata,
  notSupported,
  AI,
  OAuth,
};
