#!/usr/bin/env python3
"""Generate the daily set of 5 Japanese exercises.

Reads the handbook item bank, weights items by past mistakes and recent
exposure, and writes a dated exercise file the web app can load.

Outputs:
  docs/data/exercises/YYYY-MM-DD.json   today's 5 exercises
  docs/data/index.json                  list of available dates (newest first)
  docs/data/history.jsonl               one line per generated day (items served)

Usage:
  python3 exercise-generator/generate_exercises.py [--date YYYY-MM-DD] [--count 5] [--force]
"""
from __future__ import annotations

import argparse
import json
import random
import re
from datetime import date
from pathlib import Path

from itembank import load_item_bank

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "data"
EXERCISE_DIR = DATA_DIR / "exercises"
HISTORY_PATH = DATA_DIR / "history.jsonl"
MISTAKES_PATH = DATA_DIR / "mistakes.jsonl"
ATTEMPTS_PATH = DATA_DIR / "attempts.jsonl"
INDEX_PATH = DATA_DIR / "index.json"

FURIGANA_RE = re.compile(r"（[ぁ-んァ-ヶー]+）")

# Weighting knobs.
BASE_WEIGHT = 1.0
MISTAKE_BONUS = 4.0        # per outstanding miss on that item
MISTAKE_CAP = 5            # ignore misses beyond this many, keeps one item from dominating
RECENT_PENALTY = 0.12      # damping for items served recently and answered correctly
WEAK_RECENT_PENALTY = 0.8  # much milder damping for items still being got wrong
RECENT_WINDOW = 10
REVIEW_SLOTS = 2           # reserved slots per day for items still being got wrong


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


def outstanding_misses(mistakes: list[dict], attempts: list[dict]) -> dict[str, int]:
    """Misses that haven't been cancelled out by later correct answers.

    An item you keep getting wrong stays high priority; once you answer it
    correctly as many times as you missed it, it drops back to the normal pool.
    """
    misses: dict[str, int] = {}
    for row in mistakes:
        item_id = row.get("item_id")
        if item_id:
            misses[item_id] = misses.get(item_id, 0) + 1

    corrects: dict[str, int] = {}
    for row in attempts:
        item_id = row.get("item_id")
        if item_id and row.get("correct"):
            corrects[item_id] = corrects.get(item_id, 0) + 1

    return {
        item_id: max(0, count - corrects.get(item_id, 0))
        for item_id, count in misses.items()
    }


def build_weights(
    bank: list[dict], history: list[dict], mistakes: list[dict], attempts: list[dict]
) -> dict[str, float]:
    net_misses = outstanding_misses(mistakes, attempts)

    recent_ids: set[str] = set()
    for row in history[-RECENT_WINDOW:]:
        recent_ids.update(row.get("item_ids", []))

    weights = {}
    for item in bank:
        outstanding = min(net_misses.get(item["id"], 0), MISTAKE_CAP)
        weight = BASE_WEIGHT + MISTAKE_BONUS * outstanding
        if item["id"] in recent_ids:
            # Recently served items are damped so the set stays varied, but an item
            # you are still getting wrong must be allowed to come back quickly.
            weight *= WEAK_RECENT_PENALTY if outstanding else RECENT_PENALTY
        weights[item["id"]] = weight
    return weights


def weighted_sample(bank: list[dict], weights: dict[str, float], count: int, rng: random.Random) -> list[dict]:
    pool = list(bank)
    chosen = []
    for _ in range(min(count, len(pool))):
        total = sum(weights[i["id"]] for i in pool)
        target = rng.uniform(0, total)
        upto = 0.0
        for item in pool:
            upto += weights[item["id"]]
            if upto >= target:
                chosen.append(item)
                pool.remove(item)
                break
    return chosen


def _distractors(item: dict, bank: list[dict], field: str, rng: random.Random, n: int = 3) -> list[str]:
    """Pick n plausible wrong answers from same-category (ideally same-pos) items."""
    same_pos = [
        b for b in bank
        if b["id"] != item["id"]
        and b["category"] == item["category"]
        and b.get(field)
        and b[field] != item.get(field)
        and (item.get("pos") is None or b.get("pos") == item.get("pos"))
    ]
    same_cat = [
        b for b in bank
        if b["id"] != item["id"]
        and b["category"] == item["category"]
        and b.get(field)
        and b[field] != item.get(field)
    ]
    pool = same_pos if len(same_pos) >= n else same_cat
    if len(pool) < n:
        pool = [b for b in bank if b["id"] != item["id"] and b.get(field) and b[field] != item.get(field)]

    picks = rng.sample(pool, min(n, len(pool)))
    seen, out = set(), []
    for p in picks:
        if p[field] not in seen:
            seen.add(p[field])
            out.append(p[field])
    return out


def make_mcq_meaning(item: dict, bank: list[dict], rng: random.Random) -> dict | None:
    """MCQ: given the Japanese word/pattern, choose the Chinese meaning."""
    if not item.get("meaning_zh"):
        return None
    wrong = _distractors(item, bank, "meaning_zh", rng)
    if len(wrong) < 3:
        return None
    options = wrong + [item["meaning_zh"]]
    rng.shuffle(options)

    label = item["term"]
    if item.get("reading"):
        label = f"{item['term']}（{item['reading']}）"

    return {
        "type": "mcq",
        "item_id": item["id"],
        "prompt": f"「{label}」的意思是？",
        "options": options,
        "answer": item["meaning_zh"],
        "explanation": f"{item['id']}　{label}：{item['meaning_zh']}",
        "source": item["source"],
    }


def make_mcq_reading(item: dict, bank: list[dict], rng: random.Random) -> dict | None:
    """MCQ: given the kanji word, choose the correct kana reading."""
    reading = item.get("reading")
    if not reading or item["category"] != "vocab":
        return None
    # Only interesting when the term actually contains kanji.
    if not re.search(r"[一-鿿]", item["term"]):
        return None
    wrong = _distractors(item, bank, "reading", rng)
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
    """Strings that might literally appear in an example sentence for this item.

    Grammar and expression entries are written as patterns (～たら, ～ものだ／～ものです,
    普通形＋と思う), so the literal headword is rarely in the sentence verbatim.
    """
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


def make_fill_blank(item: dict, rng: random.Random) -> dict | None:
    """Fill in the blank: remove the target word from one of its example sentences."""
    term = item["term"]
    candidates = stem_candidates(item)

    # Try every example, not just one: a pattern like ～ために appears verbatim in
    # some sentences and only in conjugated form in others. Matching is done on the
    # furigana-stripped text, since 乗り換える appears as 乗（の）り換（か）えます.
    examples = list(item["examples"])
    rng.shuffle(examples)

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

    answer_display = term
    if item.get("reading"):
        answer_display = f"{term}（{item['reading']}）"

    return {
        "type": "fill_blank",
        "item_id": item["id"],
        "prompt": "在空格处填入合适的词（可写汉字或假名）：",
        "sentence": blanked_plain,
        "sentence_zh": example["zh"],
        "answer": stem,
        "accepted": sorted({s for s in (stem, term, item.get("reading"), strip_furigana(term)) if s}),
        "explanation": f"{item['id']}　完整句子：{sentence}\n{example['zh']}\n{answer_display}：{item['meaning_zh']}",
        "source": item["source"],
    }


def make_translation(item: dict, rng: random.Random) -> dict:
    """One-sentence translation from Chinese to Japanese."""
    example = rng.choice(item["examples"])
    hint = item["term"]
    if item.get("reading"):
        hint = f"{item['term']}（{item['reading']}）"

    return {
        "type": "translation",
        "item_id": item["id"],
        "prompt": "把下面的中文翻译成日语：",
        "sentence_zh": example["zh"],
        "hint": f"提示：使用 {hint}",
        "answer": example["ja"],
        "answer_plain": strip_furigana(example["ja"]),
        "explanation": f"{item['id']}　参考答案：{example['ja']}\n{item['term']}：{item['meaning_zh']}",
        "source": item["source"],
    }


def build_exercise(item: dict, bank: list[dict], preferred: str, rng: random.Random) -> dict:
    """Build one exercise, preferring the requested format but falling back if unusable."""
    builders = {
        "mcq_meaning": lambda: make_mcq_meaning(item, bank, rng),
        "mcq_reading": lambda: make_mcq_reading(item, bank, rng),
        "fill_blank": lambda: make_fill_blank(item, rng),
        "translation": lambda: make_translation(item, rng),
    }
    order = [preferred] + [k for k in builders if k != preferred]
    for key in order:
        result = builders[key]()
        if result:
            return result
    return make_translation(item, rng)


def plan_formats(count: int, rng: random.Random) -> list[str]:
    """A mix: always at least one of each main format when count >= 3."""
    formats = ["mcq_meaning", "fill_blank", "translation"]
    plan = formats[:min(count, 3)]
    extras = ["mcq_reading", "mcq_meaning", "fill_blank", "translation"]
    while len(plan) < count:
        plan.append(rng.choice(extras))
    rng.shuffle(plan)
    return plan


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

    history = load_jsonl(HISTORY_PATH)
    mistakes = load_jsonl(MISTAKES_PATH)
    attempts = load_jsonl(ATTEMPTS_PATH)

    # Deterministic per-date: same day always yields the same set.
    rng = random.Random(f"{args.date}:{len(bank)}")

    weights = build_weights(bank, history, mistakes, attempts)
    net_misses = outstanding_misses(mistakes, attempts)

    # Reserve slots for items still being got wrong. Relying on weighting alone is
    # unreliable once the bank grows: a boosted item is still a small share of the
    # total, so a genuinely weak item could go many days without coming back.
    review_pool = [it for it in bank if net_misses.get(it["id"], 0) > 0]
    review_pool.sort(key=lambda it: (-net_misses[it["id"]], it["id"]))
    review_picks = review_pool[: min(REVIEW_SLOTS, args.count, len(review_pool))]

    remaining_bank = [it for it in bank if it["id"] not in {r["id"] for r in review_picks}]
    fill_picks = weighted_sample(remaining_bank, weights, args.count - len(review_picks), rng)

    selected = review_picks + fill_picks
    rng.shuffle(selected)
    formats = plan_formats(len(selected), rng)

    exercises = []
    for i, (item, fmt) in enumerate(zip(selected, formats), start=1):
        ex = build_exercise(item, bank, fmt, rng)
        ex["n"] = i
        exercises.append(ex)

    review_ids = [e["item_id"] for e in exercises if net_misses.get(e["item_id"])]

    payload = {
        "date": args.date,
        "generated_from": "handbook/ + Duolingo Sections 1-4",
        "count": len(exercises),
        "review_item_ids": review_ids,
        "exercises": exercises,
    }

    EXERCISE_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # history: record what was served so tomorrow avoids immediate repeats
    history = [h for h in history if h.get("date") != args.date]
    history.append({"date": args.date, "item_ids": [e["item_id"] for e in exercises]})
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        "".join(json.dumps(h, ensure_ascii=False) + "\n" for h in history), encoding="utf-8"
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
