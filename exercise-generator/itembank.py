"""Parse handbook/*.md into a structured item bank used by the exercise generator.

Each item is a dict:
{
  "id": "G-002" | "P-005" | "E-001" | "W-N001" | "DUO-014",
  "category": "grammar" | "particle" | "expression" | "vocab",
  "pos": None or a short part-of-speech tag (vocab only),
  "term": headword or grammar pattern,
  "reading": kana reading if known, else None,
  "meaning_zh": short Chinese gloss,
  "examples": [{"ja": "...", "zh": "..."}, ...],
  "source": relative path of the handbook file the item came from,
}
"""
from __future__ import annotations

import re
from pathlib import Path

HANDBOOK_DIR = Path(__file__).resolve().parent.parent / "handbook"

ANCHOR_RE = re.compile(r'<a id="([A-Z]+-[A-Za-z0-9]+)"></a>')
HEADING_RE = re.compile(r"^##\s+([A-Z]+-[A-Za-z0-9]+)\s+(.+)$", re.MULTILINE)

COLUMN_MAP = {
    "编号": "id_col",
    "单词": "word",
    "假名": "kana",
    "类型": "pos",
    "词性": "pos",
    "中文": "meaning_zh",
    "常见搭配／区别": "collocation",
    "常见搭配": "collocation",
    "例句": "example",
}

POS_SECTION_MAP = {
    "名词": "名",
    "动词": None,  # verb rows carry their own pos via the 类型 column
    "い形容词": "い形",
    "な形容词": "な形",
    "副词": "副",
    "接续词": "接续",
}


def _split_examples(block: str) -> list[dict]:
    """Pull consecutive '> ' blockquote lines out of a text block and pair them (ja, zh)."""
    quote_lines = [
        line[2:].strip() if line.startswith("> ") else line[1:].strip()
        for line in block.splitlines()
        if line.strip().startswith(">")
    ]
    quote_lines = [l for l in quote_lines if l]
    examples = []
    for i in range(0, len(quote_lines) - 1, 2):
        examples.append({"ja": quote_lines[i], "zh": quote_lines[i + 1]})
    return examples


def _is_prose(line: str) -> bool:
    """True for a line that reads as an explanation rather than page furniture.

    Comparison entries such as E-012 open with a markdown table, and taking the
    first non-blank line there yielded `| 表达 | 用法 |` — a table header served
    to the learner as the meaning of the expression.
    """
    if not line:
        return False
    if line.startswith((">", "#", "---", "|", "-", "*", "+")):
        return False
    # A row of table/rule punctuation with no actual words.
    if not re.search(r"[一-鿿぀-ヿA-Za-z]", line):
        return False
    return True


MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def _clean_meaning(text: str) -> str:
    """Reduce a handbook line to plain text; the app renders meanings verbatim.

    Inline-code marks are dropped and markdown links collapse to their label, so
    a cross-reference reads "参见 G-006" rather than showing raw brackets and a
    file path in a multiple-choice option.
    """
    text = MD_LINK_RE.sub(r"\1", text)
    return text.replace("`", "").strip()


def _extract_meaning(block: str) -> str:
    m = re.search(r"###\s*含义\s*\n(.+?)(?=\n###|\n---|\Z)", block, re.DOTALL)
    if m:
        for line in m.group(1).strip().splitlines():
            if _is_prose(line.strip()):
                return _clean_meaning(line.strip())
    # Fallback: the first line of actual prose anywhere in the entry. Tables,
    # examples, headings and link lists are skipped rather than mistaken for a
    # definition; an entry with no prose at all yields "" and is simply not
    # asked as a "what does this mean" question.
    for line in block.splitlines()[1:]:
        stripped = line.strip()
        if _is_prose(stripped):
            return _clean_meaning(stripped)
    return ""


def _parse_prose_file(path: Path, category: str) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    anchors = list(ANCHOR_RE.finditer(text))
    items = []
    for i, anchor_match in enumerate(anchors):
        item_id = anchor_match.group(1)
        start = anchor_match.end()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
        block = text[start:end]

        heading_match = HEADING_RE.search(block)
        term = heading_match.group(2).strip() if heading_match else item_id

        items.append(
            {
                "id": item_id,
                "category": category,
                "pos": None,
                "term": term,
                "reading": None,
                "meaning_zh": _extract_meaning(block),
                "examples": _split_examples(block),
                "source": str(path.relative_to(HANDBOOK_DIR.parent)),
            }
        )
    return items


def _parse_table_line(line: str) -> list[str] | None:
    line = line.strip()
    if not line.startswith("|"):
        return None
    return [c.strip() for c in line.strip("|").split("|")]


DUO_SECTION_RE = re.compile(r"^##\s+Section\s+(\d+)")


def _parse_vocab_file(path: Path, default_pos_by_section: bool) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    items = []
    current_section_pos = None
    current_duo_section = None
    header_keys: list[str] | None = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## "):
            section_name = stripped[3:].strip()
            if default_pos_by_section:
                current_section_pos = POS_SECTION_MAP.get(section_name, current_section_pos)
            duo_match = DUO_SECTION_RE.match(stripped)
            if duo_match:
                current_duo_section = int(duo_match.group(1))
            header_keys = None
            continue

        cells = _parse_table_line(line)
        if cells is None:
            continue

        if "编号" in cells:
            header_keys = [COLUMN_MAP.get(c, c) for c in cells]
            continue

        if header_keys is None or len(cells) != len(header_keys):
            continue

        first_cell = cells[0]
        anchor_match = ANCHOR_RE.search(first_cell)
        if not anchor_match:
            continue

        row = dict(zip(header_keys, cells))
        item_id = anchor_match.group(1)

        example_raw = row.get("example", "")
        if "<br>" in example_raw:
            ja, _, zh = example_raw.partition("<br>")
        else:
            ja, zh = example_raw, ""

        pos = row.get("pos") or current_section_pos
        kana = row.get("kana", "")
        if kana in ("", "—", "-"):
            kana = None

        items.append(
            {
                "id": item_id,
                "category": "vocab",
                "pos": pos,
                "term": row.get("word", ""),
                "reading": kana,
                "meaning_zh": row.get("meaning_zh", ""),
                "examples": [{"ja": ja.strip(), "zh": zh.strip()}] if ja.strip() else [],
                "source": str(path.relative_to(HANDBOOK_DIR.parent)),
                "duo_section": current_duo_section,
            }
        )

    return items


def _parse_mistakes_file(path: Path) -> list[dict]:
    """Parse 06-Mistakes.md into error-correction items.

    Each entry carries a wrong sentence and one or more corrected sentences,
    which is exactly what an error-correction exercise (guide §8.3) needs.
    """
    text = path.read_text(encoding="utf-8")
    anchors = list(ANCHOR_RE.finditer(text))
    items = []

    for i, anchor_match in enumerate(anchors):
        item_id = anchor_match.group(1)
        start = anchor_match.end()
        end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
        block = text[start:end]

        heading_match = HEADING_RE.search(block)
        term = heading_match.group(2).strip() if heading_match else item_id

        # The handbook uses two grades of "before" heading, and marks them
        # differently: ❌ for genuinely wrong Japanese, △ for grammatical but
        # less idiomatic. They must not be taught the same way, so the
        # distinction is preserved as `severity`.
        wrong_section = re.search(
            r"###\s*(?:Wrong|Incorrect choice|Less natural)\s*\n(.*?)(?=\n###|\Z)", block, re.DOTALL
        )
        correct_section = re.search(
            r"###\s*(?:Correct|More natural)\s*\n(.*?)(?=\n###|\Z)", block, re.DOTALL
        )
        why_section = re.search(r"###\s*Why\s*\n(.*?)(?=\n###|\n---|\Z)", block, re.DOTALL)
        if not (wrong_section and correct_section):
            continue

        def _quotes(chunk: str) -> list[str]:
            out = []
            for line in chunk.splitlines():
                stripped = line.strip()
                if stripped.startswith(">"):
                    out.append(stripped.lstrip("> ").strip())
            return [q for q in out if q]

        wrong_lines = _quotes(wrong_section.group(1))
        correct_lines = _quotes(correct_section.group(1))

        # Lines are (sentence, gloss) pairs marked with ❌ / △ / ✅.
        wrong_sentences = [
            l.lstrip("❌△ ").strip() for l in wrong_lines if l.startswith("❌") or l.startswith("△")
        ]
        severity = "error" if any(l.startswith("❌") for l in wrong_lines) else "unnatural"
        intent = next((l for l in wrong_lines if l.startswith("想表达")), "")
        correct_sentences = [l.lstrip("✅ ").strip() for l in correct_lines if l.startswith("✅")]

        if not wrong_sentences or not correct_sentences:
            continue

        # The gloss line following each ✅ sentence is its translation.
        correct_pairs = []
        for idx, line in enumerate(correct_lines):
            if line.startswith("✅"):
                sentence = line.lstrip("✅ ").strip()
                gloss = ""
                if idx + 1 < len(correct_lines) and not correct_lines[idx + 1].startswith("✅"):
                    gloss = correct_lines[idx + 1]
                correct_pairs.append({"ja": sentence, "zh": gloss})

        items.append(
            {
                "id": item_id,
                "category": "mistake",
                "pos": None,
                "term": term,
                "reading": None,
                "meaning_zh": (why_section.group(1).strip().splitlines()[0].strip() if why_section else ""),
                "wrong": wrong_sentences[0],
                "severity": severity,
                "intent_zh": intent.replace("想表达：", "").strip(),
                "corrections": correct_pairs,
                "why": why_section.group(1).strip() if why_section else "",
                "examples": correct_pairs,
                "source": str(path.relative_to(HANDBOOK_DIR.parent)),
                "duo_section": None,
            }
        )

    return items


def _parse_verb_table(path: Path) -> list[dict]:
    """Parse the V-004 100-verb conjugation table into verb-form items.

    Gives the generator real conjugation data (dictionary / ます / て form plus
    verb class), which error-prone conjugation questions need (guide §8.5).
    """
    text = path.read_text(encoding="utf-8")
    section = re.search(r"##\s*V-004.*?(?=\n##\s|\Z)", text, re.DOTALL)
    if not section:
        return []

    items = []
    header_keys: list[str] | None = None
    for line in section.group(0).splitlines():
        cells = _parse_table_line(line)
        if cells is None:
            continue
        # The handbook writes the header with the simplified 书; accept either form.
        if any(c in ("辞书形", "辞書形") for c in cells):
            header_keys = ["辞书形" if c == "辞書形" else c for c in cells]
            continue
        if header_keys is None or len(cells) != len(header_keys):
            continue
        row = dict(zip(header_keys, cells))
        number = row.get("编号", "").strip()
        dictionary = row.get("辞书形", "").strip()
        if not number.isdigit() or not dictionary:
            continue

        items.append(
            {
                # Namespaced so it never collides with the V-001..V-008 prose entries.
                "id": f"VF-{int(number):03d}",
                "category": "verb_form",
                "pos": row.get("类型", "").strip() or None,
                "term": dictionary,
                "reading": row.get("假名", "").strip() or None,
                "meaning_zh": row.get("中文", "").strip(),
                "forms": {
                    "dictionary": dictionary,
                    "masu": row.get("ます形", "").strip(),
                    "te": row.get("て形", "").strip(),
                },
                "examples": [],
                "source": f"{path.relative_to(HANDBOOK_DIR.parent)}#V-004",
                "duo_section": None,
            }
        )

    return items


RELATED_RE = re.compile(r"###\s*(?:Related|易混淆表达)\s*\n(.*?)(?=\n###|\n---|\Z)", re.DOTALL)
ID_IN_TEXT_RE = re.compile(r"\b([GPEVMR]-\d{3}|W-(?:N|V|I|NA|ADV|CON)\d{3}|DUO-\d{3})\b")


def load_confusion_map(items: list[dict] | None = None) -> dict[str, set[str]]:
    """Which items the handbook itself flags as easily confused with which.

    Built from the `Related` and `易混淆表达` sections the handbook already
    maintains, so distractors come from the user's own recorded confusions
    rather than from unrelated items that are trivially eliminated.

    Those sections reference other entries two ways — by ID (`G-030`) and by name
    (`～ように`) — and the most valuable pairs are written by name, so both are
    resolved. The ために/ように pair, for instance, exists only as prose.
    """
    if items is None:
        items = load_item_bank()

    # Longest first so ～ようになる wins over ～ように when both could match.
    term_index: list[tuple[str, str]] = []
    for it in items:
        for variant in re.split(r"[／/]", it["term"]):
            cleaned = re.sub(r"（[^）]*）", "", variant).strip().strip("～")
            # Single characters (particles) appear everywhere and would produce
            # noise rather than genuine confusions.
            if len(cleaned) >= 2:
                term_index.append((cleaned, it["id"]))
    term_index.sort(key=lambda pair: -len(pair[0]))

    pairs: dict[str, set[str]] = {}
    for name in ("01-Grammar.md", "02-Verbs.md", "03-Particles.md", "04-Expressions.md", "06-Mistakes.md"):
        path = HANDBOOK_DIR / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        anchors = list(ANCHOR_RE.finditer(text))
        for i, anchor_match in enumerate(anchors):
            item_id = anchor_match.group(1)
            start = anchor_match.end()
            end = anchors[i + 1].start() if i + 1 < len(anchors) else len(text)
            block = text[start:end]

            linked: set[str] = set()
            for section in RELATED_RE.finditer(block):
                body = section.group(1)
                linked.update(ID_IN_TEXT_RE.findall(body))
                for term, other_id in term_index:
                    if other_id != item_id and term in body:
                        linked.add(other_id)

            linked.discard(item_id)
            if linked:
                pairs.setdefault(item_id, set()).update(linked)
                # Confusion is symmetric: if A is confusable with B, B is with A.
                for other in linked:
                    pairs.setdefault(other, set()).add(item_id)
    return pairs


def load_item_bank() -> list[dict]:
    items: list[dict] = []
    items += _parse_prose_file(HANDBOOK_DIR / "01-Grammar.md", "grammar")
    # V-001..V-008 explain the conjugation forms themselves (て形, 可能形, ...).
    # The V-004 lookup table in the same file has no example blockquotes, so it
    # drops out here and is parsed separately into per-verb drill items.
    items += _parse_prose_file(HANDBOOK_DIR / "02-Verbs.md", "grammar")
    items += _parse_prose_file(HANDBOOK_DIR / "03-Particles.md", "particle")
    items += _parse_prose_file(HANDBOOK_DIR / "04-Expressions.md", "expression")
    items += _parse_vocab_file(HANDBOOK_DIR / "05-Vocabulary.md", default_pos_by_section=True)
    items += _parse_vocab_file(HANDBOOK_DIR / "08-Duolingo.md", default_pos_by_section=False)

    # Only prose/vocab items need an example sentence; correction and
    # conjugation items carry their own purpose-built data instead.
    items = [it for it in items if it["examples"]]

    items += _parse_mistakes_file(HANDBOOK_DIR / "06-Mistakes.md")
    items += _parse_verb_table(HANDBOOK_DIR / "02-Verbs.md")
    return items


if __name__ == "__main__":
    import json
    import sys

    bank = load_item_bank()
    by_category = {}
    for it in bank:
        by_category.setdefault(it["category"], 0)
        by_category[it["category"]] += 1

    print(f"Total items with examples: {len(bank)}", file=sys.stderr)
    print(f"By category: {by_category}", file=sys.stderr)
    print(json.dumps(bank, ensure_ascii=False, indent=2))
