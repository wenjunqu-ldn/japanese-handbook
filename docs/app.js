const REPO = "wenjunqu-ldn/japanese-handbook";
const DATA = "data";
const TYPE_LABEL = { mcq: "选择题", fill_blank: "填空题", translation: "翻译题" };

const el = {
  status: document.getElementById("status"),
  quiz: document.getElementById("quiz"),
  submit: document.getElementById("submit-btn"),
  result: document.getElementById("result"),
  score: document.getElementById("score"),
  scoreNote: document.getElementById("score-note"),
  reportLink: document.getElementById("report-link"),
  copyBtn: document.getElementById("copy-btn"),
  retryBtn: document.getElementById("retry-btn"),
  datePicker: document.getElementById("date-picker"),
  streak: document.getElementById("streak"),
};

let currentDay = null;
let graded = null;

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
  card.className = "card";
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
             spellcheck="false" placeholder="填入空格处的词">`;
  } else {
    body = `
      <p class="prompt">${escapeHtml(ex.prompt)}</p>
      <p class="sentence">${escapeHtml(ex.sentence_zh)}</p>
      <input type="text" name="q${ex.n}" autocomplete="off" autocapitalize="off"
             spellcheck="false" placeholder="写出日语句子">
      <p class="hint">${escapeHtml(ex.hint || "")}</p>`;
  }

  card.innerHTML = `
    <div class="q-head">
      <strong>第 ${ex.n} 题</strong>
      <span class="tag">${TYPE_LABEL[ex.type] || ex.type}</span>
      <span class="tag">${escapeHtml(ex.item_id)}</span>
      ${reviewTag}
    </div>
    ${body}`;
  return card;
}

function renderDay(day) {
  currentDay = day;
  graded = null;
  const reviewSet = new Set(day.review_item_ids || []);

  el.quiz.innerHTML = "";
  day.exercises.forEach((ex) => el.quiz.appendChild(renderExercise(ex, reviewSet.has(ex.item_id))));

  el.status.hidden = true;
  el.quiz.hidden = false;
  el.submit.hidden = false;
  el.result.hidden = true;
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
  if (ex.type === "fill_blank") {
    const accepted = (ex.accepted || [ex.answer]).map(normalize);
    return accepted.includes(normalize(given));
  }
  return normalize(given) === normalize(ex.answer_plain || ex.answer);
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
  fb.innerHTML =
    `<span class="verdict ${correct ? "ok" : "no"}">${correct ? "✓ 正确" : "✗ 不正确"}</span>\n` +
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
  const correctCount = graded.filter((g) => g.correct).length;
  el.score.textContent = `得分：${correctCount} / ${graded.length}`;
  const missed = graded.filter((g) => !g.correct);
  el.scoreNote.textContent = missed.length
    ? `需要复习：${missed.map((m) => m.item_id).join("、")}`
    : "全部答对，明天会换新的知识点。";
  el.reportLink.href = buildIssueUrl();
}

function buildPayload() {
  return {
    date: currentDay.date,
    results: graded.map((g) => ({ item_id: g.item_id, type: g.type, correct: g.correct })),
  };
}

function buildIssueUrl() {
  const payload = buildPayload();
  const correctCount = payload.results.filter((r) => r.correct).length;
  const title = `练习结果 ${payload.date}（${correctCount}/${payload.results.length}）`;
  const body =
    `由每日练习网页提交。\n\n` +
    "```json\n" +
    JSON.stringify(payload, null, 2) +
    "\n```\n";
  return (
    `https://github.com/${REPO}/issues/new` +
    `?labels=exercise-result` +
    `&title=${encodeURIComponent(title)}` +
    `&body=${encodeURIComponent(body)}`
  );
}

function grade() {
  graded = currentDay.exercises.map((ex) => {
    const given = readAnswer(ex);
    const correct = isCorrect(ex, given);
    showFeedback(ex, given, correct);
    return { n: ex.n, item_id: ex.item_id, type: ex.type, correct, given };
  });

  el.submit.hidden = true;
  el.result.hidden = false;
  updateScore();
  recordStreak();
  el.result.scrollIntoView({ behavior: "smooth", block: "nearest" });
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
});

el.retryBtn.addEventListener("click", () => loadDate(el.datePicker.value));

el.copyBtn.addEventListener("click", async () => {
  const text = "```json\n" + JSON.stringify(buildPayload(), null, 2) + "\n```";
  try {
    await navigator.clipboard.writeText(text);
    el.copyBtn.textContent = "已复制";
    setTimeout(() => (el.copyBtn.textContent = "复制结果 JSON"), 1500);
  } catch (_) {
    window.prompt("复制下面的内容：", text);
  }
});

init();
