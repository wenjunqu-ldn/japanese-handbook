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


def _extract_meaning(block: str) -> str:
    m = re.search(r"###\s*含义\s*\n(.+?)(?=\n###|\n---|\Z)", block, re.DOTALL)
    if m:
        return m.group(1).strip().splitlines()[0].strip()
    # Fallback: first non-blank, non-blockquote, non-heading line after the title.
    lines = block.splitlines()[1:]
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith(">") or stripped.startswith("#") or stripped.startswith("---"):
            continue
        return stripped
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


def load_item_bank() -> list[dict]:
    items: list[dict] = []
    items += _parse_prose_file(HANDBOOK_DIR / "01-Grammar.md", "grammar")
    items += _parse_prose_file(HANDBOOK_DIR / "03-Particles.md", "particle")
    items += _parse_prose_file(HANDBOOK_DIR / "04-Expressions.md", "expression")
    items += _parse_vocab_file(HANDBOOK_DIR / "05-Vocabulary.md", default_pos_by_section=True)
    items += _parse_vocab_file(HANDBOOK_DIR / "08-Duolingo.md", default_pos_by_section=False)

    # Only keep items that have at least one usable example sentence;
    # exercises are built from example sentences.
    return [it for it in items if it["examples"]]


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
