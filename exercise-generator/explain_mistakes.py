#!/usr/bin/env python3
"""Ask Claude to explain each free-text mistake, in Chinese, grounded in the handbook.

The app can only ever say "正确答案是 X". This adds the missing half — *why* the
answer was wrong and which rule it broke — by handing Claude the handbook entry
the question came from, the question itself, and what was actually written.

Deliberately a separate script, not part of the daily generation:

  * generation must stay deterministic (same date, same output), and an LLM in
    that path would break it;
  * this reads and writes only `docs/data/`, never `handbook/` — per
    PROJECT_SPEC §3 the handbook is the sole knowledge source and the exercise
    app is read-only against it. Explanations are derived data.

Usage:
  # look at the prompts without an API key or any network call
  python3 exercise-generator/explain_mistakes.py --dry-run --limit 3

  # explain everything not yet explained
  python3 exercise-generator/explain_mistakes.py

  # one day, or one item, re-doing work already done
  python3 exercise-generator/explain_mistakes.py --date 2026-08-23 --force

`ingest_mistakes.py` replaces a day's rows when that day is submitted again, so
an explanation for a re-submitted day is dropped; re-run this to restore it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from itembank import load_confusion_map, load_item_bank  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MISTAKES_PATH = ROOT / "docs" / "data" / "mistakes.jsonl"
EXERCISE_DIR = ROOT / "docs" / "data" / "exercises"
HANDBOOK_DIR = ROOT / "handbook"

MODEL = "claude-opus-5"
# Two or three sentences of Chinese plus a short flag; the ceiling only exists
# so a runaway answer cannot cost real money.
MAX_TOKENS = 2000

SYSTEM = """你是一位日语学习者的批改老师。学习者的母语是中文，正在用一本自己维护的日语手册学习。

你会拿到：手册里的原始条目、当天的题目、学习者写的答案、参考答案。

讲解要求：
- 用中文，两到三句，不要重写整段语法；
- 指出**踩了哪一条规律**（助词用错、自他动词混用、活用规则、同音异字……），而不是只说"应该写成 X"；
- 贴着给出的条目说，能引用条目里的例句就引用；
- 参考答案若用到了条目里没写的语法，**照样把它讲清楚**，别停下来说手册没有；
- 不要说教、不要鼓励语、不要重复题目。"""

# The schema is enforced by the API, so the caller can json.loads() the first
# text block without defensive parsing.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "string",
            "description": "两到三句中文讲解，指出错在哪条规律上。",
        },
        "learner_answer_ok": {
            "type": "boolean",
            "description": (
                "学习者写的答案在日语里是否其实也成立。判分是机械比对，"
                "接近参考答案的写法常常本身就对。"
            ),
        },
    },
    "required": ["analysis", "learner_answer_ok"],
    "additionalProperties": False,
}

ANCHOR_RE = re.compile(r'<a id="([A-Z]+-[A-Za-z0-9]+)"></a>')


def load_rows(path: Path) -> list[dict]:
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


def save_rows(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


# Which chapter of 02-Verbs.md states the rule for each form. A conjugation
# mistake is only explainable against the rule it broke.
FORM_SECTIONS = {
    "辞书形": "V-001",
    "ます形": "V-002",
    "て形": "V-003",
    "た形": "V-005",
    "ない形": "V-006",
    "可能形": "V-007",
    "意向形": "V-008",
}


def section_text(path: Path, section_id: str) -> str:
    """One `<a id="...">`-delimited section of a handbook file, verbatim."""
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8")
    anchors = list(ANCHOR_RE.finditer(text))
    for i, match in enumerate(anchors):
        if match.group(1) != section_id:
            continue
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
        block = text[match.end() : end].strip()
        # A vocabulary entry is a table row whose anchor sits mid-line; the row
        # is the entry, so take the whole line rather than the fragment after
        # the anchor.
        if block.startswith("|") or not block.startswith("#"):
            line_start = text.rfind("\n", 0, match.start()) + 1
            line_end = text.find("\n", match.end())
            line = text[line_start : line_end if line_end != -1 else len(text)].strip()
            if line.startswith("|"):
                return line
        return block
    return ""


def handbook_entry(item: dict, question: dict | None) -> str:
    """Everything in the handbook that bears on this item, verbatim.

    Verbatim rather than the parsed item: 构成 and 注意事项 are where the rule
    actually lives, and the item bank keeps only the gloss and the examples.

    The V-004 verb rows (`VF-…`) are the exception — they have no anchor of
    their own and no example sentences, so what gets sent is the row's own data
    plus the chapter that states the rule for the form the question asked about.
    Without that a conjugation mistake has nothing to be explained against.
    """
    # `source` can carry a fragment, e.g. "handbook/02-Verbs.md#V-004".
    source = ROOT / item["source"].split("#", 1)[0]

    if item["category"] != "verb_form":
        return section_text(source, item["id"])

    forms = " ｜ ".join(f"{k}：{v}" for k, v in (item.get("forms") or {}).items())
    parts = [
        f"{item['term']}（{item['reading']}）［{item['pos']}］：{item['meaning_zh']}",
        f"表中已有的形式：{forms}" if forms else "",
    ]
    wanted = {FORM_SECTIONS.get(question.get("form_label", ""), "")} if question else set()
    wanted.discard("")
    # 分类 first — which class a verb belongs to decides every other form.
    for section_id in ["V-001", *sorted(wanted)]:
        block = section_text(source, section_id)
        if block:
            parts.append(block)
    # The exceptions table, in case this verb is one of them.
    if item["term"] in section_text(source, "V-009"):
        parts.append(section_text(source, "V-009"))
    return "\n\n".join(p for p in parts if p)


def question_for(day: str, item_id: str) -> dict | None:
    """The question as it was asked, including the 再出题 spare batches."""
    path = EXERCISE_DIR / f"{day}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    blocks = [data.get("exercises", []), data.get("drills", [])]
    for group in ("extra_exercises", "extra_drills"):
        blocks.extend(data.get(group, []) or [])
    for block in blocks:
        for exercise in block or []:
            if exercise.get("item_id") == item_id:
                return exercise
    return None


def describe_question(question: dict | None) -> str:
    if not question:
        return "（当天的题目文件里找不到这道题）"
    parts = [f"题型：{question.get('type', '')}", f"题干：{question.get('prompt', '')}"]
    for key, label in (
        ("sentence", "句子"),
        ("sentence_zh", "中文"),
        ("wrong_sentence", "给出的错句"),
        ("hint", "提示"),
    ):
        if question.get(key):
            parts.append(f"{label}：{question[key]}")
    return "\n".join(parts)


# How many confusable entries to send. The handbook flags these itself — 自他
# 动词 pairs, 同音异字 — and they are usually the thing that was actually
# confused, so the entry alone cannot explain the mistake.
MAX_CONFUSABLE = 3


KANJI_HEAD_RE = re.compile(r"^[一-鿿々]+")
# How the handbook words a contrast, as opposed to a plain collocation.
CONTRAST_RE = re.compile(r"自他动词对|同音|不同字|区别|成对记|成组记|注意不要|混淆")


def _is_contrast(text: str) -> bool:
    return bool(CONTRAST_RE.search(text))



def _vocab_pairs(item: dict, entry: str, bank: list[dict], seen: set[str]) -> list[dict]:
    """Vocabulary entries this one is plausibly confused with.

    Vocabulary has no `Related` section, so `load_confusion_map` finds nothing
    for it. The relation is recorded in two other ways, and both are used here:

      * **spelled out in 「常见搭配／区别」** — `与「話（はな）す」同音不同字`,
        `自他动词对：壊れる（自）／壊す（他）`;
      * **implied by the columns themselves** — two entries sharing a reading are
        homophones (話す／離す), and two verbs sharing a kanji stem where one is
        marked 自动词 and the other 他动词 are a transitivity pair (始まる／
        始める). The handbook does not always spell that out — W-V045 does,
        W-V008 does not — and the 始まる／始める mix-up is exactly the mistake
        this whole feature exists to explain.

    Both are derived from what the handbook records （假名 and 类型 columns）,
    not invented.
    """
    term = item["term"]
    reading = item.get("reading")
    head = KANJI_HEAD_RE.match(term)
    stem = head.group(0) if head else ""
    pos = item.get("pos") or ""

    found = []
    for other in bank:
        if other["category"] != "vocab" or other["id"] in seen or other["term"] == term:
            continue
        other_pos = other.get("pos") or ""
        homophone = bool(reading) and other.get("reading") == reading
        transitivity_pair = (
            bool(stem)
            and other["term"].startswith(stem)
            and {"自动词" in pos, "他动词" in pos} == {True, False}
            and {"自动词" in other_pos, "他动词" in other_pos} == {True, False}
            and ("自动词" in pos) != ("自动词" in other_pos)
        )
        # A headword named in the other's row is only a *confusion* when it is
        # named as a contrast. Without that test, plain collocations matched:
        # 「とりあえず始める」 made とりあえず a confusable of 始める, and
        # 「列に並ぶ」 made 列 one of 並ぶ. Two characters minimum at both ends
        # as well — a one-character headword like 西 appears half the chapter.
        named = (
            len(other["term"]) >= 2 and other["term"] in entry and _is_contrast(entry)
        ) or (
            len(term) >= 2
            and term in (other_entry := handbook_entry(other, None) or "")
            and _is_contrast(other_entry)
        )
        if homophone or transitivity_pair or named:
            seen.add(other["id"])
            found.append(other)
    return found


def confusable(item: dict, entry: str, bank: list[dict], confusion) -> list[dict]:
    """Entries the learner could plausibly have confused this one with.

    The entry alone often cannot explain the mistake: 始めました for 始まりました
    is only explainable next to the other half of the pair.
    """
    by_id = {i["id"]: i for i in bank}
    found: list[dict] = []
    seen = {item["id"]}

    # First the handbook's own `Related` sections (grammar, particles,
    # expressions, mistakes), then the vocabulary relations.
    for other_id in sorted(confusion.get(item["id"], set())):
        if other_id in by_id and other_id not in seen:
            seen.add(other_id)
            found.append(by_id[other_id])

    if item["category"] == "vocab" and entry:
        found.extend(_vocab_pairs(item, entry, bank, seen))

    return found[:MAX_CONFUSABLE]


def grammar_index(bank: list[dict]) -> str:
    """Every grammar, particle and expression heading, as a flat list.

    Lets the explanation lean on something the learner has actually studied —
    "这是 G-019 ～てくれる 的反面" lands, an unfamiliar pattern name does not.
    """
    names = [
        f"{i['id']} {i['term']}"
        for i in bank
        if i["category"] in ("grammar", "particle", "expression")
    ]
    return "、".join(names)


def build_user_message(
    row: dict, item: dict, question: dict | None, bank: list[dict], confusion
) -> str:
    entry = handbook_entry(item, question) or "（手册里找不到这个条目）"
    examples = "\n".join(
        f"- {e['ja']}　{e['zh']}" for e in (item.get("examples") or [])
    )

    related = []
    for other in confusable(item, entry, bank, confusion):
        block = handbook_entry(other, None)
        if block:
            related.append(f"### {other['id']}\n\n{block}")

    return f"""## 手册条目 {item['id']}

{entry}

## 该条目的全部例句

{examples or "（无）"}

## 手册标记为容易与它混淆的条目

{chr(10).join(related) if related else "（无）"}

## 学习者已经学过的语法／助词／固定表达（讲解时可以直接引用）

{grammar_index(bank)}

## 当天的题目（{row['date']}）

{describe_question(question)}

## 学习者写的

{row['given']}

## 参考答案

{row.get('expected') or '（缺）'}

## 机器判定

{'接近参考答案（near miss），可能其实也对' if row.get('near') else '与参考答案差别较大'}
"""


def explain(client, system: str, user: str, model: str, effort: str) -> tuple[dict, object]:
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_config={
            "effort": effort,
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), response.usage


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="only this date")
    parser.add_argument("--item", help="only this item id")
    parser.add_argument("--limit", type=int, help="stop after N explanations")
    parser.add_argument("--force", action="store_true", help="redo rows that already have one")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="print the prompts and exit — no API key and no network call",
    )
    parser.add_argument("--model", default=MODEL)
    parser.add_argument(
        "--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"]
    )
    args = parser.parse_args()

    if not MISTAKES_PATH.exists():
        print(f"{MISTAKES_PATH} does not exist yet — nothing to explain.")
        return 0

    bank_list = load_item_bank()
    bank = {i["id"]: i for i in bank_list}
    confusion = load_confusion_map(bank_list)
    rows = load_rows(MISTAKES_PATH)

    todo = []
    orphans: set[str] = set()
    for row in rows:
        # Multiple choice records no answer text: the wrong option is already in
        # the question, so there is nothing to diagnose.
        if not row.get("given"):
            continue
        if row.get("analysis") and not args.force:
            continue
        if args.date and row.get("date") != args.date:
            continue
        if args.item and row.get("item_id") != args.item:
            continue
        if row["item_id"] not in bank:
            # Old records survive renumbering and chapter removals — the
            # Duolingo chapter went in v0.8.0 and its DUO- rows are still here.
            # Nothing to explain them against, and nothing to fix.
            orphans.add(row["item_id"])
            continue
        todo.append(row)

    if args.limit:
        todo = todo[: args.limit]

    if orphans:
        print(f"Skipped {len(orphans)} id(s) no longer in the item bank: {', '.join(sorted(orphans))}")
    if not todo:
        print("Nothing to explain.")
        return 0
    print(f"{len(todo)} mistake(s) to explain.\n")

    if args.dry_run:
        for row in todo:
            item = bank[row["item_id"]]
            print("=" * 72)
            print(f"{row['date']}  {row['item_id']}  ({row['type']})")
            print("=" * 72)
            print(build_user_message(
                row, item, question_for(row["date"], row["item_id"]), bank_list, confusion
            ))
        print(f"\n--dry-run: {len(todo)} prompt(s) shown, nothing sent.")
        return 0

    try:
        import anthropic
    except ImportError:
        print("The anthropic SDK is not installed. `pip install anthropic`", file=sys.stderr)
        return 1

    client = anthropic.Anthropic(max_retries=3)

    done = 0
    tokens_in = tokens_out = 0
    for row in todo:
        item = bank[row["item_id"]]
        user = build_user_message(
            row, item, question_for(row["date"], row["item_id"]), bank_list, confusion
        )
        tag = f"{row['date']} {row['item_id']}"
        try:
            result, usage = explain(client, SYSTEM, user, args.model, args.effort)
        # Most specific first: a bad model id or a missing endpoint is a bug to
        # fix, a 429 is worth reporting as such, and a connection error should
        # not lose the explanations already written.
        except anthropic.NotFoundError as exc:
            print(f"  {tag}: model or endpoint not found — {exc}", file=sys.stderr)
            break
        except anthropic.RateLimitError:
            print(f"  {tag}: rate limited; stopping and keeping what is done", file=sys.stderr)
            break
        except anthropic.APIStatusError as exc:
            print(f"  {tag}: API error {exc.status_code} — skipped", file=sys.stderr)
            continue
        except anthropic.APIConnectionError as exc:
            print(f"  {tag}: could not reach the API — {exc}", file=sys.stderr)
            break
        except (json.JSONDecodeError, StopIteration):
            print(f"  {tag}: no parseable JSON in the response — skipped", file=sys.stderr)
            continue

        row["analysis"] = result["analysis"]
        if result.get("learner_answer_ok"):
            row["analysis_answer_ok"] = True
        tokens_in += usage.input_tokens
        tokens_out += usage.output_tokens
        done += 1
        print(f"  {tag}: {result['analysis']}")
        if result.get("learner_answer_ok"):
            print("      ↳ 这个答案其实也成立，判错了")

    if done:
        save_rows(MISTAKES_PATH, rows)

    print(f"\nExplained {done} of {len(todo)}.")
    print(f"Tokens: {tokens_in} in, {tokens_out} out.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
