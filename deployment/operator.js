"use strict";
// The single operator token stays in memory only. Never persist, log, or embed it.
let token = "";
const input = document.getElementById("token");
const subject = document.getElementById("subject");
const status = document.getElementById("state");
const output = document.getElementById("result");
const connect = document.getElementById("connect");
const query = document.getElementById("oracle");
const clear = document.getElementById("clear");
function show(value) {
  output.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
function busy(value) {
  connect.disabled = value;
  query.disabled = value;
}
async function request(path, payload) {
  if (token.length < 32) throw Error("Operator token required (minimum 32 characters)");
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json", "Authorization": "Bearer " + token},
    body: JSON.stringify(payload),
    cache: "no-store",
    credentials: "omit",
    redirect: "error",
    referrerPolicy: "no-referrer"
  });
  const body = await response.json();
  if (!response.ok) throw Error("Gateway rejected request: " + response.status +
                                " (" + String(body.error?.code || body.error || "error") + ")");
  return body;
}
connect.addEventListener("click", async function () {
  const replacement = input.value.trim();
  if (replacement) token = replacement;
  input.value = "";
  busy(true);
  status.textContent = "INSPECTING";
  try {
    const result = await request("/v1/snapshot", {});
    show(result);
    status.textContent = result.ok ? "INSPECTED" : "PARTIAL / CHECK DETAILS";
  } catch (error) {
    show(String(error.message));
    status.textContent = "NOT CONNECTED";
  } finally { busy(false); }
});
query.addEventListener("click", async function () {
  busy(true);
  status.textContent = "QUERYING";
  try {
    const result = await request("/v1/oracle/query", {subject: subject.value});
    show(result);
    status.textContent = "EVIDENCE STATE RETURNED";
  } catch (error) {
    show(String(error.message));
    status.textContent = "QUERY FAILED";
  } finally { busy(false); }
});
clear.addEventListener("click", function () {
  token = "";
  input.value = "";
  subject.value = "";
  show("Operator credential cleared from this tab's application memory.");
  status.textContent = "NOT AUTHENTICATED";
  input.focus();
});
window.addEventListener("pagehide", function () { token = ""; });
