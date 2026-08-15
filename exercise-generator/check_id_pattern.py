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
from itembank import load_item_bank


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
