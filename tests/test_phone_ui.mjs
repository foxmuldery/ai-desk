import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {test} from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../web/app.js", import.meta.url), "utf8");

function response(data, status = 200) {
  return {ok: status >= 200 && status < 300, status, json: async () => data};
}

function appWith(fetcher) {
  const ids = [
    "focusInput", "token", "target", "adapter", "instruction",
    "speakEnabled", "connection", "verification", "submit",
    "error", "tasks", "refresh", "verify", "voiceTest",
  ];
  const elements = Object.fromEntries(ids.map((id) => [
    id, {
      id, value: "", textContent: "", innerHTML: "", disabled: false,
      checked: false, listeners: {},
      addEventListener(name, callback) { this.listeners[name] = callback; },
      focus() {},
    },
  ]));
  elements.adapter.value = "dry-run";
  elements.target.value = "mac-studio";
  elements.instruction.value = "检查模拟任务，不执行真实操作";

  const document = {
    hidden: false,
    getElementById: (id) => elements[id],
    querySelectorAll: () => [],
    addEventListener() {},
  };
  const fakeWindow = {
    crypto: {randomUUID: () => "idempotency-fixed"},
    speechSynthesis: {cancel() {}, speak() {}},
  };
  function SpeechSynthesisUtterance(text) { this.text = text; this.lang = ""; }
  const context = vm.createContext({
    document, window: fakeWindow, crypto: fakeWindow.crypto,
    fetch: fetcher, setInterval() {}, SpeechSynthesisUtterance,
    console,
  });
  vm.runInContext(source, context, {filename: "app.js"});
  return {elements, context};
}

const safeHealth = () => response({ok: true, mode: "phone-dry-run"});
const safeCaps = () => response({adapters: [
  {id: "dry-run", directory_id: "demo", label: "Dry-run"},
]});

test("only phone-dry-run + dry-run capability may enable submit", async () => {
  const app = appWith(async (url) => {
    if (url === "/api/v1/health") return safeHealth();
    if (url === "/api/v1/capabilities") return response({adapters: [
      {id: "codex-readonly", directory_id: "codex-lab"},
      {id: "dry-run", directory_id: "demo"},
    ]});
    throw new Error("unexpected call");
  });
  app.elements.token.value = "local-test-token";
  const ok = await vm.runInContext("verifyAccess()", app.context);
  assert.equal(ok, false);
  assert.equal(app.elements.submit.disabled, true);
  assert.match(app.elements.error.textContent, /未经授权/);
});

test("insecure coordinator mode is never accepted", async () => {
  const app = appWith(async (url) => {
    if (url === "/api/v1/health") return response({ok: true, mode: "dry-run"});
    throw new Error("capabilities endpoint must not be called");
  });
  app.elements.token.value = "local-test-token";
  const ok = await vm.runInContext("verifyAccess()", app.context);
  assert.equal(ok, false);
  assert.equal(app.elements.submit.disabled, true);
});

test("phone submission accepts only dry-run and retains idempotency key on retry", async () => {
  let postCount = 0;
  const keys = [];
  const sentBodies = [];
  const app = appWith(async (url, options = {}) => {
    if (url === "/api/v1/health") return safeHealth();
    if (url === "/api/v1/capabilities") return safeCaps();
    if (url === "/api/v1/tasks?limit=30") return response({tasks: []});
    if (url === "/api/v1/tasks") {
      postCount++;
      keys.push(options.headers["Idempotency-Key"]);
      sentBodies.push(JSON.parse(options.body));
      if (postCount === 1) throw new Error("simulated network drop");
      return response({
        accepted: true, created: true,
        task: {id: "task_1", adapter: "dry-run", status: "queued"},
      }, 201);
    }
    throw new Error("Unexpected request: " + url);
  });
  app.elements.token.value = "local-test-token";
  assert.equal(await vm.runInContext("verifyAccess()", app.context), true);
  await vm.runInContext("submitTask()", app.context);
  assert.equal(postCount, 1);
  assert.equal(app.elements.instruction.value, "检查模拟任务，不执行真实操作");
  await vm.runInContext("submitTask()", app.context);
  assert.equal(postCount, 2);
  assert.equal(keys[0], keys[1]);
  assert.equal(sentBodies[0].adapter, "dry-run");
  assert.equal(sentBodies[0].working_directory_id, "demo");
  assert.equal(sentBodies[0].target_device_id, "mac-studio");
  assert.equal(app.elements.instruction.value, "");
});

test("token changes invalidate verification before the next task submission", async () => {
  const app = appWith(async (url) => {
    if (url === "/api/v1/health") return safeHealth();
    if (url === "/api/v1/capabilities") return safeCaps();
    if (url === "/api/v1/tasks?limit=30") return response({tasks: []});
    throw new Error("Submission was not permitted");
  });
  app.elements.token.value = "valid-test-token";
  assert.equal(await vm.runInContext("verifyAccess()", app.context), true);
  app.elements.token.value = "different-token";
  app.elements.token.listeners.input();
  assert.equal(app.elements.submit.disabled, true);
  await vm.runInContext("submitTask()", app.context);
  assert.match(app.elements.error.textContent, /验证连接/);
});
