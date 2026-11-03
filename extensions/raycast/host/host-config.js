"use strict";

const React = require("react");

const hostConfig = {
  supportsMutation: true,
  supportsPersistence: false,
  supportsHydration: false,
  isPrimaryRenderer: true,
  noTimeout: -1,
  createInstance(type, props) {
    return { type, props: props || {}, children: [] };
  },
  createTextInstance(text) {
    return { type: "#text", text: String(text), props: {}, children: [] };
  },
  appendInitialChild(parent, child) {
    parent.children.push(child);
  },
  finalizeInitialChildren() {
    return false;
  },
  prepareUpdate() {
    return true;
  },
  shouldSetTextContent() {
    return false;
  },
  getRootHostContext() {
    return {};
  },
  getChildHostContext(parent) {
    return parent;
  },
  getPublicInstance(instance) {
    return instance;
  },
  prepareForCommit() {
    return null;
  },
  resetAfterCommit(containerInfo) {
    if (containerInfo && containerInfo.onCommit) containerInfo.onCommit(containerInfo);
  },
  preparePortalMount() {},
  scheduleTimeout: setTimeout,
  cancelTimeout: clearTimeout,
  getCurrentEventPriority() {
    return 16;
  },
  getInstanceFromNode() {
    return null;
  },
  beforeActiveInstanceBlur() {},
  afterActiveInstanceBlur() {},
  prepareScopeUpdate() {},
  getInstanceFromScope() {
    return null;
  },
  detachDeletedInstance() {},
  clearContainer() {},
  appendChild(parent, child) {
    parent.children.push(child);
  },
  appendChildToContainer(container, child) {
    container.root = child;
  },
  insertBefore(parent, child, before) {
    const i = parent.children.indexOf(before);
    if (i < 0) parent.children.push(child);
    else parent.children.splice(i, 0, child);
  },
  insertInContainerBefore(container, child) {
    container.root = child;
  },
  removeChild(parent, child) {
    parent.children = parent.children.filter((c) => c !== child);
  },
  removeChildFromContainer(container) {
    container.root = null;
  },
  commitUpdate(instance, _type, _old, newProps) {
    instance.props = newProps || {};
  },
  commitTextUpdate(instance, _old, next) {
    instance.text = String(next);
  },
  hideInstance() {},
  hideTextInstance() {},
  unhideInstance() {},
  unhideTextInstance() {},
  maySuspendCommit() {
    return false;
  },
  preloadInstance() {
    return true;
  },
  startSuspendingCommit() {},
  suspendInstance() {},
  waitForCommitToBeReady() {
    return null;
  },
  NotPendingTransition: null,
  HostTransitionContext: React.createContext(null),
  setCurrentUpdatePriority() {},
  getCurrentUpdatePriority() {
    return 1;
  },
  resolveUpdatePriority() {
    return 1;
  },
  trackSchedulerEvent() {},
  resolveEventType() {
    return null;
  },
  resolveEventTimeStamp() {
    return -1.1;
  },
  shouldAttemptEagerTransition() {
    return false;
  },
  requestPostPaintCallback() {},
  mayResourceSuspendCommit() {
    return false;
  },
  resetFormInstance() {},
};

module.exports = hostConfig;
