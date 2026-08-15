#!/usr/bin/env python3
"""Ingest a practice result reported from the web app into docs/data/mistakes.jsonl.

The web app opens a prefilled GitHub issue whose body contains a fenced JSON block:

    ```json
    {"date": "2026-08-15", "results": [{"item_id": "G-002", "type": "mcq", "correct": false}]}
    ```

This script reads that body (from --body, --body-file, or stdin), extracts the JSON,
and appends one line per *missed* item to docs/data/mistakes.jsonl. The generator
then weights those items up so they come back in future exercises.

Usage:
  python3 exercise-generator/ingest_mistakes.py --body-file issue.txt
  echo "$ISSUE_BODY" | python3 exercise-generator/ingest_mistakes.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MISTAKES_PATH = ROOT / "docs" / "data" / "mistakes.jsonl"
ATTEMPTS_PATH = ROOT / "docs" / "data" / "attempts.jsonl"
STATS_PATH = ROOT / "docs" / "data" / "stats.json"

FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
VALID_ID_RE = re.compile(r"^(G|V|P|E|M|R|W-N|W-V|W-I|W-NA|W-ADV|W-CON|DUO)-?\d+$")


def extract_payload(body: str) -> dict:
    """Pull the JSON object out of the issue body (fenced block preferred)."""
    match = FENCE_RE.search(body)
    candidate = match.group(1) if match else None

    if candidate is None:
        start = body.find("{")
        end = body.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found in the issue body.")
        candidate = body[start : end + 1]

    return json.loads(candidate)


def normalize_results(payload: dict) -> tuple[str, list[dict]]:
    day = str(payload.get("date") or datetime.now(timezone.utc).date().isoformat())
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
        raise ValueError(f"Invalid date in payload: {day!r}")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("Payload is missing a 'results' list.")

    cleaned = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        item_id = str(entry.get("item_id", "")).strip()
        if not item_id or not VALID_ID_RE.match(item_id):
            continue
        cleaned.append(
            {
                "item_id": item_id,
                "type": str(entry.get("type", ""))[:32],
                "correct": bool(entry.get("correct")),
            }
        )

    if not cleaned:
        raise ValueError("No valid result entries found in the payload.")
    return day, cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--body", help="issue body text")
    parser.add_argument("--body-file", help="file containing the issue body")
    parser.add_argument("--reporter", default="web-app", help="who reported this result")
    args = parser.parse_args()

    if args.body is not None:
        body = args.body
    elif args.body_file:
        body = Path(args.body_file).read_text(encoding="utf-8")
    else:
        body = sys.stdin.read()

    try:
        payload = extract_payload(body)
        day, results = normalize_results(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Could not read a result payload from the issue body: {exc}", file=sys.stderr)
        return 1

    recorded_at = datetime.now(timezone.utc).isoformat()
    missed = [r for r in results if not r["correct"]]

    MISTAKES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MISTAKES_PATH.open("a", encoding="utf-8") as fh:
        for entry in missed:
            fh.write(
                json.dumps(
                    {
                        "date": day,
                        "item_id": entry["item_id"],
                        "type": entry["type"],
                        "reporter": args.reporter,
                        "recorded_at": recorded_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    # Full record (right and wrong) — the generator uses corrects to retire an item
    # from the review queue once it has been answered correctly enough times.
    with ATTEMPTS_PATH.open("a", encoding="utf-8") as fh:
        for entry in results:
            fh.write(
                json.dumps(
                    {
                        "date": day,
                        "item_id": entry["item_id"],
                        "type": entry["type"],
                        "correct": entry["correct"],
                        "reporter": args.reporter,
                        "recorded_at": recorded_at,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )

    # Refresh a small rollup so the app and README can show progress at a glance.
    all_mistakes = []
    if MISTAKES_PATH.exists():
        for line in MISTAKES_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    all_mistakes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    per_item: dict[str, int] = {}
    for row in all_mistakes:
        iid = row.get("item_id")
        if iid:
            per_item[iid] = per_item.get(iid, 0) + 1

    top = sorted(per_item.items(), key=lambda kv: (-kv[1], kv[0]))[:20]
    STATS_PATH.write_text(
        json.dumps(
            {
                "updated_at": recorded_at,
                "total_misses": len(all_mistakes),
                "distinct_items": len(per_item),
                "top_missed": [{"item_id": k, "misses": v} for k, v in top],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    correct_count = len(results) - len(missed)
    print(f"date={day} answered={len(results)} correct={correct_count} missed={len(missed)}")
    for entry in missed:
        print(f"  missed: {entry['item_id']} ({entry['type']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
