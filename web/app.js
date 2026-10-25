"use strict";

const $ = (id) => document.getElementById(id);
const statuses = {
  queued: "模拟任务排队中",
  accepted: "模拟任务已接收",
  running: "模拟处理中",
  needs_input: "等待输入",
  succeeded: "模拟完成",
  failed: "模拟失败",
  cancelled: "已取消",
  unknown: "状态未知",
};

const knownStatuses = new Map();
const watchedTasks = new Set();
const expandedTaskIds = new Set();
const eventCache = new Map();

let authorizedToken = null;
let authorizedProfile = null;
let pendingSubmission = null;
let fetchingTasks = false;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]
  ));
}

function token() {
  return $("token").value.trim();
}

function authHeaders(extra = {}) {
  return {Authorization: "Bearer " + token(), ...extra};
}

function speak(text) {
  if (!text || !("speechSynthesis" in window)) {
    $("error").textContent = "当前浏览器不支持语音播报。";
    return;
  }
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "zh-CN";
  window.speechSynthesis.speak(utterance);
}

function maybeAnnounce(task) {
  const previous = knownStatuses.get(task.id);
  const attentionStates = ["succeeded", "failed", "needs_input"];
  if (watchedTasks.has(task.id) && attentionStates.includes(task.status)
      && previous !== task.status) {
    if ($("speakEnabled").checked) {
      // Do not read the full potentially sensitive task instruction out loud.
      speak("AI Desk 的" + (statuses[task.status] || "模拟任务状态已更新") + "。");
    }
    watchedTasks.delete(task.id);
  }
  knownStatuses.set(task.id, task.status);
}

function invalidateVerification() {
  authorizedToken = null;
  authorizedProfile = null;
  $("verification").textContent = "需要重新验证";
  $("submit").disabled = true;
  $("tasks").textContent = "输入令牌后验证连接。";
}

async function checkHealth() {
  try {
    const response = await fetch("/api/v1/health", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok || data.ok !== true) throw new Error("服务不可用");
    if (data.mode !== "phone-dry-run") {
      $("connection").textContent = "模式不安全";
      $("error").textContent = "当前服务器不是专用 phone-dry-run 服务，已阻止提交。";
      invalidateVerification();
      return false;
    }
    $("connection").textContent = "模拟服务在线";
    return true;
  } catch {
    $("connection").textContent = "连接中断";
    return false;
  }
}

async function verifyAccess() {
  $("error").textContent = "";
  const enteredToken = token();
  if (!enteredToken) {
    invalidateVerification();
    $("verification").textContent = "请先输入临时令牌";
    return false;
  }
  const safeHealth = await checkHealth();
  if (!safeHealth) {
    $("verification").textContent = "未能连接安全模拟服务";
    return false;
  }
  try {
    const response = await fetch("/api/v1/capabilities", {
      headers: authHeaders(),
      cache: "no-store",
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || "访问令牌无效");
    const adapters = data.adapters;
    if (!Array.isArray(adapters) || adapters.length !== 1
        || adapters[0].id !== "dry-run" || adapters[0].directory_id !== "demo") {
      throw new Error("服务器提供了未经授权的执行能力，请停止手机测试。");
    }
    authorizedToken = enteredToken;
    authorizedProfile = "phone-dry-run";
    $("verification").textContent = "已验证 · 仅模拟任务";
    $("submit").disabled = false;
    await loadTasks();
    return true;
  } catch (error) {
    invalidateVerification();
    $("verification").textContent = "权限验证失败";
    $("error").textContent = error.message;
    return false;
  }
}

function renderEvents(events) {
  return events.map((event) => (
    '<div class="event-item"><div class="muted">' +
      esc(event.at) + " · " + esc(event.event_type) +
    '</div><div>' + esc(JSON.stringify(event.detail)) + "</div></div>"
  )).join("");
}

function renderTasks(tasks) {
  if (!tasks.length) {
    $("tasks").innerHTML = '<div class="muted">暂无任务，可以提交一条模拟任务。</div>';
    return;
  }
  $("tasks").innerHTML = tasks.map((task) => {
    const id = String(task.id);
    const open = expandedTaskIds.has(id);
    const events = eventCache.get(id);
    return `
      <article class="task">
        <div class="row">
          <div class="task-title">${esc(task.title)}</div>
          <span class="status ${esc(task.status)}">${esc(statuses[task.status] || "状态未知")}</span>
        </div>
        <div class="muted">${esc(id)} · Mac Studio · ${esc(task.created_at)}</div>
        <div class="summary">${esc(task.summary || task.instruction)}</div>
        <button class="secondary event-trigger" type="button"
                data-task-id="${esc(id)}">${open ? "收起事件" : "查看事件"}</button>
        <div class="event-panel summary" id="events-${esc(id)}" ${open ? "" : "hidden"}>
          ${events ? renderEvents(events) : '<span class="muted">加载中…</span>'}
        </div>
      </article>`;
  }).join("");

  document.querySelectorAll("[data-task-id]").forEach((button) => {
    button.addEventListener("click", () => toggleEvents(button.dataset.taskId));
  });
}

async function loadTasks() {
  if (fetchingTasks || !authorizedToken || authorizedProfile !== "phone-dry-run"
      || token() !== authorizedToken) return;
  fetchingTasks = true;
  try {
    const expectedToken = authorizedToken;
    const response = await fetch("/api/v1/tasks?limit=30", {
      headers: {Authorization: "Bearer " + expectedToken}, cache: "no-store",
    });
    const data = await response.json();
    // An in-flight response from an old login must not repaint after token changes.
    if (!authorizedToken || authorizedToken !== expectedToken || token() !== expectedToken) return;
    if (!response.ok) throw new Error(data.error?.message || "任务查询失败");
    if (!Array.isArray(data.tasks) || data.tasks.some((task) => task.adapter !== "dry-run")) {
      throw new Error("出现非模拟任务，当前手机端已经停止显示结果。");
    }
    data.tasks.forEach(maybeAnnounce);
    renderTasks(data.tasks);
    $("connection").textContent = "模拟服务在线";
  } catch (error) {
    $("connection").textContent = "任务连接异常";
    $("error").textContent = error.message;
  } finally {
    fetchingTasks = false;
  }
}

async function toggleEvents(id) {
  if (expandedTaskIds.has(id)) {
    expandedTaskIds.delete(id);
    await loadTasks();
    return;
  }
  expandedTaskIds.add(id);
  if (!eventCache.has(id)) {
    try {
      const response = await fetch("/api/v1/tasks/" + encodeURIComponent(id) + "/events", {
        headers: authHeaders(), cache: "no-store",
      });
      const data = await response.json();
      if (!response.ok || !Array.isArray(data.events)) {
        throw new Error(data.error?.message || "读取事件失败");
      }
      eventCache.set(id, data.events);
    } catch (error) {
      expandedTaskIds.delete(id);
      $("error").textContent = error.message;
      return;
    }
  }
  await loadTasks();
}

function newIdempotencyKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  if (!window.crypto?.getRandomValues) throw new Error("浏览器缺少安全随机数功能");
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function submitTask() {
  $("error").textContent = "";
  const instruction = $("instruction").value.trim();
  if (!instruction) {
    $("error").textContent = "请先输入模拟任务指令。";
    return;
  }
  if (!authorizedToken || token() !== authorizedToken || authorizedProfile !== "phone-dry-run") {
    $("error").textContent = "请先验证连接和模拟执行权限。";
    return;
  }
  const body = {
    instruction,
    target_device_id: "mac-studio",
    adapter: "dry-run",
    working_directory_id: "demo",
  };
  const signature = JSON.stringify(body);
  // If the HTTP response is lost, retrying the same instruction uses
  // exactly the same idempotency key rather than creating a duplicate.
  if (!pendingSubmission || pendingSubmission.signature !== signature) {
    pendingSubmission = {signature, key: newIdempotencyKey()};
  }
  $("submit").disabled = true;
  try {
    const response = await fetch("/api/v1/tasks", {
      method: "POST",
      headers: authHeaders({
        "Content-Type": "application/json",
        "Idempotency-Key": pendingSubmission.key,
      }),
      body: signature,
    });
    const result = await response.json();
    if (!response.ok || result.accepted !== true || !result.task?.id) {
      throw new Error(result.error?.message || "任务没有被服务端确认接收");
    }
    const id = result.task.id;
    watchedTasks.add(id);
    knownStatuses.set(id, result.task.status);
    pendingSubmission = null;
    $("instruction").value = "";
    $("error").textContent = "";
    await loadTasks();
  } catch (error) {
    $("error").textContent = "提交状态未确认，可保留原文并安全重试。详情：" + error.message;
  } finally {
    $("submit").disabled = !authorizedToken || authorizedProfile !== "phone-dry-run"
      || token() !== authorizedToken;
  }
}

$("focusInput").addEventListener("click", () => $("instruction").focus());
$("verify").addEventListener("click", verifyAccess);
$("token").addEventListener("input", invalidateVerification);
$("refresh").addEventListener("click", async () => {
  if (!authorizedToken) await verifyAccess();
  else await loadTasks();
});
$("submit").addEventListener("click", submitTask);
$("voiceTest").addEventListener("click", () => speak("AI Desk 中文模拟任务语音播报测试。"));

$("submit").disabled = true;
checkHealth();
setInterval(() => {
  if (!document.hidden && authorizedToken) loadTasks();
}, 3000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    checkHealth();
    loadTasks();
  }
});
