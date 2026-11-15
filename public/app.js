// Between dashboard. Uses the LifeBrain API, including /api/plan from the gap engine.

const state = {
  tasks: [], inbox: [], stats: {}, plan: [], fitCount: 0,
  freeNow: 0, freeNote: "", userSetMinutes: false, questions: [],
};
const $ = (id) => document.getElementById(id);

// Task ids whose "Log time" box is open, and overruns the user chose to keep.
const openLogs = new Set();
const keptOverruns = new Set();

const escapeHtml = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

// Phone token: arrives once as ?token=… in the link, is kept in this browser,
// and is sent as a header on every API call. It's removed from the address bar
// right away so it doesn't stay in history or get shared in a screenshot.
const TOKEN_KEY = "between-token";
let memoryToken = "";

function saveTokenFromUrl() {
  const url = new URL(window.location.href);
  const token = url.searchParams.get("token");
  if (!token) return;
  memoryToken = token;
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch (err) {
    // Private mode or blocked storage: keep it for this page only.
  }
  url.searchParams.delete("token");
  window.history.replaceState(null, "", url.pathname + url.search + url.hash);
}

function phoneToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || memoryToken;
  } catch (err) {
    return memoryToken;
  }
}

saveTokenFromUrl();

async function api(path, options = {}) {
  const { headers = {}, ...rest } = options;
  const token = phoneToken();
  const res = await fetch(path, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { "X-Life-Brain-Token": token } : {}),
      ...headers,
    },
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401) {
    throw new Error("This device needs the Between link with ?token= once. Open it again from your setup link.");
  }
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 3000);
}

function setStatus(text, ok) {
  const el = $("status");
  el.textContent = text;
  el.className = "status " + (ok ? "ok" : "bad");
}

function openTasks() {
  return state.tasks.filter((t) => t.status === "open");
}

// Time logging. The server returns logged_minutes for each task.
function loggedOf(task) {
  return Number(task.logged_minutes) || 0;
}

function remainingOf(task) {
  if (!task.duration_minutes) return null;
  return Math.max(task.duration_minutes - loggedOf(task), 0);
}

function isOverrun(task) {
  return Boolean(task.duration_minutes) && loggedOf(task) > task.duration_minutes;
}

// Same rule as the server: next 15-minute mark after logged time plus a 60-minute buffer.
function suggestedEstimate(task) {
  return Math.ceil((loggedOf(task) + 60) / 15) * 15;
}

const CATEGORY_NAMES = {
  urgent_important: "Urgent & important",
  urgent: "Urgent",
  important: "Important",
};
const CATEGORY_ORDER = ["urgent_important", "urgent", "important"];

function taskMeta(task) {
  const parts = [];
  if (task.duration_minutes) parts.push(`${task.duration_minutes} min`);
  if (loggedOf(task)) parts.push(`${loggedOf(task)} logged`);
  if (task.duration_minutes && !isOverrun(task)) parts.push(`${remainingOf(task)} left`);
  if (task.due_date && task.due_text && task.due_date !== task.due_text) parts.push(`due ${task.due_text} (${task.due_date})`);
  else if (task.due_date || task.due_text) parts.push(`due ${task.due_date || task.due_text}`);
  return parts.join(" · ");
}

function progressBar(task) {
  if (!task.duration_minutes) return "";
  const pct = Math.min(100, Math.round((loggedOf(task) / task.duration_minutes) * 100));
  return `<div class="bar ${isOverrun(task) ? "over" : ""}" aria-hidden="true"><span style="width:${pct}%"></span></div>`;
}

function overrunBox(task) {
  if (!isOverrun(task) || keptOverruns.has(task.id)) return "";
  const over = loggedOf(task) - task.duration_minutes;
  const suggested = suggestedEstimate(task);
  return `
    <div class="overrun">
      Over by ${over} min. Update the estimate to ${suggested} min?
      <div class="actions">
        <button class="ghost" data-estimate="${task.id}" data-minutes="${suggested}">Update estimate</button>
        <button class="ghost" data-keep="${task.id}">Keep it</button>
      </div>
    </div>`;
}

function taskRow(task, { checkbox = true } = {}) {
  const logOpen = openLogs.has(task.id);
  return `
    <li class="item" data-task="${task.id}">
      ${checkbox ? `<input type="checkbox" class="check" data-done="${task.id}" aria-label="Mark done">` : ""}
      <div class="item-body">
        <div class="item-title">${escapeHtml(task.title)}</div>
        <div class="item-meta">${escapeHtml(taskMeta(task))}</div>
        ${progressBar(task)}
        ${overrunBox(task)}
        <div class="actions">
          <button class="ghost" data-log-open="${task.id}">${logOpen ? "Close" : "Log time"}</button>
          <button class="ghost" data-skip="${task.id}">Not today</button>
        </div>
        <form class="log-form ${logOpen ? "" : "hidden"}" data-log-form="${task.id}">
          <input type="number" min="1" max="720" inputmode="numeric" placeholder="minutes" aria-label="Minutes worked" required>
          <button type="submit" class="primary">Save</button>
        </form>
      </div>
    </li>`;
}

// The server's gap engine decides what fits and in what order.
function planRow(item) {
  const label = item.kind === "finish" ? "Finish it" : "Make progress";
  return `
    <li class="item">
      <div class="item-body">
        <div class="item-title">${escapeHtml(item.title)}</div>
        <div class="item-meta">${label} · ${item.minutes} min</div>
      </div>
    </li>`;
}

function renderFits() {
  $("fits").innerHTML = state.plan.map(planRow).join("");
  $("fits-empty").classList.toggle("hidden", state.plan.length > 0);
  $("stat-fits").textContent = state.fitCount;
}

// Reads free time from Google Calendar. Until you type a number, "I have" follows the calendar.
async function loadFreeTime() {
  try {
    const data = await api("/api/free-time");
    const gaps = data.gaps || [];
    state.freeNow = data.free_now_minutes || 0;
    if (data.source !== "Google Calendar") {
      state.freeNote = "Connect Google Calendar to fill this in automatically.";
    } else if (state.freeNow > 0) {
      state.freeNote = `Your calendar says ${state.freeNow} min free right now.`;
    } else if (gaps.length) {
      const next = gaps[0];
      state.freeNote = `Next free stretch: ${next.start} to ${next.end} (${next.minutes} min).`;
    } else {
      state.freeNote = "Your calendar has no free time left today.";
    }
    if (!state.userSetMinutes) {
      const suggested = state.freeNow || (gaps[0] ? gaps[0].minutes : 0);
      if (suggested > 0) $("minutes").value = Math.min(480, suggested);
    }
  } catch (err) {
    state.freeNote = "";
  }
  $("calendar-note").textContent = state.freeNote;
}

// Today's plan: the sessions Between placed in your free time today.
async function loadToday() {
  let data = { blocks: [], unplaced: 0, note: "" };
  try {
    data = await api("/api/today");
  } catch (err) {
    data.note = err.message;
  }
  const blocks = data.blocks || [];
  $("today").innerHTML = blocks.map((b) => `
    <li class="item" data-task="${b.task_id}">
      <div class="item-body">
        <div class="item-title">${escapeHtml(b.start)}–${escapeHtml(b.end)} · ${escapeHtml(b.title)}</div>
        <div class="item-meta">${escapeHtml(CATEGORY_NAMES[b.category] || "")} · ${b.minutes} min${b.reason ? " · " + escapeHtml(b.reason) : ""}</div>
      </div>
    </li>`).join("");
  $("today-empty").classList.toggle("hidden", blocks.length > 0);
  const notes = [];
  if (data.unplaced) notes.push(`${data.unplaced} task${data.unplaced === 1 ? "" : "s"} didn't fit in the next two weeks`);
  if (data.note) notes.push(data.note);
  $("today-note").textContent = notes.join(" · ");
}

// Follow-up questions Gemini asked about new captures.
async function loadQuestions() {
  try {
    const data = await api("/api/questions");
    state.questions = data.questions || [];
  } catch (err) {
    state.questions = [];
  }
  renderQuestions();
}

let lastQuestionsKey = "";

function renderQuestions() {
  $("questions-card").classList.toggle("hidden", state.questions.length === 0);
  // Only redraw when the questions actually changed, so typed answers survive refreshes.
  const key = JSON.stringify(state.questions);
  if (key === lastQuestionsKey) return;
  lastQuestionsKey = key;
  $("questions").innerHTML = state.questions.map((q) => `
    <li class="item">
      <div class="item-body">
        <div class="item-title">${escapeHtml(q.question)}</div>
        <div class="item-meta">About: ${escapeHtml(q.task_title)}</div>
        <form class="answer-form" data-answer-form="${q.id}">
          <input type="text" required placeholder="${q.field === "minutes" ? "e.g. 45 min" : "e.g. Friday"}" aria-label="Your answer">
          <button type="submit" class="primary">Save</button>
        </form>
      </div>
    </li>`).join("");
}

// "Not today": takes the task off today's plan (back tomorrow) and counts the skip.
// After two skips, a non-urgent task also goes behind others with the same deadline.
async function skipTask(taskId) {
  try {
    const result = await api(`/api/tasks/${taskId}/skip`, { method: "POST", body: "{}" });
    toast(result.reason || "Okay, we'll try it another time.");
    await load();
  } catch (err) {
    toast(err.message);
  }
}

async function refreshPlan() {
  const minutes = Math.max(1, Math.min(480, Number($("minutes").value) || 0));
  try {
    const data = await api(`/api/plan?minutes=${minutes}`);
    state.plan = data.plan || [];
    state.fitCount = data.fits || 0;
  } catch (err) {
    state.plan = [];
    state.fitCount = 0;
  }
  renderFits();
}

function renderTasks() {
  const open = openTasks();
  $("tasks").innerHTML = CATEGORY_ORDER.map((key) => {
    const group = open.filter((t) => t.category === key);
    if (!group.length) return "";
    const heading = `<li class="category-title">${CATEGORY_NAMES[key]} · ${group.length}</li>`;
    return heading + group.map((t) => taskRow(t)).join("");
  }).join("");
  $("tasks-empty").classList.toggle("hidden", open.length > 0);
  $("stat-open").textContent = open.length;
  $("stat-done").textContent = state.tasks.filter((t) => t.status === "done").length;
}

function renderReview() {
  const review = state.inbox.filter((i) => i.status === "review");
  $("review").innerHTML = review.map((item) => `
    <li class="item">
      <div class="item-body">
        <div class="item-title">${escapeHtml(item.raw_text)}</div>
        <div class="actions">
          <button class="ghost" data-convert="task" data-id="${item.id}">Make task</button>
          <button class="ghost" data-convert="note" data-id="${item.id}">Make note</button>
          <button class="ghost" data-archive="${item.id}">Archive</button>
        </div>
      </div>
    </li>`).join("");
  $("review-empty").classList.toggle("hidden", review.length > 0);
  $("stat-review").textContent = review.length;
}

function render() {
  renderTasks();
  renderFits();
  renderReview();
}

async function load() {
  try {
    const data = await api("/api/state");
    state.tasks = data.tasks || [];
    state.inbox = data.inbox || [];
    state.stats = data.stats || {};
    setStatus("Connected", true);
    render();
    await loadFreeTime();
    await refreshPlan();
    await loadQuestions();
    await loadToday();
  } catch (err) {
    setStatus("Offline", false);
    toast(err.message);
  }
}

async function addCapture(event) {
  event.preventDefault();
  const text = $("capture-text").value.trim();
  if (!text) {
    toast("Type something first.");
    return;
  }
  try {
    await api("/api/capture", {
      method: "POST",
      body: JSON.stringify({ text, source: $("capture-source").value }),
    });
    $("capture-text").value = "";
    toast("Captured.");
    await load();
  } catch (err) {
    toast(err.message);
  }
}

async function markDone(id) {
  try {
    await api(`/api/tasks/${id}`, { method: "PATCH", body: JSON.stringify({ status: "done" }) });
    await load();
  } catch (err) {
    toast(err.message);
  }
}

async function logTime(id, minutes) {
  try {
    await api(`/api/tasks/${id}/log`, { method: "POST", body: JSON.stringify({ minutes }) });
    openLogs.delete(Number(id));
    toast(`Logged ${minutes} min.`);
    await load();
  } catch (err) {
    toast(err.message);
  }
}

async function setEstimate(id, minutes) {
  try {
    await api(`/api/tasks/${id}/estimate`, {
      method: "POST",
      body: JSON.stringify({ duration_minutes: minutes }),
    });
    keptOverruns.delete(Number(id));
    toast(`Estimate set to ${minutes} min.`);
    await load();
  } catch (err) {
    toast(err.message);
  }
}

async function convert(id, kind) {
  try {
    await api(`/api/inbox/${id}/convert`, { method: "POST", body: JSON.stringify({ kind }) });
    await load();
  } catch (err) {
    toast(err.message);
  }
}

async function archive(id) {
  try {
    await api(`/api/inbox/${id}`, { method: "PATCH", body: JSON.stringify({ status: "archived" }) });
    await load();
  } catch (err) {
    toast(err.message);
  }
}

function toggleLog(id) {
  const key = Number(id);
  if (openLogs.has(key)) {
    openLogs.delete(key);
  } else {
    openLogs.add(key);
  }
  render();
  const form = document.querySelector(`[data-log-form="${id}"]`);
  if (form && openLogs.has(key)) form.querySelector("input").focus();
}

document.addEventListener("DOMContentLoaded", () => {
  $("capture-form").addEventListener("submit", addCapture);
  let planTimer;
  $("minutes").addEventListener("input", () => {
    state.userSetMinutes = true;
    clearTimeout(planTimer);
    planTimer = setTimeout(refreshPlan, 250);
  });

  // One delegated listener handles every row action.
  document.body.addEventListener("change", (event) => {
    const id = event.target.dataset.done;
    if (id) markDone(id);
  });

  document.body.addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    if (button.dataset.skip) skipTask(button.dataset.skip);
    if (button.dataset.convert) convert(button.dataset.id, button.dataset.convert);
    if (button.dataset.archive) archive(button.dataset.archive);
    if (button.classList.contains("chip")) {
      state.userSetMinutes = true;
      $("minutes").value = button.dataset.minutes;
      refreshPlan();
    }
    if (button.dataset.logOpen) toggleLog(button.dataset.logOpen);
    if (button.dataset.estimate) setEstimate(button.dataset.estimate, Number(button.dataset.minutes));
    if (button.dataset.keep) {
      keptOverruns.add(Number(button.dataset.keep));
      render();
    }
  });

  document.body.addEventListener("submit", async (event) => {
    const answerForm = event.target.closest("[data-answer-form]");
    if (answerForm) {
      event.preventDefault();
      const answer = answerForm.querySelector("input").value.trim();
      try {
        await api(`/api/questions/${answerForm.dataset.answerForm}/answer`, {
          method: "POST",
          body: JSON.stringify({ answer }),
        });
        toast("Got it. Pip updated the task.");
        await load();
      } catch (err) {
        toast(err.message);
      }
      return;
    }
    const form = event.target.closest("[data-log-form]");
    if (!form) return;
    event.preventDefault();
    const minutes = Number(form.querySelector("input").value);
    if (!Number.isInteger(minutes) || minutes < 1 || minutes > 720) {
      toast("Enter a whole number of minutes from 1 to 720.");
      return;
    }
    logTime(form.dataset.logForm, minutes);
  });

  load();
  // Pause refreshes while a log box or an answer box is in use so typing isn't wiped.
  setInterval(() => {
    const logOpen = document.querySelector(".log-form:not(.hidden)");
    const answering = [...document.querySelectorAll(".answer-form input")].some(
      (input) => input.value.trim() || document.activeElement === input
    );
    if (!logOpen && !answering) load();
  }, 30000);
});
