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


MARKUP_RE = re.compile(r"^[|\-:\s]*$|^\|")


def make_mcq_meaning(item: dict, bank: list[dict], rng: random.Random, confusion) -> dict | None:
    """MCQ: given the Japanese word/pattern, choose the Chinese meaning."""
    meaning = (item.get("meaning_zh") or "").strip()
    # Never offer leftover markdown as a definition: a comparison entry opening
    # with a table once had "| 表达 | 用法 |" served to the learner as its meaning.
    if not meaning or MARKUP_RE.match(meaning) or item["category"] in ("mistake", "verb_form"):
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


# Characters the blank must never swallow: particles carry the sentence
# structure the learner needs in order to work out what goes in the gap, and
# punctuation marks its edges.
BLANK_STOP = set("はがをにへでともやのかねよ、。「」！？")
# Where a blank may legitimately begin. や in やすい and ね in ねこ are ordinary
# word-internal kana, so stopping there means the scan cut a word in half;
# お／ご are honorific prefixes and make a clean edge in front of お手伝いします.
BLANK_LEFT_EDGE = set("はがをにへでとものかおご、。「」！？")
KANA_RE = re.compile(r"[ぁ-ん]")
KANA_ANY_RE = re.compile(r"[ぁ-んァ-ヶ]")
KANJI_RE = re.compile(r"[一-鿿々]")
KATAKANA_RE = re.compile(r"[ァ-ヴー]")

# What may follow a stem and still belong to the same word. A blind run of kana
# swallowed the head of whatever came next (ように＋ま of まとめます), so the blank
# only grows over an actual inflection. Longer endings come first: た must not
# win where たら is meant.
_MASU = r"ませんでした|ましょうか|ませんか|ましょう|ました|ません|ます"
_ENDINGS = (
    rf"{_MASU}|"
    r"なかった|ないで|ない|たかった|たくない|たい|"
    r"てください|ています|ておきます|ている|ておく|てある|てしまう|ても|て|"
    # Voiced で／だ belong to the て形 and た形 of 読む・泳ぐ・遊ぶ, where the ん or
    # い sits directly on the kanji stem. The same two kana after kana are the
    # copula instead — 休みでした, 挑戦したいです, 詳しいんですか — and stay out.
    # An い-adjective has the verb's shape (悪い vs 泳い), so で is also refused
    # in front of す, where it is the です of 天気が悪いです.
    r"(?<=[一-鿿々ァ-ヴー][んい])(?:で(?!す)|だ)|"
    r"いました|います|いる|いた|ください|おく|"
    r"られませんでした|られましょう|られません|られました|られます|られない|られる|"
    r"れませんでした|れません|れました|れます|れない|れる|"
    r"させる|せる|たら|たり|た|ながら|やすい|にくい|すぎる|ようか|よう|ば"
)
# 治 and 焼 are stems without their ます-row kana, so the ending is reached across
# one of those: 治＋り＋ました, 焼＋い＋て. That kana may also stand alone, as in
# 買い に行きます, where nothing more attaches to it. に is the exception: it is a
# particle far more often than the ます-stem of 死ぬ, so it bridges only to ます
# itself — 上司に説明します must keep its に outside the blank.
INFLECTION_TAIL = re.compile(
    rf"[っん]?(?:{_ENDINGS})|に(?:{_MASU})|[いきぎしちびみり](?:{_ENDINGS})?"
)


def _absorb_word_body(plain: str, start: int, span_head: str) -> int:
    """Extend a blank leftwards over the kanji/katakana body of the same word.

    Stopping at the first kanji leaves the learner the front of the word — the
    complaint that 毎日練習し＿＿＿ tests only ～たら applies just as much to
    毎日練習＿＿＿. What is safe to swallow depends on the shape of the word:

      サ变 verbs (the span starts with し) carry a noun body of at most two
      kanji, or a whole katakana word: 練習したら, コピーしたら.
      Everything else is a single-stem verb, so its kanji run is absorbed only
      when the run itself is short — 終わったら, お手伝いしましょうか. A long run
      such as 図書館行ったら spans two words and is left alone.
    """
    if start == 0 or KATAKANA_RE.match(plain[start - 1]):
        run = start
        while run > 0 and KATAKANA_RE.match(plain[run - 1]):
            run -= 1
        return run if span_head == "し" and run < start else start

    body = start
    while body > 0 and KANJI_RE.match(plain[body - 1]):
        body -= 1
    length = start - body
    if length == 0:
        return start
    if span_head == "し":
        return max(body, start - 2)
    return body if length <= 2 else start


def expand_blank(plain: str, stem: str, attaches_left: bool = False) -> str:
    """Grow a blank over the whole inflected word, not just the pattern.

    ～たら sits after 練習し, and 忘れ sits before ました; in both cases the part
    left showing is the conjugation itself, which is most of the point. The span
    grows across adjacent hiragana, then over the word body the inflection hangs
    off, stopping at a particle so the sentence structure stays intact.

    `attaches_left` marks a grammar pattern, the only kind of item that hangs off
    what precedes it. A noun keeps its own boundary however it is written: お城
    begins with kana too, and growing leftwards there swallowed the whole
    relative clause in 二人が行ったお城.
    """
    start = plain.find(stem)
    if start < 0:
        return stem
    end = start + len(stem)

    # Only a pattern that itself begins with kana (～たら, ～ので) attaches to an
    # inflection on its left. When the stem starts with a kanji the kana before
    # it belong to the previous word — expanding there turned もう治りました into
    # a nonsense "う治りました".
    if attaches_left and KANA_RE.match(stem[0]):
        scan = start
        while scan > 0:
            ch = plain[scan - 1]
            if ch in BLANK_STOP or not KANA_RE.match(ch):
                break
            scan -= 1
        # Stopping on a kana that is not a real edge means the scan ran into the
        # middle of the preceding word (分かりや|すいように), so nothing is taken.
        if scan == 0 or not KANA_RE.match(plain[scan - 1]) or plain[scan - 1] in BLANK_LEFT_EDGE:
            start = _absorb_word_body(plain, scan, plain[scan])

    while True:
        match = INFLECTION_TAIL.match(plain, end)
        if not match or match.end() == end:
            break
        tail, end = plain[end:match.end()], match.end()
        # Only a て形 takes a further ending (読んで＋います). Anything else is
        # already the end of the word, and carrying on swallows the next one.
        if not tail.endswith(("て", "で")):
            break

    span = plain[start:end]
    # An expanded blank must still be unambiguous within the sentence, and it has
    # to leave something behind: blanking 心配しないでください whole turns the
    # question into "＿＿＿。" with nothing to work from.
    if plain.count(span) != 1 or not plain.replace(span, "", 1).strip("、。！？「」 　"):
        return stem
    return span


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
    # Blank the whole inflected word, not just the pattern. Leaving 練習し in
    # front of a ～たら blank tests only the two trailing kana; swallowing the
    # inflection makes the learner produce 練習したら from scratch.
    blank_text = expand_blank(
        plain, stem, attaches_left=item["category"] in ("grammar", "expression")
    )
    blanked_plain = plain.replace(blank_text, "＿＿＿", 1)

    return {
        "type": "fill_blank",
        "item_id": item["id"],
        "prompt": "在空格处填入合适的词（可写汉字或假名）：",
        "sentence": blanked_plain,
        "sentence_zh": example["zh"],
        "answer": blank_text,
        # When the blank was widened to cover the inflection, only the full form
        # counts — accepting a bare たら would give back exactly the shortcut the
        # wider blank exists to remove.
        "accepted": (
            [blank_text]
            if blank_text != stem
            else sorted({s for s in (stem, term, item.get("reading"), strip_furigana(term)) if s})
        ),
        # A wider blank needs a prompt for what belongs there, or it is guesswork
        # rather than a harder question. Plain vocabulary gaps already have the
        # answer in their translation, so they get no redundant hint.
        "hint": (
            f"提示：{item['meaning_zh']}"
            if item.get("meaning_zh")
            and (blank_text != stem or item["category"] in ("grammar", "expression"))
            else ""
        ),
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


def personal_errors(mistakes: list[dict]) -> dict[str, dict]:
    """The learner's own wrong sentences, newest first, keyed by item.

    Guide §5 priority 1 and §8.3: an error you actually made is the most
    valuable thing to re-test. Near misses are excluded — the grader flags those
    when an answer was close to the reference, and a close answer is often
    perfectly good Japanese. Replaying one as "this is wrong, fix it" would
    teach a mistake rather than correct one.
    """
    latest: dict[str, dict] = {}
    for row in sorted(mistakes, key=lambda r: r.get("date", "")):
        given = (row.get("given") or "").strip()
        expected = (row.get("expected") or "").strip()
        if not given or not expected or row.get("near"):
            continue
        if strip_furigana(given) == strip_furigana(expected):
            continue
        latest[row["item_id"]] = {
            "given": given,
            "expected": expected,
            "date": row.get("date", ""),
        }
    return latest


def make_personal_correction(item: dict, personal: dict[str, dict]) -> dict | None:
    """Hand back a sentence the learner actually wrote, to be corrected."""
    record = personal.get(item["id"])
    if not record:
        return None

    reference = record["expected"]
    # Only the sentence actually being corrected counts. The item's other example
    # sentences use the same grammar point but mean something else entirely, so
    # accepting them would mark an unrelated answer correct.
    accepted = {strip_furigana(reference), reference}

    return {
        "type": "correction",
        "item_id": item["id"],
        "prompt": f"这是你在 {record['date']} 写过的答案，请改成正确的说法：",
        "wrong_sentence": strip_furigana(record["given"]),
        "sentence_zh": (item["examples"][0]["zh"] if item.get("examples") else item.get("meaning_zh", "")),
        "answer": reference,
        "answer_plain": strip_furigana(reference),
        "accepted": sorted(a for a in accepted if a),
        "explanation": (
            f"{item['id']}　你写的：{record['given']}\n"
            f"参考答案：{reference}\n"
            f"{_label(item)}：{item['meaning_zh']}"
        ),
        "source": item["source"],
        "personal": True,
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
    "dictionary": ("辞书形", "辞书形"),
    "masu": ("ます形", "ます形"),
    "te": ("て形", "て形"),
    "ta": ("た形", "た形"),
    "nai": ("ない形", "ない形"),
    "potential": ("可能形", "可能形"),
}

# ます形 is the first form learned and quickly becomes automatic, so it is asked
# only when nothing harder can be derived for that verb.
FORM_PRIORITY = ["potential", "nai", "ta", "te", "masu"]

# Verbs whose ない形 or 可能形 do not follow the class rule. An empty string means
# the form is not worth asking: ある has no ordinary 可能形 (有り得る is a separate
# word, not a conjugation), so the drill skips it instead of teaching a wrong rule.
IRREGULAR_FORMS = {
    "ある": {"nai": "ない", "potential": ""},
    "する": {"nai": "しない", "potential": "できる"},
    "来る": {"nai": "来ない", "potential": "来られる"},
    "いる": {"nai": "いない", "potential": "いられる"},
}


def kana_form(item: dict, answer: str) -> str:
    """The same conjugated form written entirely in kana.

    Typing 話せる on a phone means finding the kanji; はなせる is the same answer
    and tests the same rule, so it is accepted too. The kanji stem maps onto the
    head of the reading — 話す／はなす gives 話→はな — which fails only for 来る,
    whose reading changes with the form (くる／こられる), so カ变 is left out.
    """
    reading, term = item.get("reading", ""), item["term"]
    pos = (item.get("pos") or "").strip()
    if not reading or reading == term or pos.startswith("カ变"):
        return ""
    kanji_len = 0
    while kanji_len < len(term) and KANJI_RE.match(term[kanji_len]):
        kanji_len += 1
    okurigana = len(term) - kanji_len
    if not kanji_len or okurigana >= len(reading) or not answer.startswith(term[:kanji_len]):
        return ""
    return reading[: len(reading) - okurigana] + answer[kanji_len:]


def derive_form(item: dict, key: str) -> str:
    """Build た形／ない形／可能形 from the dictionary form and the verb class.

    Only ます形 and て形 are tabulated in V-004. The rest follow from the class
    (V-005 – V-007), and た形 in particular is just て形 with its final kana
    voiced-swapped, so it needs no separate rule.
    """
    forms = item.get("forms") or {}
    if key in forms and forms[key]:
        return forms[key]

    term = forms.get("dictionary") or item["term"]
    verb_class = (item.get("pos") or "").strip()
    te = forms.get("te", "")

    override = IRREGULAR_FORMS.get(term, {})
    if key in override:
        return override[key]

    if key == "ta":
        # 遊んで → 遊んだ, 会って → 会った, 行って → 行った (the 行く exception is
        # already baked into its tabulated て形).
        if not te:
            return ""
        return te[:-1] + ("だ" if te.endswith("で") else "た")

    if verb_class.startswith("サ变"):
        stem = term[:-2] if term.endswith("する") else term
        return {"nai": stem + "しない", "potential": stem + "できる"}.get(key, "")

    if verb_class.startswith("カ变"):
        return {"nai": "来ない", "potential": "来られる"}.get(key, "")

    if verb_class.startswith("一段"):
        stem = term[:-1]
        return {"nai": stem + "ない", "potential": stem + "られる"}.get(key, "")

    if verb_class.startswith("五段"):
        body, tail = term[:-1], term[-1]
        if key == "nai" and tail in GODAN_NAI_STEM:
            return body + GODAN_NAI_STEM[tail] + "ない"
        if key == "potential" and tail in GODAN_POTENTIAL_STEM:
            return body + GODAN_POTENTIAL_STEM[tail] + "る"
    return ""

# 五段 て形 endings, used to build the mistakes a learner actually makes.
GODAN_TE = {"う": "って", "つ": "って", "る": "って", "む": "んで", "ぶ": "んで",
            "ぬ": "んで", "く": "いて", "ぐ": "いで", "す": "して"}
GODAN_MASU_STEM = {"う": "い", "つ": "ち", "る": "り", "む": "み", "ぶ": "び",
                   "ぬ": "に", "く": "き", "ぐ": "ぎ", "す": "し"}
# The ない-form stem; using it before ます (遊ばます) is a classic slip.
GODAN_NAI_STEM = {"う": "わ", "つ": "た", "る": "ら", "む": "ま", "ぶ": "ば",
                  "ぬ": "な", "く": "か", "ぐ": "が", "す": "さ"}
# The え-row stem the 可能形 is built on: 話す → 話せる, 飲む → 飲める.
GODAN_POTENTIAL_STEM = {"う": "え", "つ": "て", "る": "れ", "む": "め", "ぶ": "べ",
                        "ぬ": "ね", "く": "け", "ぐ": "げ", "す": "せ"}


def wrong_conjugations(item: dict, key: str) -> list[str]:
    """Plausible *wrong* forms of the same verb — the real conjugation errors.

    A learner who muddles 一段 and 五段 writes 止めります for 止める, or 遊びて for
    遊ぶ. Those make far better distractors than the correct form of an unrelated
    verb, which can be eliminated without knowing any conjugation rule.
    """
    term = (item.get("forms") or {}).get("dictionary") or item["term"]
    verb_class = (item.get("pos") or "").strip()
    correct = derive_form(item, key)
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
    elif key in ("te", "ta"):
        if verb_class.startswith("一段"):
            out.append(body + "って")          # 食べる -> 食べって
            out.append(term + "て")            # 食べる -> 食べるて
        elif verb_class.startswith("五段"):
            if tail in GODAN_MASU_STEM:
                out.append(body + GODAN_MASU_STEM[tail] + "て")  # 遊ぶ -> 遊びて
            for ending in ("って", "んで", "いて"):
                out.append(body + ending)
        elif verb_class.startswith("サ变"):
            stem = term[:-2] if term.endswith("する") else term
            out.append(term + "て")                        # 勉強するて
            out.append(stem + "すて")                      # 勉強すて
        elif verb_class.startswith("カ变"):
            out.extend(["来るて", "来って", "来きて"])
        if key == "ta":
            # た形 errors are て形 errors with the same voicing swap, so the wrong
            # 遊びて becomes the wrong 遊びた rather than a separate rule set.
            out = [f[:-1] + ("だ" if f.endswith("で") else "た") for f in out]
    elif key == "nai":
        if verb_class.startswith("一段"):
            out.append(term + "ない")                      # 食べる -> 食べるない
            out.append(body + "らない")                    # as 五段: 食べらない
        elif verb_class.startswith("五段"):
            out.append(body + "ない")                      # as 一段: 飲ない
            if tail in GODAN_MASU_STEM:
                # ます-stem instead of ない-stem: 飲む -> 飲みない
                out.append(body + GODAN_MASU_STEM[tail] + "ない")
            for stem in ("ら", "わ", "か"):
                out.append(body + stem + "ない")           # wrong row of the same class
        elif verb_class.startswith("サ变"):
            stem = term[:-2] if term.endswith("する") else term
            out.append(stem + "するない")
            out.append(stem + "さない")
        elif verb_class.startswith("カ变"):
            out.extend(["来るない", "来らない", "来れない"])
    elif key == "potential":
        if verb_class.startswith("一段"):
            out.append(body + "れる")                      # ら抜き: 食べれる
            out.append(term + "られる")                    # 食べるられる
            out.append(body + "える")                      # as 五段: 食べえる
        elif verb_class.startswith("五段"):
            out.append(body + "られる")                    # as 一段: 飲られる
            if tail in GODAN_NAI_STEM:
                # ない-stem + れる, i.e. the passive shape: 飲む -> 飲まれる
                out.append(body + GODAN_NAI_STEM[tail] + "れる")
            if tail in GODAN_MASU_STEM:
                out.append(body + GODAN_MASU_STEM[tail] + "れる")
            out.append(term + "られる")
        elif verb_class.startswith("サ变"):
            stem = term[:-2] if term.endswith("する") else term
            out.extend([stem + "しられる", stem + "される", stem + "するできる"])
        elif verb_class.startswith("カ变"):
            out.extend(["来れる", "来できる", "来るられる"])

    seen, unique = set(), []
    for form in out:
        if form and form != correct and form not in seen:
            seen.add(form)
            unique.append(form)
    return unique


def verb_surfaces(item: dict) -> list[tuple[str, bool]]:
    """Written shapes of a verb to look for in a sentence.

    Returns (surface, needs_masu) — the bare ます-stem (入り) is only a verb when
    ます follows it, otherwise it matches nouns like 入り口.
    """
    forms = {k: derive_form(item, k) for k in DRILL_FORMS}
    out = [(v, False) for v in forms.values() if v and len(v) >= 2]
    stem = forms.get("masu", "")[:-2]
    if len(stem) >= 2:
        out.append((stem, True))
    seen, unique = set(), []
    for surface, needs in sorted(out, key=lambda s: -len(s[0])):
        if surface not in seen:
            seen.add(surface)
            unique.append((surface, needs))
    return unique


def verb_usage_index(bank: list[dict]) -> dict[str, list[dict]]:
    """Sentences elsewhere in the handbook that actually use each V-004 verb.

    The verb table has no example sentences of its own, which is why those items
    could only ever be asked as bare form conversion. Borrowing a real sentence
    lets the same verb be asked the harder way — work out which form the
    sentence needs — without inventing Japanese.
    """
    pool = [
        {"ja": ex["ja"], "zh": ex["zh"], "plain": strip_furigana(ex["ja"]), "owner": b["id"]}
        for b in bank if b["category"] != "verb_form"
        for ex in b["examples"]
        # A translation with kana in it is not a translation: dialogue examples
        # (A：… / B：…) split into two Japanese lines and the second was being
        # served as the Chinese prompt.
        if ex["zh"] and not KANA_ANY_RE.search(ex["zh"])
    ]
    index: dict[str, list[dict]] = {}
    for item in bank:
        if item["category"] != "verb_form":
            continue
        found = []
        for sentence in pool:
            for surface, needs_masu in verb_surfaces(item):
                at = sentence["plain"].find(surface)
                if at < 0 or sentence["plain"].count(surface) != 1:
                    continue
                if needs_masu and not sentence["plain"][at + len(surface):].startswith("ま"):
                    continue
                found.append({**sentence, "surface": surface})
                break
        if found:
            index[item["id"]] = found
    return index


def _pick_usage(item, usage, rng, avoid):
    sentences = list(usage.get(item["id"], []))
    if not sentences:
        return None
    rng.shuffle(sentences)
    sentences.sort(key=lambda s: s["ja"] in (avoid or set()))
    return sentences[0]


def make_verb_form_choice(
    item: dict, usage: dict, rng: random.Random, avoid: set[str] | None = None
) -> dict | None:
    """Give the dictionary form, ask which form the sentence needs.

    Harder than the drill block: nothing states the target form, so the sentence
    itself has to be read before anything can be written.
    """
    if item["category"] != "verb_form":
        return None
    sentence = _pick_usage(item, usage, rng, avoid)
    if not sentence:
        return None
    blank = expand_blank(sentence["plain"], sentence["surface"])
    if sentence["plain"].count(blank) != 1 or blank == sentence["plain"]:
        return None
    return {
        "type": "fill_blank",
        "item_id": item["id"],
        # The verb itself is never named: printing 「曲がる」 above the blank turns
        # the question into pure conjugation, which is what the drill block is
        # for. The Chinese sentence plus the meaning is enough to identify it.
        "prompt": "在空格处填入合适的动词形式：",
        "sentence": sentence["plain"].replace(blank, "＿＿＿", 1),
        "sentence_zh": sentence["zh"],
        "hint": f"提示：{item['meaning_zh']}｜{item['pos']}",
        "answer": blank,
        "accepted": sorted({s for s in (blank, kana_form(item, blank)) if s}),
        "explanation": (
            f"{item['id']}　完整句子：{sentence['ja']}\n{sentence['zh']}\n"
            f"{item['term']}（{item['reading']}）［{item['pos']}］：{item['meaning_zh']}"
        ),
        "source": item["source"],
        "probe": sentence["ja"],
    }


def make_verb_translation(
    item: dict, usage: dict, rng: random.Random, avoid: set[str] | None = None
) -> dict | None:
    """Whole-sentence translation built around a verb from the V-004 table."""
    if item["category"] != "verb_form":
        return None
    sentence = _pick_usage(item, usage, rng, avoid)
    if not sentence:
        return None
    return {
        "type": "translation",
        "item_id": item["id"],
        "prompt": "把下面的中文翻译成日语：",
        "sentence_zh": sentence["zh"],
        # No hint at all. Naming the verb would hand over the answer, and naming
        # its Chinese meaning misleads whenever the verb sits inside a pattern —
        # なる in ようになりました is not the learner's "become". Translating the
        # whole sentence correctly already proves the verb was known.
        "hint": "",
        "answer": sentence["ja"],
        "answer_plain": sentence["plain"],
        "accepted": [sentence["plain"]],
        "explanation": (
            f"{item['id']}　参考答案：{sentence['ja']}\n"
            f"{item['term']}（{item['reading']}）［{item['pos']}］：{item['meaning_zh']}"
        ),
        "source": item["source"],
        "probe": sentence["ja"],
    }


# Which form the drill shows. The dictionary form is the usual starting point,
# but converting out of ます形 or て形 is a different (and harder) lookup, so both
# appear regularly.
DRILL_SOURCES = [("dictionary", 5), ("masu", 3), ("te", 2)]
DRILL_COOLDOWN = 2         # days a drilled verb sits out of the weak-slot queue
DRILL_FORMS = ["dictionary", "masu", "te", "ta", "nai", "potential"]


def make_conjugation_drill(item: dict, rng: random.Random) -> dict | None:
    """Pure form-conversion drill: given one form of a verb, write another.

    No sentence and no context — this is the flash-card half of the practice,
    meant to be answered quickly and in volume, so the daily five can stay on
    meaning and usage.
    """
    if item["category"] != "verb_form":
        return None
    forms = {k: derive_form(item, k) for k in DRILL_FORMS}
    forms = {k: v for k, v in forms.items() if v}
    if len(forms) < 2:
        return None

    pairs = [(k, w) for k, w in DRILL_SOURCES if k in forms]
    if not pairs:
        return None
    source = rng.choices([k for k, _ in pairs], [w for _, w in pairs])[0]
    # A target that happens to be spelled like the source teaches nothing.
    targets = [k for k, v in forms.items() if k != source and v != forms[source]]
    if not targets:
        return None
    # ます形 is the first form learned; ask for it only when nothing else exists.
    harder = [k for k in targets if k != "masu"]
    target = rng.choice(harder or targets)

    answer = forms[target]
    table = "｜".join(
        f"{CONJUGATION_FORMS[k][0]}：{forms[k]}" for k in DRILL_FORMS if k in forms
    )
    return {
        "type": "conjugation",
        "item_id": item["id"],
        "prompt": f"「{forms[source]}」（{CONJUGATION_FORMS[source][0]}）→ 写出{CONJUGATION_FORMS[target][0]}：",
        "verb": item["term"],
        "verb_reading": item["reading"],
        "verb_class": item["pos"],
        "source_label": CONJUGATION_FORMS[source][0],
        "source_form": forms[source],
        "form_label": CONJUGATION_FORMS[target][0],
        "meaning_zh": item["meaning_zh"],
        "answer": answer,
        "accepted": sorted(
            {s for s in (answer, strip_furigana(answer), kana_form(item, answer)) if s}
        ),
        "explanation": (
            f"{item['id']}　{item['term']}（{item['reading']}）［{item['pos']}］\n"
            f"{table}\n意思：{item['meaning_zh']}"
        ),
        "source": item["source"],
    }


def make_conjugation(item: dict, bank: list[dict], rng: random.Random, confusion) -> dict | None:
    """Verb conjugation drill from the V-004 table (guide §8.5)."""
    if item["category"] != "verb_form":
        return None
    available = [k for k in FORM_PRIORITY if derive_form(item, k)]
    if not available:
        return None
    # Prefer the harder forms. ます形 is the first one learned and stops testing
    # anything once it is automatic, so it is only used when it is all there is.
    harder = [k for k in available if k != "masu"]
    key = rng.choice(harder) if harder else "masu"
    label = CONJUGATION_FORMS[key][0]
    answer = derive_form(item, key)

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
            "accepted": sorted(
                {s for s in (answer, strip_furigana(answer), kana_form(item, answer)) if s}
            ),
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
        (b, derive_form(b, key)) for b in bank
        if b["category"] == "verb_form" and b["id"] != item["id"]
    ]
    others = [(b, form) for b, form in others if form and form != answer]
    tail = item["term"][-1]
    near = [pair for pair in others if pair[0]["term"].endswith(tail)]
    pool = near if len(near) >= 3 else others
    rng.shuffle(pool)
    for _, candidate in pool:
        if len(wrong_options) >= 3:
            break
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
    personal: dict[str, dict],
    usage: dict[str, list[dict]],
    exclude: set[str] | None = None,
) -> dict | None:
    """Build one exercise, trying the requested formats in order.

    `preferred` is a priority list rather than a single choice: many formats are
    impossible for a given item (a particle has no reading to test, a verb-table
    row has no example sentence), and silently falling back to the same default
    every time is what makes a day turn into five multiple-choice questions.
    """
    builders = {
        "personal_correction": lambda: make_personal_correction(item, personal),
        "correction": lambda: make_correction(item, rng),
        "naturalness": lambda: make_naturalness(item, rng),
        "conjugation": lambda: make_conjugation(item, bank, rng, confusion),
        "mcq_meaning": lambda: make_mcq_meaning(item, bank, rng, confusion),
        "mcq_reading": lambda: make_mcq_reading(item, bank, rng, confusion),
        "fill_blank": lambda: make_fill_blank(item, rng, avoid),
        "translation": lambda: make_translation(item, rng, avoid),
        "verb_form_choice": lambda: make_verb_form_choice(item, usage, rng, avoid),
        "verb_translation": lambda: make_verb_translation(item, usage, rng, avoid),
    }
    # `exclude` is a hard ban, not a preference: the fallback below tries every
    # remaining builder, so a format merely left out of `preferred` would come
    # straight back — which is how conjugation kept reappearing in the daily
    # five after being moved to its own block.
    for key in exclude or ():
        builders.pop(key, None)
    order = [k for k in preferred if k in builders]
    order += [k for k in builders if k not in order]
    for key in order:
        result = builders[key]()
        if result:
            result["format_key"] = key
            return result
    return None


# Which builders each format key ultimately renders as, for balancing purposes.
FORMAT_DISPLAY = {
    "verb_form_choice": "fill_blank",
    "verb_translation": "translation",
    "personal_correction": "correction",
    "correction": "correction",
    "naturalness": "mcq",
    "conjugation": "conjugation",
    "mcq_meaning": "mcq",
    "mcq_reading": "mcq",
    "fill_blank": "fill_blank",
    "translation": "translation",
}


def candidate_formats(
    item: dict, personal: dict[str, dict], allow_conjugation: bool = True
) -> list[str]:
    """Formats this item could plausibly support, best first.

    `allow_conjugation` is off whenever the day carries its own drill block:
    form conversion belongs there, and spending one of the daily five on it
    would ask the same thing twice in one sitting.
    """
    if item["category"] == "mistake":
        return ["correction" if item.get("severity") == "error" else "naturalness"]
    if item["category"] == "verb_form":
        # Without the drill block the plain conversion is still the best question
        # for a verb-table row. With it, the same verb is asked the harder way:
        # decide the form from the sentence, or produce the whole sentence.
        harder = ["verb_form_choice", "verb_translation", "mcq_reading"]
        return (["conjugation"] + harder) if allow_conjugation else harder
    formats = ["fill_blank", "translation", "mcq_meaning", "mcq_reading"]
    # Re-testing a sentence the learner actually got wrong beats any generated
    # question for that item, so it goes first when one exists (guide §5.1).
    if item["id"] in personal:
        return ["personal_correction"] + formats
    return formats


def order_by_balance(options: list[str], used: dict[str, int], rng: random.Random) -> list[str]:
    """Put the least-used display format first, so a day spreads across formats."""
    shuffled = list(options)
    rng.shuffle(shuffled)
    return sorted(shuffled, key=lambda key: used.get(FORMAT_DISPLAY.get(key, key), 0))


def drill_problems(drills: list[dict], expected: int) -> list[str]:
    """The drills get the same refusal-to-ship treatment as the daily five."""
    problems: list[str] = []
    if len(drills) != expected:
        problems.append(f"expected {expected} drills, produced {len(drills)}")
    seen: set[str] = set()
    for d in drills:
        tag = f"drill #{d.get('n')} {d.get('item_id')}"
        if not d.get("answer"):
            problems.append(f"{tag}: no answer")
        if not d.get("accepted"):
            problems.append(f"{tag}: no accepted answers")
        if d.get("answer") == d.get("source_form"):
            problems.append(f"{tag}: answer repeats the form it was given")
        if d.get("item_id") in seen:
            problems.append(f"{tag}: same verb drilled twice in one day")
        seen.add(d.get("item_id"))
    return problems


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
        # Markdown that leaked out of the handbook is never a valid answer.
        for field in ("answer", *(ex.get("options") or [])):
            value = ex.get(field) if field == "answer" else field
            if isinstance(value, str) and MARKUP_RE.match(value.strip()):
                problems.append(f"{tag}: markup leaked into an answer/option: {value[:30]!r}")
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
    parser.add_argument(
        "--drills", type=int, default=5,
        help="verb-form conversion drills to append (0 disables them)",
    )
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
    # Sentences from elsewhere in the handbook that use each V-004 verb, so the
    # verb table can be asked with real context and not only as conversion.
    usage = verb_usage_index(bank)

    # Drop any existing entry for the target date: on a --force regeneration the
    # previous run's own entry would otherwise damp the very items it served,
    # making repeated runs of the same date produce different sets.
    history = [h for h in load_jsonl(HISTORY_PATH) if h.get("date") != args.date]
    mistakes = load_jsonl(MISTAKES_PATH)
    attempts = load_jsonl(ATTEMPTS_PATH)

    mastery = build_mastery(attempts, mistakes)
    personal = personal_errors(mistakes)

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

    # Form conversion has its own block below, so the daily five leave it out.
    allow_conjugation = args.drills <= 0

    exercises = []
    used_formats: dict[str, int] = {}
    # Spares to draw on when a picked item cannot produce a question at all —
    # otherwise the day silently comes up short and the quality check kills it.
    spares = [
        it for it in bank
        if it["id"] not in {s["id"] for s in selected}
    ]
    rng.shuffle(spares)
    queue = list(selected)
    while queue and len(exercises) < args.count:
        item = queue.pop(0)
        options = candidate_formats(item, personal, allow_conjugation)
        if options and options[0] == "personal_correction":
            # A personal correction is a deliberate priority, not something to be
            # shuffled away for the sake of format balance.
            wanted = options
        elif item["category"] == "verb_form":
            # Verbs keep their own priority: work out the form from the sentence,
            # or produce the whole sentence. Balancing would keep promoting the
            # reading question, which is the easiest thing a verb can be asked
            # and is already covered by writing the forms in the drill block.
            wanted = list(options)
            if len(wanted) >= 2:
                head = wanted[:2]
                rng.shuffle(head)
                wanted[:2] = head
        else:
            wanted = order_by_balance(options, used_formats, rng)
        ex = build_exercise(
            item, bank, wanted, rng, confusion, recent_probes, personal, usage,
            exclude=None if allow_conjugation else {"conjugation"},
        )
        if ex is None:
            if spares:
                queue.append(spares.pop(0))
            continue
        ex["n"] = len(exercises) + 1
        display = FORMAT_DISPLAY.get(ex.pop("format_key", ""), ex["type"])
        used_formats[display] = used_formats.get(display, 0) + 1
        exercises.append(ex)

    # --- verb-form drills -------------------------------------------------
    # A separate block from the daily five: no sentence, no context, just a
    # form conversion. Selection uses the same mastery machinery, but over its
    # own history so a verb drilled yesterday is not drilled again today while
    # still being free to appear in the main set.
    drills: list[dict] = []
    if args.drills > 0:
        # A verb already asked in the daily five is not drilled again the same
        # day: two questions on one item makes the set feel narrower than it is.
        served = {e["item_id"] for e in exercises}
        verbs = [b for b in bank if b["category"] == "verb_form" and b["id"] not in served]
        drill_history = [
            {"date": h.get("date"), "item_ids": h.get("drill_item_ids", [])} for h in history
        ]
        drill_weights = build_weights(verbs, drill_history, mastery, args.date)
        weak_verbs = [
            v for v in verbs
            if v["id"] in mastery and mastery[v["id"]]["mastery"] < MASTERY_THRESHOLD
        ]
        weak_verbs.sort(key=lambda v: (mastery[v["id"]]["mastery"], v["id"]))
        # The verb pool is small enough that one stubborn verb would otherwise
        # hold a weak slot every single day — with a single weak verb on record
        # it appeared 29 days out of 30. A verb just drilled sits out of the
        # reserved slots for two days; the slot is then left to the weighted
        # sample, which still favours weak items but damps recent ones, so the
        # verb returns every few days instead of every day.
        cooling: set[str] = set()
        for row in drill_history[-DRILL_COOLDOWN:]:
            cooling.update(row.get("item_ids", []))
        rested = [v for v in weak_verbs if v["id"] not in cooling]
        picks = rested[: min(REVIEW_SLOTS, args.drills)]
        rest = [v for v in verbs if v["id"] not in {p["id"] for p in picks}]
        picks += weighted_sample(rest, drill_weights, args.drills - len(picks), rng)
        rng.shuffle(picks)
        for verb in picks:
            drill = make_conjugation_drill(verb, rng)
            if drill is None:
                continue
            drill["n"] = len(drills) + 1
            drills.append(drill)

    review_ids = [
        e["item_id"] for e in exercises
        if e["item_id"] in mastery and mastery[e["item_id"]]["mastery"] < MASTERY_THRESHOLD
    ]

    problems, warnings = quality_check(
        exercises, args.count, recent_probes, {b["id"]: b for b in bank}
    )
    problems += drill_problems(drills, args.drills)
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
        "drill_count": len(drills),
        "drills": drills,
    }

    EXERCISE_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    history.append(
        {
            "date": args.date,
            "item_ids": [e["item_id"] for e in exercises],
            "drill_item_ids": [d["item_id"] for d in drills],
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

    print(f"Wrote {out_path} ({len(exercises)} exercises, {len(drills)} drills)")
    for e in exercises:
        marker = " [复习]" if e["item_id"] in review_ids else ""
        print(f"  {e['n']}. [{e['type']}] {e['item_id']}{marker}")
    for d in drills:
        print(f"  变形 {d['n']}. {d['item_id']} {d['source_form']}（{d['source_label']}）"
              f" → {d['form_label']}：{d['answer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
