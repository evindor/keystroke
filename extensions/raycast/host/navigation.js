"use strict";

const React = require("react");

const stack = [];
let notify = () => {};

function setNavigator(fn) {
  notify = fn || (() => {});
}

function push(element, _options) {
  stack.push(element);
  notify();
}

function pop() {
  if (stack.length <= 1) return false;
  stack.pop();
  notify();
  return true;
}

function reset(root) {
  stack.length = 0;
  if (root) stack.push(root);
}

function top() {
  return stack.length ? stack[stack.length - 1] : null;
}

function depth() {
  return stack.length;
}

function useNavigation() {
  const [, setTick] = React.useState(0);
  return {
    push: (element) => {
      push(element);
      setTick((n) => n + 1);
    },
    pop: () => {
      pop();
      setTick((n) => n + 1);
    },
  };
}

module.exports = { setNavigator, push, pop, reset, top, depth, useNavigation, stack };
