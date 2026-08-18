#!/usr/bin/env python3
"""Assert that every item-bank ID is accepted by the result-ingest validator.

`ingest_mistakes.py` silently discards any result whose `item_id` fails
`VALID_ID_RE`, which is correct for junk but disastrous for a legitimate ID the
pattern has not been taught about: the answer is dropped without an error and
the learner's history quietly loses entries.

That is exactly what happened when the V-004 verb table added 100 `VF-*` items
while the pattern still only knew `V-`. This check runs in CI so the next new ID
prefix fails the build instead of eating data.

Usage:
  python3 exercise-generator/check_id_pattern.py
"""
from __future__ import annotations

import collections
import sys

from ingest_mistakes import VALID_ID_RE
from itembank import load_irregular_forms, load_item_bank


def main() -> int:
    bank = load_item_bank()
    if not bank:
        print("Item bank is empty — nothing to check.", file=sys.stderr)
        return 1

    rejected = [item["id"] for item in bank if not VALID_ID_RE.match(item["id"])]

    if rejected:
        by_prefix = collections.Counter(i.split("-")[0] for i in rejected)
        print("FAIL: these item IDs would be discarded when a result is reported.")
        print(f"  {len(rejected)} of {len(bank)} items affected")
        for prefix, count in sorted(by_prefix.items()):
            print(f"  prefix {prefix!r}: {count} items (e.g. {next(i for i in rejected if i.startswith(prefix))})")
        print("\nAdd the prefix to VALID_ID_RE in exercise-generator/ingest_mistakes.py.")
        print("Order matters: a longer prefix must precede any prefix it starts with,")
        print("so VF comes before V.")
        return 1

    prefixes = sorted({i["id"].split("-")[0] for i in bank})
    print(f"OK: all {len(bank)} item IDs are accepted.")
    print(f"    prefixes in use: {', '.join(prefixes)}")

    return check_irregular_forms(bank)


def check_irregular_forms(bank: list[dict]) -> int:
    """V-009 must actually reach the verbs it names.

    A typo in the table is silent otherwise: the row parses, no verb matches it,
    and the drill goes on serving the regular — wrong — form.
    """
    irregular = load_irregular_forms()
    if not irregular:
        print("FAIL: handbook V-009 parsed to nothing; check the table format.")
        return 1

    verbs = {
        (b.get("forms") or {}).get("dictionary") or b["term"]
        for b in bank
        if b["category"] == "verb_form" or b["id"].startswith("W-V")
    }
    unmatched = sorted(set(irregular) - verbs)

    print(f"OK: handbook V-009 lists {len(irregular)} irregular verbs.")
    if unmatched:
        # Not fatal: a verb may be listed ahead of being added to the handbook,
        # which is better than the exception being forgotten. Say so loudly.
        print(f"    note: {len(unmatched)} not (yet) a handbook verb entry: {', '.join(unmatched)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
