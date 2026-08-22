const REPO = "wenjunqu-ldn/japanese-handbook";
const DATA = "data";
const TYPE_LABEL = {
  mcq: "选择题",
  fill_blank: "填空题",
  translation: "翻译题",
  correction: "改错题",
  conjugation: "变形题",
};

const el = {
  status: document.getElementById("status"),
  quiz: document.getElementById("quiz"),
  submit: document.getElementById("submit-btn"),
  result: document.getElementById("result"),
  score: document.getElementById("score"),
  scoreNote: document.getElementById("score-note"),
  reportLink: document.getElementById("report-link"),
  reportDone: document.getElementById("report-done"),
  copyBtn: document.getElementById("copy-btn"),
  retryBtn: document.getElementById("retry-btn"),
  datePicker: document.getElementById("date-picker"),
  streak: document.getElementById("streak"),
  pending: document.getElementById("pending"),
  pendingText: document.getElementById("pending-text"),
  pendingActions: document.getElementById("pending-actions"),
};

const PENDING_KEY = "jp-pending-results";
// What has already been answered on a given day, so a reload does not wipe it.
// Without this, reopening a day you had already submitted re-rendered every
// card blank, and the next 提交 graded those blanks as wrong — overwriting
// answers that were right and pushing those items back into the review queue.
const DAY_STATE_KEY = "jp-day-state";
const DAY_STATE_KEEP = 7;

let currentDay = null;
let graded = null;
// Numbering runs across the whole page, not per block: every input name, card
// lookup and feedback slot is keyed on it, so a batch appended later must not
// reuse a number the first batch already took.
let nextN = 0;
// The two blocks, each with its own container, its own 「再出 5 题」 button and
// its own queue of spare batches generated with the day.
let blocks = {};

/* ---------- helpers ---------- */

// 電車（でんしゃ）で → 電車で
const stripFurigana = (s) => s.replace(/（[ぁ-んァ-ヶー]+）/g, "");

// Loose comparison for free-text Japanese: ignore furigana, spaces and punctuation.
function normalize(s) {
  return stripFurigana(String(s || ""))
    .replace(/[\s　]/g, "")
    .replace(/[。、，,.!！?？「」『』()（）]/g, "")
    .trim();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

async function getJSON(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

/* ---------- rendering ---------- */

function renderExercise(ex, isReview) {
  const card = document.createElement("div");
  card.className = ex.block === "drill" ? "card drill" : "card";
  card.dataset.n = ex.n;

  const reviewTag = isReview ? '<span class="tag review">复习</span>' : "";
  let body = "";

  if (ex.type === "mcq") {
    body = `
      <p class="prompt">${escapeHtml(ex.prompt)}</p>
      <div class="options">
        ${ex.options
          .map(
            (opt, i) => `
          <label class="option" data-value="${escapeHtml(opt)}">
            <input type="radio" name="q${ex.n}" value="${escapeHtml(opt)}" id="q${ex.n}o${i}">
            <span>${escapeHtml(opt)}</span>
          </label>`
          )
          .join("")}
      </div>`;
  } else if (ex.type === "fill_blank") {
    body = `
      <p class="prompt">${escapeHtml(ex.prompt)}</p>
      <p class="sentence">${escapeHtml(ex.sentence)}</p>
      <p class="sentence-zh">${escapeHtml(ex.sentence_zh || "")}</p>
      <input type="text" name="q${ex.n}" autocomplete="off" autocapitalize="off"
             spellcheck="false" placeholder="填入空格处的词">
      ${ex.hint ? `<p class="hint">${escapeHtml(ex.hint)}</p>` : ""}`;
  } else if (ex.type === "conjugation") {
    body = `
      <p class="prompt">${escapeHtml(ex.prompt)}</p>
      <p class="sentence-zh">${escapeHtml(ex.verb_class || "")}　${escapeHtml(ex.meaning_zh || "")}</p>
      <input type="text" name="q${ex.n}" autocomplete="off" autocapitalize="off"
             spellcheck="false" placeholder="写出${escapeHtml(ex.form_label || "")}">`;
  } else if (ex.type === "correction") {
    body = `
      <p class="prompt">${escapeHtml(ex.prompt)}</p>
      <p class="sentence wrong-sentence">❌ ${escapeHtml(ex.wrong_sentence)}</p>
      <p class="sentence-zh">想表达：${escapeHtml(ex.sentence_zh || "")}</p>
      <input type="text" name="q${ex.n}" autocomplete="off" autocapitalize="off"
             spellcheck="false" placeholder="写出正确的句子">`;
  } else {
    body = `
      <p class="prompt">${escapeHtml(ex.prompt)}</p>
      <p class="sentence">${escapeHtml(ex.sentence_zh)}</p>
      <input type="text" name="q${ex.n}" autocomplete="off" autocapitalize="off"
             spellcheck="false" placeholder="写出日语句子">
      ${ex.hint ? `<p class="hint">${escapeHtml(ex.hint)}</p>` : ""}`;
  }

  card.innerHTML = `
    <div class="q-head">
      <strong>${escapeHtml(ex.label || `第 ${ex.n} 题`)}</strong>
      <span class="tag">${TYPE_LABEL[ex.type] || ex.type}</span>
      <span class="tag">${escapeHtml(ex.item_id)}</span>
      ${reviewTag}
    </div>
    ${body}`;
  return card;
}

function blockLabel(kind, index) {
  return kind === "drill" ? `变形 ${index}` : `第 ${index} 题`;
}

function appendBatch(kind, options) {
  const silent = options && options.silent;
  const block = blocks[kind];
  const batch = block.spare[block.used++];
  const reviewSet = new Set(currentDay.review_item_ids || []);
  let first = null;
  batch.forEach((ex) => {
    ex.n = ++nextN;
    ex.block = kind;
    ex.label = blockLabel(kind, ++block.count);
    const card = renderExercise(ex, reviewSet.has(ex.item_id));
    block.body.appendChild(card);
    currentDay.all.push(ex);
    if (!first) first = card;
  });
  // Adding questions after grading is allowed: the new cards are ungraded, so
  // the submit button comes back and grading picks up only what is unanswered.
  el.submit.hidden = false;
  if (block.used >= block.spare.length) block.more.remove();
  // Remember the batch even before it is answered, so a reload brings back the
  // questions rather than a shorter page.
  saveDayState();
  if (!silent && first) first.scrollIntoView({ behavior: "smooth", block: "center" });
}

function buildBlock(kind, heading, items, spare) {
  const wrap = document.createElement("div");
  wrap.className = `block block-${kind}`;

  if (heading) {
    const h = document.createElement("h2");
    h.className = "block-heading";
    h.textContent = heading;
    wrap.appendChild(h);
  }

  const body = document.createElement("div");
  wrap.appendChild(body);

  const block = { body, spare: spare || [], used: 0, count: 0, more: null };
  blocks[kind] = block;

  const reviewSet = new Set(currentDay.review_item_ids || []);
  items.forEach((ex) => {
    ex.n = ++nextN;
    ex.block = kind;
    ex.label = blockLabel(kind, ++block.count);
    body.appendChild(renderExercise(ex, reviewSet.has(ex.item_id)));
    currentDay.all.push(ex);
  });

  if (block.spare.length) {
    const more = document.createElement("button");
    more.type = "button";
    more.className = "btn more";
    more.textContent = `再出 ${block.spare[0].length} 题`;
    more.addEventListener("click", () => appendBatch(kind));
    const actions = document.createElement("div");
    actions.className = "block-actions";
    actions.appendChild(more);
    wrap.appendChild(actions);
    block.more = actions;
  }

  el.quiz.appendChild(wrap);
  return block;
}

function renderDay(day) {
  currentDay = day;
  graded = null;
  nextN = 0;
  blocks = {};
  currentDay.all = [];

  el.quiz.innerHTML = "";
  buildBlock("main", "", day.exercises, day.extra_exercises);

  // The drills are a second block: no sentence, no context, just form
  // conversion. Each block extends on its own, so more sentence questions can
  // be added without also adding conversions, and the other way round.
  if ((day.drills || []).length) {
    buildBlock("drill", "动词变形练习", day.drills, day.extra_drills);
  }

  el.status.hidden = true;
  el.quiz.hidden = false;
  el.submit.hidden = false;
  el.result.hidden = true;

  // Anything already answered on this day comes back with it. Grading only
  // looks at ungraded cards, so without this a reload turned answered
  // questions back into blanks and the next 提交 reported them as wrong.
  const saved = readDayState()[day.date];
  if (saved) restoreDay(saved);
}

/* ---------- grading ---------- */

function readAnswer(ex) {
  if (ex.type === "mcq") {
    const checked = el.quiz.querySelector(`input[name="q${ex.n}"]:checked`);
    return checked ? checked.value : "";
  }
  const input = el.quiz.querySelector(`input[name="q${ex.n}"]`);
  return input ? input.value : "";
}

function isCorrect(ex, given) {
  if (!given.trim()) return false;
  if (ex.type === "mcq") return given === ex.answer;
  const accepted = (ex.accepted || [ex.answer_plain || ex.answer]).map(normalize);
  return accepted.includes(normalize(given));
}

// Rough closeness, used only to soften the wording on free-text answers: a
// near miss is flagged as "check this yourself" rather than flatly wrong,
// since one Chinese sentence has many valid Japanese renderings.
function isNearMiss(ex, given) {
  if (ex.type === "mcq" || !given.trim()) return false;
  const target = normalize(ex.answer_plain || ex.answer);
  const mine = normalize(given);
  if (!target || !mine) return false;
  const shorter = mine.length < target.length ? mine : target;
  const longer = mine.length < target.length ? target : mine;
  let shared = 0;
  const pool = longer.split("");
  for (const ch of shorter) {
    const i = pool.indexOf(ch);
    if (i !== -1) { shared++; pool.splice(i, 1); }
  }
  return shared / longer.length >= 0.6;
}

function showFeedback(ex, given, correct) {
  const card = el.quiz.querySelector(`.card[data-n="${ex.n}"]`);
  card.classList.add(correct ? "correct" : "wrong");

  card.querySelectorAll("input").forEach((i) => (i.disabled = true));

  if (ex.type === "mcq") {
    card.querySelectorAll(".option").forEach((opt) => {
      const val = opt.dataset.value;
      if (val === ex.answer) opt.classList.add("is-answer");
      else if (val === given) opt.classList.add("is-chosen-wrong");
    });
  }

  const fb = document.createElement("div");
  fb.className = "feedback";
  const yourAnswer = given.trim() ? escapeHtml(given) : "（未作答）";
  const near = !correct && isNearMiss(ex, given);
  const verdict = correct ? "✓ 正确" : near ? "△ 与参考答案不同，请自行判断" : "✗ 不正确";
  fb.innerHTML =
    `<span class="verdict ${correct ? "ok" : near ? "near" : "no"}">${verdict}</span>\n` +
    (correct ? "" : `你的答案：${yourAnswer}\n`) +
    escapeHtml(ex.explanation);

  // Free-text answers have many valid forms; let the learner correct the machine.
  if (!correct && ex.type !== "mcq" && given.trim()) {
    const label = document.createElement("label");
    label.className = "override";
    label.innerHTML = `<input type="checkbox" data-override="${ex.n}"> 我的答案其实也对，按答对记录`;
    fb.appendChild(label);
  }

  card.appendChild(fb);
}

function updateScore() {
  const main = graded.filter((g) => !g.drill);
  const drill = graded.filter((g) => g.drill);
  const hit = (rows) => rows.filter((g) => g.correct).length;
  // The two blocks are scored apart: mixing them hides which half went wrong.
  el.score.textContent = drill.length
    ? `得分：${hit(main)} / ${main.length}　·　变形：${hit(drill)} / ${drill.length}`
    : `得分：${hit(main)} / ${main.length}`;
  const missed = graded.filter((g) => !g.correct);
  const notes = [
    missed.length
      ? `需要复习：${missed.map((m) => m.item_id).join("、")}`
      : "全部答对，明天会换新的知识点。",
  ];
  const payload = buildPayload();
  if (isTrimmed(payload)) {
    // Say so rather than silently dropping them: the scores still go in, but
    // the sentences that would have come back as correction questions do not.
    notes.push("题目较多，提交链接放不下你写的句子，只上报对错。要保留句子请用「复制结果 JSON」自建 issue。");
  }
  el.scoreNote.textContent = notes.join("　·　");
  el.reportLink.href = issueUrlFor(payload);
}

function buildPayload(options) {
  const lean = options && options.lean;
  const correct = [];
  const missed = [];
  const near = [];
  const given = {};
  for (const g of graded) {
    (g.correct ? correct : missed).push(g.item_id);
    // Report what was actually written on a missed free-text answer, so the
    // generator can hand the sentence back later as a correction question.
    // Multiple-choice picks are omitted: the wrong option is already known.
    if (!lean && !g.correct && g.type !== "mcq" && g.given && g.given.trim()) {
      given[g.item_id] = g.given.trim().slice(0, 300);
      // A near miss may well have been acceptable Japanese, so it is flagged
      // and never replayed as though it were definitely an error.
      if (g.near) near.push(g.item_id);
    }
  }
  // Id lists rather than a row per answer. With the 再出题 buttons a day can
  // reach 30 questions, and repeating the id, the type and "correct" on every
  // row pushed the prefilled issue URL past what GitHub accepts once the login
  // redirect wraps it — which is what produced the 500 on 2026-08-17. The
  // question type and the expected answer are both in the day's exercise file,
  // so the workflow reads them there instead of carrying them through the URL.
  const payload = { date: currentDay.date, correct, missed };
  if (near.length) payload.near = near;
  if (Object.keys(given).length) payload.given = given;
  return payload;
}

function buildIssueUrl() {
  return issueUrlFor(buildPayload());
}

function payloadBody(payload) {
  // Compact rather than pretty-printed: every space and newline is three bytes
  // in the URL, and the workflow is the only reader.
  return `由每日练习网页提交。\n\n` + "```json\n" + JSON.stringify(payload) + "\n```\n";
}

// GitHub rejects an over-long prefilled issue URL, and the login redirect it
// may pass through roughly doubles the length. Budget for that, not for the
// bare URL.
const MAX_ISSUE_URL = 3400;

function urlFrom(payload) {
  // `results` is the shape used before the id lists; a phone can still be
  // holding one in its pending queue, and its link has to keep working.
  const legacy = payload.results;
  const hit = legacy ? legacy.filter((r) => r.correct).length : (payload.correct || []).length;
  const answered = legacy ? legacy.length : hit + (payload.missed || []).length;
  const title = `练习结果 ${payload.date}（${hit}/${answered}）`;
  return (
    `https://github.com/${REPO}/issues/new` +
    `?labels=exercise-result` +
    `&title=${encodeURIComponent(title)}` +
    `&body=${encodeURIComponent(payloadBody(payload))}`
  );
}

function issueUrlFor(payload) {
  const url = urlFrom(payload);
  if (url.length <= MAX_ISSUE_URL || !payload.given) return url;
  // Only the learner's own sentences are big enough to matter. Dropping them
  // costs the later "here is what you wrote" question but keeps the scores,
  // which is much better than a link GitHub refuses to open.
  const lean = { date: payload.date, correct: payload.correct, missed: payload.missed };
  return urlFrom(lean);
}

function isTrimmed(payload) {
  return Boolean(payload.given) && urlFrom(payload).length > MAX_ISSUE_URL;
}

function grade() {
  // Only what has not been graded yet: pressing 再出 5 题 after submitting adds
  // fresh cards, and regrading the earlier ones would stack a second feedback
  // block onto every card and reset any "my answer was fine" overrides.
  const done = new Set((graded || []).map((g) => g.n));
  const fresh = (currentDay.all || []).filter((ex) => !done.has(ex.n));
  const rows = fresh.map((ex) => {
    const given = readAnswer(ex);
    const correct = isCorrect(ex, given);
    showFeedback(ex, given, correct);
    return {
      n: ex.n,
      item_id: ex.item_id,
      type: ex.type,
      drill: ex.block === "drill",
      correct,
      given,
      expected: ex.answer_plain || ex.answer || "",
      near: !correct && isNearMiss(ex, given),
    };
  });
  graded = [...(graded || []), ...rows];

  el.submit.hidden = true;
  el.result.hidden = false;
  updateScore();
  recordStreak();
  // Kept locally until reported, so a session finished offline — or a tab
  // closed before submitting — is not lost.
  queuePending(buildPayload());
  saveDayState();
  el.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- answers already given today ---------- */

function readDayState() {
  try {
    const raw = JSON.parse(localStorage.getItem(DAY_STATE_KEY) || "{}");
    return raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
  } catch (_) {
    return {};
  }
}

function writeDayState(map) {
  try {
    localStorage.setItem(DAY_STATE_KEY, JSON.stringify(map));
  } catch (_) {
    /* storage unavailable — the day simply will not survive a reload */
  }
}

function saveDayState() {
  if (!currentDay) return;
  const map = readDayState();
  map[currentDay.date] = {
    // How many extra batches were revealed, so the same questions come back.
    revealed: {
      main: blocks.main ? blocks.main.used : 0,
      drill: blocks.drill ? blocks.drill.used : 0,
    },
    // Keyed by item id rather than by card number: the number depends on how
    // many batches are on the page, the id does not.
    graded: (graded || []).map((g) => ({
      item_id: g.item_id,
      correct: g.correct,
      given: g.given,
    })),
  };
  // Only the recent days: this is a convenience, not a record. The repository
  // holds the real one.
  const keep = Object.keys(map).sort().reverse().slice(0, DAY_STATE_KEEP);
  writeDayState(Object.fromEntries(keep.map((d) => [d, map[d]])));
}

function dropDayState(date) {
  const map = readDayState();
  delete map[date];
  writeDayState(map);
}

function restoreAnswer(ex, given) {
  if (ex.type === "mcq") {
    el.quiz.querySelectorAll(`input[name="q${ex.n}"]`).forEach((input) => {
      if (input.value === given) input.checked = true;
    });
    return;
  }
  const input = el.quiz.querySelector(`input[name="q${ex.n}"]`);
  if (input) input.value = given || "";
}

function restoreDay(state) {
  for (const kind of ["main", "drill"]) {
    const want = (state.revealed || {})[kind] || 0;
    const block = blocks[kind];
    while (block && block.used < want && block.used < block.spare.length) {
      appendBatch(kind, { silent: true });
    }
  }

  const byId = new Map(currentDay.all.map((ex) => [ex.item_id, ex]));
  const rows = [];
  for (const saved of state.graded || []) {
    const ex = byId.get(saved.item_id);
    if (!ex) continue;
    const given = saved.given || "";
    restoreAnswer(ex, given);
    // Re-run the machine verdict rather than trusting the stored one, so the
    // card comes back exactly as it looked — including the "my answer was
    // actually fine" checkbox, which only appears on a machine-wrong answer.
    const machine = isCorrect(ex, given);
    showFeedback(ex, given, machine);
    if (saved.correct !== machine) {
      const box = el.quiz.querySelector(`input[data-override="${ex.n}"]`);
      if (box) box.checked = true;
      const card = el.quiz.querySelector(`.card[data-n="${ex.n}"]`);
      if (card) {
        card.classList.toggle("correct", saved.correct);
        card.classList.toggle("wrong", !saved.correct);
      }
    }
    rows.push({
      n: ex.n,
      item_id: ex.item_id,
      type: ex.type,
      drill: ex.block === "drill",
      correct: saved.correct,
      given,
      expected: ex.answer_plain || ex.answer || "",
      near: !saved.correct && isNearMiss(ex, given),
    });
  }

  if (!rows.length) return;
  graded = rows;
  el.result.hidden = false;
  el.submit.hidden = graded.length >= currentDay.all.length;
  updateScore();
}

/* ---------- pending results (offline queue) ---------- */

// Reporting a result opens a prefilled GitHub issue, which needs a connection.
// Offline, the payload is kept locally so a session done on the train is not
// lost; the app offers to submit it once there is a network again.

// Days already recorded in the repository. The pending queue survives until it
// is cleared by hand, and clearing is easy to forget — so the same day kept
// being offered and submitted again （2026-08-19 went in four times）. The
// workflow writes this list, so the app can simply check.
async function pruneSubmitted() {
  let dates;
  try {
    const index = await getJSON(`${DATA}/submitted.json`);
    dates = new Set(index.dates || []);
  } catch (err) {
    return; // offline or not generated yet — the manual button still works
  }
  const list = readPending();
  const keep = list.filter((p) => !dates.has(p.date));
  if (keep.length !== list.length) {
    writePending(keep);
    renderPending();
  }
}

function readPending() {
  try {
    const raw = JSON.parse(localStorage.getItem(PENDING_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch (_) {
    return [];
  }
}

function writePending(list) {
  try {
    localStorage.setItem(PENDING_KEY, JSON.stringify(list));
  } catch (_) {
    /* storage unavailable — nothing more we can do */
  }
}

function queuePending(payload) {
  const list = readPending().filter((p) => p.date !== payload.date);
  list.push(payload);
  writePending(list);
  renderPending();
}

function dropPending(date) {
  writePending(readPending().filter((p) => p.date !== date));
  renderPending();
}

function renderPending() {
  const shown = graded && currentDay ? currentDay.date : null;
  const list = readPending().filter((p) => p.date !== shown);
  if (!list.length) {
    el.pending.hidden = true;
    return;
  }
  el.pending.hidden = false;
  el.pendingText.textContent = navigator.onLine
    ? `有 ${list.length} 天的练习结果还没上报，点下面的按钮提交：`
    : `有 ${list.length} 天的练习结果已保存在本机，联网后即可提交。`;

  el.pendingActions.innerHTML = "";
  list.sort((a, b) => (a.date < b.date ? -1 : 1));
  for (const payload of list) {
    const link = document.createElement("a");
    link.className = "btn primary";
    link.textContent = `提交 ${payload.date}`;
    link.href = issueUrlFor(payload);
    link.target = "_blank";
    link.rel = "noopener";
    // The result stays queued after the link is opened. Clicking only means the
    // GitHub page was launched, not that the issue was created — it can fail, or
    // be abandoned — and dropping it here lost the day's answers for good.
    link.addEventListener("click", () => {
      const done = document.createElement("button");
      done.className = "btn";
      done.textContent = `已提交 ${payload.date}，清除`;
      done.addEventListener("click", () => dropPending(payload.date));
      link.replaceWith(done);
    });
    el.pendingActions.appendChild(link);

    const copy = document.createElement("button");
    copy.className = "btn";
    copy.textContent = "复制";
    copy.addEventListener("click", () => copyText(payloadBody(payload), copy, "复制"));
    el.pendingActions.appendChild(copy);
  }
  const clear = document.createElement("button");
  clear.className = "btn";
  clear.textContent = "全部清除";
  clear.addEventListener("click", () => {
    writePending([]);
    renderPending();
  });
  el.pendingActions.appendChild(clear);
}

/* ---------- streak (local only) ---------- */

function recordStreak() {
  try {
    const key = "jp-exercise-days";
    const days = new Set(JSON.parse(localStorage.getItem(key) || "[]"));
    days.add(currentDay.date);
    const sorted = [...days].sort();
    localStorage.setItem(key, JSON.stringify(sorted));
    renderStreak(sorted);
  } catch (_) {
    /* localStorage unavailable — streak display is optional */
  }
}

function renderStreak(days) {
  if (!days || !days.length) return;
  let streak = 0;
  const set = new Set(days);
  const cursor = new Date(days[days.length - 1] + "T00:00:00");
  while (set.has(cursor.toISOString().slice(0, 10))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  el.streak.textContent = `已练习 ${days.length} 天 · 连续 ${streak} 天`;
}

/* ---------- boot ---------- */

async function loadDate(date) {
  el.status.hidden = false;
  el.status.textContent = "正在加载练习……";
  el.quiz.hidden = true;
  el.submit.hidden = true;
  el.result.hidden = true;
  try {
    renderDay(await getJSON(`${DATA}/exercises/${date}.json`));
  } catch (err) {
    el.status.textContent = `无法加载 ${date} 的练习：${err.message}`;
  }
}

async function init() {
  try {
    renderStreak(JSON.parse(localStorage.getItem("jp-exercise-days") || "[]"));
  } catch (_) {
    /* ignore */
  }

  // Anything finished but not yet reported — typically a session done offline.
  renderPending();
  pruneSubmitted();

  let index;
  try {
    index = await getJSON(`${DATA}/index.json`);
  } catch (err) {
    el.status.textContent =
      "还没有生成任何练习。请先运行 exercise-generator/generate_exercises.py，或等待每日的 GitHub Actions 任务。";
    return;
  }

  const dates = index.dates || [];
  if (!dates.length) {
    el.status.textContent = "还没有生成任何练习。";
    return;
  }

  el.datePicker.innerHTML = dates.map((d) => `<option value="${d}">${d}</option>`).join("");
  const requested = new URLSearchParams(location.search).get("date");
  const start = dates.includes(requested) ? requested : index.latest || dates[0];
  el.datePicker.value = start;

  el.datePicker.addEventListener("change", () => loadDate(el.datePicker.value));
  await loadDate(start);
}

el.submit.addEventListener("click", (e) => {
  e.preventDefault();
  grade();
});

el.quiz.addEventListener("submit", (e) => e.preventDefault());

// "my answer was actually fine" toggle on free-text questions
el.quiz.addEventListener("change", (e) => {
  const n = e.target.dataset && e.target.dataset.override;
  if (!n || !graded) return;
  const entry = graded.find((g) => String(g.n) === n);
  if (!entry) return;
  entry.correct = e.target.checked;
  const card = el.quiz.querySelector(`.card[data-n="${n}"]`);
  card.classList.toggle("correct", e.target.checked);
  card.classList.toggle("wrong", !e.target.checked);
  updateScore();
  queuePending(buildPayload());
  saveDayState();
});

// Opening the GitHub page is not proof that the issue was created: it can fail,
// or be abandoned at the login screen. The result therefore stays on this device
// until the learner confirms it landed — dropping it here lost a whole day of
// answers the first time GitHub returned a 500.
el.reportLink.addEventListener("click", () => {
  el.reportDone.hidden = false;
});

el.reportDone.addEventListener("click", () => {
  if (currentDay) dropPending(currentDay.date);
  el.reportDone.hidden = true;
  el.reportDone.blur();
});

// 「再做一次」 means start the day over, so the stored answers go with it —
// otherwise the page would come straight back with every card already graded.
el.retryBtn.addEventListener("click", () => {
  dropDayState(el.datePicker.value);
  loadDate(el.datePicker.value);
});

window.addEventListener("online", () => {
  renderPending();
  pruneSubmitted();
});
window.addEventListener("offline", renderPending);

// Coming back from the GitHub tab is exactly when the day has just been
// recorded, so re-check instead of waiting for the next launch.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) pruneSubmitted();
});

async function copyText(text, button, label) {
  try {
    await navigator.clipboard.writeText(text);
    button.textContent = "已复制";
    setTimeout(() => (button.textContent = label), 1500);
  } catch (_) {
    window.prompt("复制下面的内容：", text);
  }
}

el.copyBtn.addEventListener("click", () =>
  copyText(payloadBody(buildPayload()), el.copyBtn, "复制结果 JSON")
);

init();
