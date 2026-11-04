"use strict";
// Built-in Node test runner only; zero npm packages and zero browser/runtime
// dependencies. Executes the actual browser script against a minimal DOM stub.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function launch() {
  const handles = new Map();
  const elements = new Map();
  for (const name of ["token", "subject", "state", "result", "connect", "oracle", "clear"]) {
    elements.set(name, {
      value: "", textContent: "", disabled: false,
      addEventListener(event, callback) { handles.set(name + ":" + event, callback); },
      focus() {},
    });
  }
  const events = new Map();
  const calls = [];
  const script = fs.readFileSync(path.join(__dirname, "operator.js"), "utf8");
  const context = {
    document: { getElementById: (id) => elements.get(id) },
    window: { addEventListener: (event, callback) => events.set(event, callback) },
    async fetch(url, options) {
      calls.push({ url, options });
      return {ok: true, status: 200, async json() {return {ok: true, protocol: "fixture"};}};
    },
  };
  vm.runInNewContext(script, context, {filename: "deployment/operator.js", timeout: 1000});
  return { handles, elements, events, calls };
}

test("repeated inspection reuses a tab-memory token, then ORACLE query works", async () => {
  const state = launch();
  const token = "a".repeat(48);
  state.elements.get("token").value = token;
  await state.handles.get("connect:click")();
  assert.equal(state.calls.length, 1);
  assert.equal(state.elements.get("token").value, "");
  await state.handles.get("connect:click")();
  assert.equal(state.calls.length, 2);
  assert.equal(state.calls[1].options.headers.Authorization, "Bearer " + token);
  state.elements.get("subject").value = "exact-subject";
  await state.handles.get("oracle:click")();
  assert.equal(state.calls.length, 3);
  assert.equal(state.calls[2].url, "/v1/oracle/query");
  assert.equal(state.calls[2].options.headers.Authorization, "Bearer " + token);
});

test("explicit replacement, clear and pagehide enforce in-memory lifetime", async () => {
  const state = launch();
  const first = "a".repeat(48);
  const second = "b".repeat(48);
  state.elements.get("token").value = first;
  await state.handles.get("connect:click")();
  state.elements.get("token").value = "  " + second + "  ";
  await state.handles.get("connect:click")();
  assert.equal(state.calls[1].options.headers.Authorization, "Bearer " + second);
  state.handles.get("clear:click")();
  assert.equal(state.elements.get("token").value, "");
  const countBeforeClear = state.calls.length;
  await state.handles.get("connect:click")();
  assert.equal(state.calls.length, countBeforeClear, "cleared token must not send");
  assert.match(state.elements.get("result").textContent, /Operator token required/);

  state.elements.get("token").value = first;
  await state.handles.get("connect:click")();
  state.events.get("pagehide")();
  const countBeforeHide = state.calls.length;
  await state.handles.get("oracle:click")();
  assert.equal(state.calls.length, countBeforeHide, "pagehide-cleared token must not send");
});
