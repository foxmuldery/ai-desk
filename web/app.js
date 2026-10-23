const $ = (id) => document.getElementById(id);
const statuses = {queued:"排队中",accepted:"已接收",running:"执行中",needs_input:"等待确认",succeeded:"成功",failed:"失败",cancelled:"已取消",unknown:"状态未知"};
const knownStatuses = new Map();
const watchedTasks = new Set();
$("focusInput").addEventListener("click", () => $("instruction").focus());

function speak(text) {
  if (!text || !("speechSynthesis" in window)) return;
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
    const label = statuses[task.status] || task.status;
    speak((task.target_device_id || "执行电脑") + "的任务" + label + "。" + (task.summary || task.title || ""));
    watchedTasks.delete(task.id);
  }
  knownStatuses.set(task.id, task.status);
}
$("refresh").addEventListener("click", loadTasks);

function authHeaders(extra={}) {
  return {"Authorization":"Bearer "+$("token").value.trim(), ...extra};
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
async function checkHealth() {
  try {
    const r = await fetch("/api/v1/health");
    const d = await r.json();
    $("connection").textContent = d.ok ? "服务在线 · dry-run" : "服务异常";
  } catch { $("connection").textContent = "无法连接"; }
}
async function loadTasks() {
  $("error").textContent = "";
  if (!$("token").value.trim()) {
    $("tasks").innerHTML = '<div class="muted">输入本地服务令牌后即可查看任务。</div>';
    return;
  }
  try {
    const r = await fetch("/api/v1/tasks?limit=30", {headers:authHeaders()});
    const d = await r.json();
    if (!r.ok) throw new Error(d.error?.message || "读取任务失败");
    d.tasks.forEach(maybeAnnounce);
    if (!d.tasks.length) { $("tasks").innerHTML = '<div class="muted">暂无任务。可以先提交一条 dry-run 测试。</div>'; return; }
    $("tasks").innerHTML = d.tasks.map(t => `
      <article class="task">
        <div class="row"><div class="task-title">${esc(t.title)}</div><span class="status ${esc(t.status)}">${esc(statuses[t.status] || t.status)}</span></div>
        <div class="muted">${esc(t.id)} · ${esc(t.target_device_id)} · ${esc(t.created_at)}</div>
        <div class="summary">${esc(t.summary || t.instruction)}</div>
        <button class="secondary" style="margin-top:10px" data-task="${esc(t.id)}">查看事件</button>
        <div class="summary" id="events-${esc(t.id)}" hidden></div>
      </article>`).join("");
    document.querySelectorAll("[data-task]").forEach(btn => btn.addEventListener("click", () => loadEvents(btn.dataset.task)));
  } catch (e) {
    $("error").textContent = e.message;
    $("tasks").innerHTML = '<div class="muted">请输入有效令牌，或检查服务是否运行。</div>';
  }
}
async function loadEvents(id) {
  const box = $("events-"+id);
  if (!box) return;
  if (!box.hidden) { box.hidden = true; return; }
  try {
    const r = await fetch("/api/v1/tasks/"+encodeURIComponent(id)+"/events", {headers:authHeaders()});
    const d = await r.json();
    if (!r.ok) throw new Error(d.error?.message || "读取事件失败");
    box.innerHTML = d.events.map(e => `<div style="border-top:1px solid var(--line);padding:8px 0"><div class="muted">${esc(e.at)} · ${esc(e.event_type)}</div><div>${esc(JSON.stringify(e.detail))}</div></div>`).join("");
    box.hidden = false;
  } catch(e) { $("error").textContent = e.message; }
}
$("submit").addEventListener("click", async () => {
  $("error").textContent = "";
  const instruction = $("instruction").value.trim();
  if (!instruction) { $("error").textContent = "请先输入任务指令。"; return; }
  const key = (crypto.randomUUID ? crypto.randomUUID() : Date.now()+"-"+Math.random());
  $("submit").disabled = true;
  try {
    const r = await fetch("/api/v1/tasks", {
      method:"POST",
      headers:authHeaders({"Content-Type":"application/json","Idempotency-Key":key}),
      body:JSON.stringify({instruction,target_device_id:$("target").value,adapter:$("adapter").value,working_directory_id:"demo"})
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error?.message || "任务提交失败");
    $("instruction").value = "";
    watchedTasks.add(d.task.id);
    knownStatuses.set(d.task.id, d.task.status);
    await loadTasks();
  } catch(e) { $("error").textContent = e.message; }
  finally { $("submit").disabled = false; }
});
checkHealth();
loadTasks();
setInterval(() => {
  if (!document.hidden && $("token").value.trim()) loadTasks();
}, 3000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && $("token").value.trim()) loadTasks();
});
