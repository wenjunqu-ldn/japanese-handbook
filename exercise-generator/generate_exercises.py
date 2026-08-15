#!/usr/bin/env python3
"""Generate the daily set of 5 Japanese exercises.

Implements EXERCISE_GENERATION_GUIDE.md: selection is driven by the handbook,
the learner's answer history and a per-item mastery score, not by chance.

Outputs:
  docs/data/exercises/YYYY-MM-DD.json   today's 5 exercises
  docs/data/index.json                  list of available dates (newest first)
  docs/data/history.jsonl               one line per generated day (items served)
  docs/data/mastery.json                per-item learning state (guide §15)

Usage:
  python3 exercise-generator/generate_exercises.py [--date YYYY-MM-DD] [--count 5] [--force]
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
from datetime import date, datetime
from pathlib import Path

from itembank import load_confusion_map, load_item_bank

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
EXERCISE_DIR = DATA_DIR / "exercises"
HISTORY_PATH = DATA_DIR / "history.jsonl"
MISTAKES_PATH = DATA_DIR / "mistakes.jsonl"
ATTEMPTS_PATH = DATA_DIR / "attempts.jsonl"
INDEX_PATH = DATA_DIR / "index.json"
MASTERY_PATH = DATA_DIR / "mastery.json"

FURIGANA_RE = re.compile(r"（[ぁ-んァ-ヶー]+）")

# --- selection knobs (guide §5) ---
BASE_WEIGHT = 1.0
WEAK_BONUS = 6.0           # weight added for a completely unmastered item
RECENT_PENALTY = 0.12      # damping for items served recently and known
WEAK_RECENT_PENALTY = 0.8  # much milder damping for items still being got wrong
RECENT_WINDOW = 10
REVIEW_SLOTS = 2           # reserved slots per day for items not yet mastered
MASTERY_THRESHOLD = 0.75   # at or above this an item counts as mastered
SPACED_DAYS = 14           # a mastered item becomes eligible again after this long


def strip_furigana(text: str) -> str:
    """'電車（でんしゃ）で' -> '電車で' — used for building answer targets."""
    return FURIGANA_RE.sub("", text)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


# ---------------------------------------------------------------- mastery


def build_mastery(attempts: list[dict], mistakes: list[dict]) -> dict[str, dict]:
    """Per-item learning state, as described in guide §15.

    mastery is a smoothed success rate biased by the current streak, so an item
    answered right three times running settles high, while one recently missed
    drops sharply regardless of its lifetime average.
    """
    events: dict[str, list[dict]] = {}

    for row in attempts:
        item_id = row.get("item_id")
        if item_id:
            events.setdefault(item_id, []).append(
                {"date": row.get("date", ""), "correct": bool(row.get("correct"))}
            )

    # Older logs recorded only misses; fold those in for items with no attempt row.
    logged = {a.get("item_id") for a in attempts}
    for row in mistakes:
        item_id = row.get("item_id")
        if item_id and item_id not in logged:
            events.setdefault(item_id, []).append({"date": row.get("date", ""), "correct": False})

    state: dict[str, dict] = {}
    for item_id, rows in events.items():
        rows.sort(key=lambda r: r["date"])
        correct = sum(1 for r in rows if r["correct"])
        wrong = len(rows) - correct

        streak = 0
        for r in reversed(rows):
            if r["correct"]:
                streak += 1
            else:
                break

        last_wrong = next((r["date"] for r in reversed(rows) if not r["correct"]), None)

        # Laplace-smoothed rate, then lifted toward 1 by the current streak so
        # recent consecutive successes count for more than old failures.
        rate = (correct + 1) / (len(rows) + 2)
        mastery = min(1.0, rate + 0.10 * min(streak, 3))

        state[item_id] = {
            "item_id": item_id,
            "correct_count": correct,
            "wrong_count": wrong,
            "streak": streak,
            "last_seen": rows[-1]["date"],
            "last_wrong": last_wrong,
            "mastery": round(mastery, 3),
        }
    return state


def _days_between(earlier: str, later: str) -> int:
    try:
        a = datetime.strptime(earlier, "%Y-%m-%d")
        b = datetime.strptime(later, "%Y-%m-%d")
    except (ValueError, TypeError):
        return 0
    return (b - a).days


def build_weights(
    bank: list[dict], history: list[dict], mastery: dict[str, dict], today: str
) -> dict[str, float]:
    """Guide §5: recent errors first, then weak items, then spaced review."""
    recent_ids: set[str] = set()
    for row in history[-RECENT_WINDOW:]:
        recent_ids.update(row.get("item_ids", []))

    weights = {}
    for item in bank:
        state = mastery.get(item["id"])
        score = state["mastery"] if state else None

        if score is None:
            # Never attempted — normal priority, it still needs a first outing.
            weight = BASE_WEIGHT
            mastered = False
        else:
            mastered = score >= MASTERY_THRESHOLD
            # The weaker the item, the heavier it weighs.
            weight = BASE_WEIGHT + WEAK_BONUS * (1.0 - score)
            if mastered and state.get("last_seen"):
                # Spaced review: a mastered item fades, then returns (guide §5.3).
                gap = _days_between(state["last_seen"], today)
                if gap >= SPACED_DAYS:
                    weight += 1.5

        if item["id"] in recent_ids:
            weight *= RECENT_PENALTY if mastered else WEAK_RECENT_PENALTY

        weights[item["id"]] = max(weight, 0.01)
    return weights


# Drill-type categories are numerous (100 verb rows alone) and would otherwise
# crowd a day out; cap how many of each can appear in one set.
CATEGORY_CAPS = {"verb_form": 2, "mistake": 2}


def weighted_sample(
    bank: list[dict],
    weights: dict[str, float],
    count: int,
    rng: random.Random,
    already: list[dict] | None = None,
) -> list[dict]:
    pool = list(bank)
    chosen: list[dict] = []

    used: dict[str, int] = {}
    for item in already or []:
        used[item["category"]] = used.get(item["category"], 0) + 1

    def allowed(item: dict) -> bool:
        cap = CATEGORY_CAPS.get(item["category"])
        return cap is None or used.get(item["category"], 0) < cap

    for _ in range(min(count, len(pool))):
        eligible = [i for i in pool if allowed(i)]
        if not eligible:
            eligible = pool  # caps are a preference, never a reason to under-fill
        total = sum(weights[i["id"]] for i in eligible)
        if total <= 0:
            break
        target = rng.uniform(0, total)
        upto = 0.0
        for item in eligible:
            upto += weights[item["id"]]
            if upto >= target:
                chosen.append(item)
                pool.remove(item)
                used[item["category"]] = used.get(item["category"], 0) + 1
                break
    return chosen


# ---------------------------------------------------------------- distractors


def _distractors(
    item: dict,
    bank: list[dict],
    field: str,
    rng: random.Random,
    confusion: dict[str, set[str]],
    n: int = 3,
) -> list[str]:
    """Wrong options that are actually tempting (guide §8.1).

    Preference order, most confusable first:
      1. items the handbook itself flags as easily confused with this one
      2. same part of speech and same thematic section
      3. same part of speech
      4. same category
    """
    by_id = {b["id"]: b for b in bank}

    def usable(b: dict) -> bool:
        return (
            b["id"] != item["id"]
            and b.get(field)
            and b[field] != item.get(field)
        )

    tiers: list[list[dict]] = []

    confusable = [by_id[i] for i in confusion.get(item["id"], set()) if i in by_id]
    tiers.append([b for b in confusable if usable(b)])

    same_cat = [b for b in bank if usable(b) and b["category"] == item["category"]]
    if item.get("pos"):
        same_pos = [b for b in same_cat if b.get("pos") == item["pos"]]
        if item.get("duo_section"):
            tiers.append([b for b in same_pos if b.get("duo_section") == item["duo_section"]])
        tiers.append(same_pos)
    elif item.get("duo_section"):
        tiers.append([b for b in same_cat if b.get("duo_section") == item["duo_section"]])

    tiers.append(same_cat)
    tiers.append([b for b in bank if usable(b)])

    picked: list[str] = []
    seen: set[str] = {item.get(field)}
    for tier in tiers:
        candidates = [b for b in tier if b[field] not in seen]
        rng.shuffle(candidates)
        for b in candidates:
            if len(picked) >= n:
                break
            picked.append(b[field])
            seen.add(b[field])
        if len(picked) >= n:
            break
    return picked


# ---------------------------------------------------------------- builders


def _label(item: dict) -> str:
    if item.get("reading"):
        return f"{item['term']}（{item['reading']}）"
    return item["term"]


def make_mcq_meaning(item: dict, bank: list[dict], rng: random.Random, confusion) -> dict | None:
    """MCQ: given the Japanese word/pattern, choose the Chinese meaning."""
    if not item.get("meaning_zh") or item["category"] in ("mistake", "verb_form"):
        return None
    wrong = _distractors(item, bank, "meaning_zh", rng, confusion)
    if len(wrong) < 3:
        return None
    options = wrong + [item["meaning_zh"]]
    rng.shuffle(options)
    return {
        "type": "mcq",
        "item_id": item["id"],
        "prompt": f"「{_label(item)}」的意思是？",
        "options": options,
        "answer": item["meaning_zh"],
        "explanation": f"{item['id']}　{_label(item)}：{item['meaning_zh']}",
        "source": item["source"],
    }


def make_mcq_reading(item: dict, bank: list[dict], rng: random.Random, confusion) -> dict | None:
    """MCQ: given the kanji word, choose the correct kana reading."""
    reading = item.get("reading")
    if not reading or item["category"] not in ("vocab", "verb_form"):
        return None
    if not re.search(r"[一-鿿]", item["term"]):
        return None
    wrong = _distractors(item, bank, "reading", rng, confusion)
    if len(wrong) < 3:
        return None
    options = wrong + [reading]
    rng.shuffle(options)
    return {
        "type": "mcq",
        "item_id": item["id"],
        "prompt": f"「{item['term']}」的读音是？",
        "options": options,
        "answer": reading,
        "explanation": f"{item['id']}　{item['term']}（{reading}）：{item['meaning_zh']}",
        "source": item["source"],
    }


def _verb_stem(word: str) -> str:
    """紹介する → 紹介, 治る → 治, 苦い → 苦 — the part that survives conjugation."""
    if len(word) < 2:
        return word
    if word.endswith("する"):
        return word[:-2] or word
    if re.search(r"[ぁ-ん]$", word):
        return word[:-1] or word
    return word


def stem_candidates(item: dict) -> list[str]:
    """Strings that might literally appear in an example sentence for this item."""
    term = item["term"]

    if item["category"] == "particle":
        return [term]

    if item["category"] == "vocab":
        stem = _verb_stem(term)
        return [term, stem] if stem != term else [term]

    candidates: list[str] = []
    for alternative in re.split(r"[／/]", term):
        cleaned = re.sub(r"（[^）]*）", "", alternative).strip().strip("～")
        if not cleaned:
            continue
        # "普通形＋と思う" — only the trailing literal part appears in the sentence.
        if "＋" in cleaned:
            cleaned = cleaned.split("＋")[-1].strip()
        if not cleaned:
            continue
        # No verb-stem trimming here: chopping the tail off a grammar pattern
        # (～ようになる → ようにな) would blank half of it and leave the rest
        # dangling in the sentence.
        candidates.append(cleaned)

    seen, out = set(), []
    for c in candidates + [term]:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def make_fill_blank(item: dict, rng: random.Random, avoid: set[str] | None = None) -> dict | None:
    """Fill in the blank: remove the target word from one of its example sentences."""
    if item["category"] in ("mistake", "verb_form"):
        return None
    term = item["term"]
    candidates = stem_candidates(item)
    avoid = avoid or set()

    examples = list(item["examples"])
    rng.shuffle(examples)
    # Prefer a sentence this item has not been tested on before (guide §6).
    examples.sort(key=lambda e: e["ja"] in avoid)

    found = None
    for candidate_example in examples:
        plain = strip_furigana(candidate_example["ja"])
        # Blank a span only when it occurs exactly once, otherwise it is ambiguous
        # which occurrence the learner is meant to supply.
        stem = next((c for c in candidates if plain.count(c) == 1), None)
        if stem:
            found = (candidate_example, plain, stem)
            break

    if not found:
        return None

    example, plain, stem = found
    sentence = example["ja"]
    blanked_plain = plain.replace(stem, "＿＿＿", 1)

    return {
        "type": "fill_blank",
        "item_id": item["id"],
        "prompt": "在空格处填入合适的词（可写汉字或假名）：",
        "sentence": blanked_plain,
        "sentence_zh": example["zh"],
        "answer": stem,
        "accepted": sorted({s for s in (stem, term, item.get("reading"), strip_furigana(term)) if s}),
        "explanation": f"{item['id']}　完整句子：{sentence}\n{example['zh']}\n{_label(item)}：{item['meaning_zh']}",
        "source": item["source"],
        "probe": example["ja"],
    }


def make_translation(item: dict, rng: random.Random, avoid: set[str] | None = None) -> dict | None:
    """One-sentence translation from Chinese to Japanese."""
    if item["category"] in ("mistake", "verb_form") or not item["examples"]:
        return None
    avoid = avoid or set()
    examples = list(item["examples"])
    rng.shuffle(examples)
    examples.sort(key=lambda e: e["ja"] in avoid)
    example = examples[0]

    return {
        "type": "translation",
        "item_id": item["id"],
        "prompt": "把下面的中文翻译成日语：",
        "sentence_zh": example["zh"],
        "hint": f"提示：使用 {_label(item)}",
        "answer": example["ja"],
        "answer_plain": strip_furigana(example["ja"]),
        # Grading free text against one reference is inherently rough, so the app
        # treats a near miss as "check it yourself" rather than a hard failure.
        "accepted": [strip_furigana(example["ja"])],
        "explanation": f"{item['id']}　参考答案：{example['ja']}\n{item['term']}：{item['meaning_zh']}",
        "source": item["source"],
        "probe": example["ja"],
    }


def make_correction(item: dict, rng: random.Random) -> dict | None:
    """Error correction, built from a recorded mistake (guide §8.3)."""
    if item["category"] != "mistake" or not item.get("corrections"):
        return None
    # Only genuine errors become "fix this" questions. Entries the handbook marks
    # △ are grammatical but less idiomatic, and become a naturalness MCQ instead.
    if item.get("severity") != "error":
        return None

    correct = item["corrections"][0]
    accepted = [strip_furigana(c["ja"]) for c in item["corrections"]]

    intent = item.get("intent_zh") or correct.get("zh", "")
    return {
        "type": "correction",
        "item_id": item["id"],
        "prompt": "下面的句子有错误，请改成正确的说法：",
        "wrong_sentence": strip_furigana(item["wrong"]),
        "sentence_zh": intent,
        "answer": correct["ja"],
        "answer_plain": strip_furigana(correct["ja"]),
        "accepted": accepted,
        "explanation": (
            f"{item['id']}　❌ {item['wrong']}\n"
            f"✅ {correct['ja']}\n{correct.get('zh','')}\n\n{item.get('why','')}"
        ),
        "source": item["source"],
    }


def make_naturalness(item: dict, rng: random.Random) -> dict | None:
    """Two-option 'which is more natural' MCQ from a △ entry (guide §12)."""
    if item["category"] != "mistake" or item.get("severity") != "unnatural":
        return None
    if not item.get("corrections"):
        return None

    better = item["corrections"][0]["ja"]
    worse = item["wrong"]
    options = [strip_furigana(better), strip_furigana(worse)]
    rng.shuffle(options)

    return {
        "type": "mcq",
        "item_id": item["id"],
        "prompt": "下面哪种说法更自然？",
        "options": options,
        "answer": strip_furigana(better),
        "explanation": (
            f"{item['id']}　更自然：{better}\n"
            f"不够自然：{worse}\n\n{item.get('why','')}"
        ),
        "source": item["source"],
    }


CONJUGATION_FORMS = {
    "masu": ("ます形", "ます形"),
    "te": ("て形", "て形"),
}

# 五段 て形 endings, used to build the mistakes a learner actually makes.
GODAN_TE = {"う": "って", "つ": "って", "る": "って", "む": "んで", "ぶ": "んで",
            "ぬ": "んで", "く": "いて", "ぐ": "いで", "す": "して"}
GODAN_MASU_STEM = {"う": "い", "つ": "ち", "る": "り", "む": "み", "ぶ": "び",
                   "ぬ": "に", "く": "き", "ぐ": "ぎ", "す": "し"}
# The ない-form stem; using it before ます (遊ばます) is a classic slip.
GODAN_NAI_STEM = {"う": "わ", "つ": "た", "る": "ら", "む": "ま", "ぶ": "ば",
                  "ぬ": "な", "く": "か", "ぐ": "が", "す": "さ"}


def wrong_conjugations(item: dict, key: str) -> list[str]:
    """Plausible *wrong* forms of the same verb — the real conjugation errors.

    A learner who muddles 一段 and 五段 writes 止めります for 止める, or 遊びて for
    遊ぶ. Those make far better distractors than the correct form of an unrelated
    verb, which can be eliminated without knowing any conjugation rule.
    """
    term = item["term"]
    verb_class = (item.get("pos") or "").strip()
    correct = (item.get("forms") or {}).get(key, "")
    if len(term) < 2:
        return []

    body, tail = term[:-1], term[-1]
    out: list[str] = []

    if key == "masu":
        if verb_class.startswith("一段"):
            # Conjugated as if it were 五段: 止める -> 止めります
            out.append(term + "ります" if tail == "る" else term + "ます")
        elif verb_class.startswith("五段"):
            # Conjugated as if it were 一段: 会う -> 会ます
            out.append(body + "ます")
            # ない-stem instead of ます-stem: 歩く -> 歩かます
            if tail in GODAN_NAI_STEM:
                out.append(body + GODAN_NAI_STEM[tail] + "ます")
    else:  # て形
        if verb_class.startswith("一段"):
            out.append(body + "って")          # 食べる -> 食べって
            out.append(term + "て")            # 食べる -> 食べるて
        elif verb_class.startswith("五段"):
            if tail in GODAN_MASU_STEM:
                out.append(body + GODAN_MASU_STEM[tail] + "て")  # 遊ぶ -> 遊びて
            for ending in ("って", "んで", "いて"):
                candidate = body + ending
                if candidate != correct:
                    out.append(candidate)

    seen, unique = set(), []
    for form in out:
        if form and form != correct and form not in seen:
            seen.add(form)
            unique.append(form)
    return unique


def make_conjugation(item: dict, bank: list[dict], rng: random.Random, confusion) -> dict | None:
    """Verb conjugation drill from the V-004 table (guide §8.5)."""
    if item["category"] != "verb_form":
        return None
    forms = item.get("forms") or {}
    choices = [k for k in ("te", "masu") if forms.get(k)]
    if not choices:
        return None
    key = rng.choice(choices)
    label = CONJUGATION_FORMS[key][0]
    answer = forms[key]

    # Half the time ask the learner to produce the form rather than recognise it:
    # writing 遊んで from 遊ぶ is a different (and harder) skill than picking it
    # from a list, and it keeps the daily mix from filling up with MCQs.
    if rng.random() < 0.5:
        return {
            "type": "conjugation",
            "item_id": item["id"],
            "prompt": f"写出「{item['term']}（{item['reading']}）」的{label}：",
            "verb": item["term"],
            "verb_reading": item["reading"],
            "verb_class": item["pos"],
            "form_label": label,
            "meaning_zh": item["meaning_zh"],
            "answer": answer,
            "accepted": [answer, strip_furigana(answer)],
            "explanation": (
                f"{item['id']}　{item['term']}（{item['reading']}）"
                f"［{item['pos']}］{label}：{answer}\n意思：{item['meaning_zh']}"
            ),
            "source": item["source"],
        }

    wrong_options: list[str] = []
    seen = {answer}

    # First choice: wrong conjugations of this very verb, so the question tests
    # the conjugation rule rather than vocabulary recognition.
    for form in wrong_conjugations(item, key):
        if len(wrong_options) >= 3:
            break
        if form not in seen:
            wrong_options.append(form)
            seen.add(form)

    # Top up from other verbs' forms if the rules produced too few.
    others = [
        b for b in bank
        if b["category"] == "verb_form"
        and b["id"] != item["id"]
        and (b.get("forms") or {}).get(key)
        and b["forms"][key] != answer
    ]
    tail = item["term"][-1]
    near = [b for b in others if b["term"].endswith(tail)]
    pool = near if len(near) >= 3 else others
    rng.shuffle(pool)
    for b in pool:
        if len(wrong_options) >= 3:
            break
        candidate = b["forms"][key]
        if candidate not in seen:
            wrong_options.append(candidate)
            seen.add(candidate)

    if len(wrong_options) < 3:
        return None

    options = wrong_options + [answer]
    rng.shuffle(options)

    return {
        "type": "mcq",
        "item_id": item["id"],
        "prompt": f"「{item['term']}（{item['reading']}）」的{label}是？",
        "options": options,
        "answer": answer,
        "explanation": (
            f"{item['id']}　{item['term']}（{item['reading']}）"
            f"［{item['pos']}］{label}：{answer}\n意思：{item['meaning_zh']}"
        ),
        "source": item["source"],
    }


# ---------------------------------------------------------------- assembly


def build_exercise(
    item: dict,
    bank: list[dict],
    preferred: list[str],
    rng: random.Random,
    confusion: dict[str, set[str]],
    avoid: set[str],
) -> dict | None:
    """Build one exercise, trying the requested formats in order.

    `preferred` is a priority list rather than a single choice: many formats are
    impossible for a given item (a particle has no reading to test, a verb-table
    row has no example sentence), and silently falling back to the same default
    every time is what makes a day turn into five multiple-choice questions.
    """
    builders = {
        "correction": lambda: make_correction(item, rng),
        "naturalness": lambda: make_naturalness(item, rng),
        "conjugation": lambda: make_conjugation(item, bank, rng, confusion),
        "mcq_meaning": lambda: make_mcq_meaning(item, bank, rng, confusion),
        "mcq_reading": lambda: make_mcq_reading(item, bank, rng, confusion),
        "fill_blank": lambda: make_fill_blank(item, rng, avoid),
        "translation": lambda: make_translation(item, rng, avoid),
    }
    order = list(preferred) + [k for k in builders if k not in preferred]
    for key in order:
        result = builders[key]()
        if result:
            result["format_key"] = key
            return result
    return None


# Which builders each format key ultimately renders as, for balancing purposes.
FORMAT_DISPLAY = {
    "correction": "correction",
    "naturalness": "mcq",
    "conjugation": "conjugation",
    "mcq_meaning": "mcq",
    "mcq_reading": "mcq",
    "fill_blank": "fill_blank",
    "translation": "translation",
}


def candidate_formats(item: dict) -> list[str]:
    """Formats this item could plausibly support, best first."""
    if item["category"] == "mistake":
        return ["correction" if item.get("severity") == "error" else "naturalness"]
    if item["category"] == "verb_form":
        return ["conjugation", "mcq_reading"]
    return ["fill_blank", "translation", "mcq_meaning", "mcq_reading"]


def order_by_balance(options: list[str], used: dict[str, int], rng: random.Random) -> list[str]:
    """Put the least-used display format first, so a day spreads across formats."""
    shuffled = list(options)
    rng.shuffle(shuffled)
    return sorted(shuffled, key=lambda key: used.get(FORMAT_DISPLAY.get(key, key), 0))


def quality_check(
    exercises: list[dict], count: int, recent_probes: set[str], bank_by_id: dict[str, dict]
) -> tuple[list[str], list[str]]:
    """Guide §13 — refuse to ship a malformed day.

    Returns (errors, warnings). Errors abort the run; warnings are printed but
    tolerated, because some are unavoidable: an item with a single example
    sentence has to reuse it when it comes back for review.
    """
    problems: list[str] = []
    warnings: list[str] = []

    if len(exercises) != count:
        problems.append(f"expected {count} exercises, produced {len(exercises)}")

    for ex in exercises:
        tag = f"#{ex.get('n')} {ex.get('item_id')}"
        if not ex.get("answer"):
            problems.append(f"{tag}: no answer")
        if not ex.get("explanation"):
            problems.append(f"{tag}: no explanation")
        if ex["type"] == "mcq":
            options = ex.get("options") or []
            if len(options) != len(set(options)):
                problems.append(f"{tag}: duplicate options")
            if ex.get("answer") not in options:
                problems.append(f"{tag}: answer missing from options")
            if len(options) < 2:
                problems.append(f"{tag}: fewer than 2 options")
        if ex["type"] == "fill_blank" and "＿＿＿" not in (ex.get("sentence") or ""):
            problems.append(f"{tag}: blank marker missing")

    item_ids = [ex["item_id"] for ex in exercises]
    if len(set(item_ids)) != len(item_ids):
        problems.append("the same item appears twice in one day")
    if len(set(item_ids)) == 1 and len(item_ids) > 1:
        problems.append("all questions test a single knowledge point")

    # Guide §4: the five should span formats rather than all be the same kind.
    kinds = collections.Counter(ex["type"] for ex in exercises)
    if len(exercises) >= 3 and len(kinds) < 2:
        problems.append("every question uses the same format")
    if len(exercises) >= 4 and max(kinds.values()) > len(exercises) - 1:
        warnings.append(f"format mix is thin: {dict(kinds)}")

    # Guide §6: prefer a fresh sentence when an item comes back. The builders
    # already sort unused examples first, so a reuse here means no other example
    # could actually carry the question — worth reporting, not worth failing on.
    reused = [ex["item_id"] for ex in exercises if ex.get("probe") and ex["probe"] in recent_probes]
    if reused:
        warnings.append(f"reused a recent question sentence for: {reused}")

    return problems, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--force", action="store_true", help="regenerate even if the file exists")
    args = parser.parse_args()

    out_path = EXERCISE_DIR / f"{args.date}.json"
    if out_path.exists() and not args.force:
        print(f"{out_path} already exists; use --force to regenerate.")
        return 0

    bank = load_item_bank()
    if not bank:
        print("Item bank is empty — nothing to generate.")
        return 1
    confusion = load_confusion_map()

    # Drop any existing entry for the target date: on a --force regeneration the
    # previous run's own entry would otherwise damp the very items it served,
    # making repeated runs of the same date produce different sets.
    history = [h for h in load_jsonl(HISTORY_PATH) if h.get("date") != args.date]
    mistakes = load_jsonl(MISTAKES_PATH)
    attempts = load_jsonl(ATTEMPTS_PATH)

    mastery = build_mastery(attempts, mistakes)

    # Sentences already used as questions recently, so repeats get a new angle.
    recent_probes: set[str] = set()
    for row in history[-RECENT_WINDOW:]:
        recent_probes.update(row.get("probes", []))

    rng = random.Random(f"{args.date}:{len(bank)}")
    weights = build_weights(bank, history, mastery, args.date)

    # Reserve slots for items not yet mastered. Relying on weighting alone is
    # unreliable once the bank grows: a boosted item is still a small share of
    # the total, so a genuinely weak item could go many days without returning.
    weak = [
        it for it in bank
        if it["id"] in mastery and mastery[it["id"]]["mastery"] < MASTERY_THRESHOLD
    ]
    weak.sort(key=lambda it: (mastery[it["id"]]["mastery"], it["id"]))
    review_picks = weak[: min(REVIEW_SLOTS, args.count, len(weak))]

    remaining = [it for it in bank if it["id"] not in {r["id"] for r in review_picks}]
    fill_picks = weighted_sample(
        remaining, weights, args.count - len(review_picks), rng, already=review_picks
    )

    selected = review_picks + fill_picks
    rng.shuffle(selected)

    exercises = []
    used_formats: dict[str, int] = {}
    for item in selected:
        wanted = order_by_balance(candidate_formats(item), used_formats, rng)
        ex = build_exercise(item, bank, wanted, rng, confusion, recent_probes)
        if ex is None:
            continue
        ex["n"] = len(exercises) + 1
        display = FORMAT_DISPLAY.get(ex.pop("format_key", ""), ex["type"])
        used_formats[display] = used_formats.get(display, 0) + 1
        exercises.append(ex)

    review_ids = [
        e["item_id"] for e in exercises
        if e["item_id"] in mastery and mastery[e["item_id"]]["mastery"] < MASTERY_THRESHOLD
    ]

    problems, warnings = quality_check(
        exercises, args.count, recent_probes, {b["id"]: b for b in bank}
    )
    if problems:
        print("Quality check failed:")
        for p in problems:
            print(f"  - {p}")
        return 1
    for w in warnings:
        print(f"  note: {w}")

    payload = {
        "date": args.date,
        "generated_from": "handbook/ (grammar, particles, expressions, vocabulary, verbs, mistakes, Duolingo)",
        "count": len(exercises),
        "review_item_ids": review_ids,
        "exercises": exercises,
    }

    EXERCISE_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    history.append(
        {
            "date": args.date,
            "item_ids": [e["item_id"] for e in exercises],
            "probes": [e["probe"] for e in exercises if e.get("probe")],
        }
    )
    history.sort(key=lambda h: h.get("date", ""))
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        "".join(json.dumps(h, ensure_ascii=False) + "\n" for h in history), encoding="utf-8"
    )

    MASTERY_PATH.write_text(
        json.dumps(
            {"updated_at": args.date, "items": sorted(mastery.values(), key=lambda s: s["item_id"])},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    dates = sorted((p.stem for p in EXERCISE_DIR.glob("*.json")), reverse=True)
    INDEX_PATH.write_text(
        json.dumps({"latest": dates[0] if dates else None, "dates": dates}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {out_path} ({len(exercises)} exercises)")
    for e in exercises:
        marker = " [复习]" if e["item_id"] in review_ids else ""
        print(f"  {e['n']}. [{e['type']}] {e['item_id']}{marker}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
