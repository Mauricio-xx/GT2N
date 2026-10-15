#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Check that every GT2N KLayout DRC rule under test fires, and only where expected.

make_drc_fixtures.py writes one cell per known-bad or known-good pattern
together with the exact number of markers per rule that the deck must
report for that cell in route and in full mode. This script builds the
fixtures, runs libs.tech/klayout/tech/drc/gt2n.lydrc in both modes and
fails on any difference (a missing marker, an extra marker, or a marker
outside every fixture). Markers that the deck reports in TOP (flat checks)
are assigned to the fixture whose bounding box holds their first point.

Usage: run_drc_rules.py [--workdir DIR] [--mode route|full ...] [--deck FILE]
       (requires klayout in PATH)
"""

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]
DECK = PDK / "libs.tech" / "klayout" / "tech" / "drc" / "gt2n.lydrc"


def owner(cell, value, expected):
    """Fixture a marker belongs to: its cell, or for TOP the fixture under it."""
    if cell != "TOP":
        return cell
    x, y = (float(v) for v in re.findall(r"-?\d+(?:\.\d*)?(?:e-?\d+)?", value)[:2])
    for name, fx in expected.items():
        x0, y0, x1, y1 = fx["bbox"]
        if x0 - 1e-4 <= x <= x1 + 1e-4 and y0 - 1e-4 <= y <= y1 + 1e-4:
            return name
    return cell


def run_deck(deck, gds, rdb, mode, expected):
    log = rdb.with_suffix(".log")
    with open(log, "w") as f:
        subprocess.run(["klayout", "-b", "-r", str(deck), "-rd", f"input={gds}",
                        "-rd", "topcell=TOP", "-rd", f"report={rdb}",
                        "-rd", f"drc_mode={mode}"], check=True, stdout=f, stderr=subprocess.STDOUT)
    root = ET.parse(rdb).getroot()
    rules = [c.find("name").text.strip("'") for c in root.find("categories")]
    found = Counter()
    for item in root.iter("item"):
        value = item.find("values")[0].text
        cell = owner(item.find("cell").text, value, expected)
        found[(cell, item.find("category").text.strip("'"))] += 1
    return rules, found


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", default=str(HERE / "run"))
    parser.add_argument("--mode", action="append", choices=("route", "full"))
    parser.add_argument("--deck", default=str(DECK), help="DRC deck to test (default: the PDK deck)")
    args = parser.parse_args()
    work = Path(args.workdir)
    work.mkdir(parents=True, exist_ok=True)
    gds, exp_json = work / "drc_fixtures.gds", work / "drc_fixtures.json"
    subprocess.run(["klayout", "-b", "-r", str(HERE / "make_drc_fixtures.py"),
                    "-rd", f"out_gds={gds}", "-rd", f"out_json={exp_json}"],
                   check=True, capture_output=True)
    expected = json.loads(exp_json.read_text())
    failed = False
    for mode in args.mode or ["route", "full"]:
        rules, found = run_deck(args.deck, gds, work / f"drc_fixtures_{mode}.lyrdb", mode, expected)
        errors = []
        for cell in sorted({c for c, _ in found} - set(expected)):
            errors.append(f"{cell}: markers outside every fixture")
        for cell, modes in sorted(expected.items()):
            want = modes[mode]
            got = {r: n for (c, r), n in found.items() if c == cell}
            for rule in sorted(set(want) | set(got)):
                if want.get(rule, 0) != got.get(rule, 0):
                    errors.append(f"{cell}: {rule} expected {want.get(rule, 0)}, got {got.get(rule, 0)}")
        fired = {r for modes in expected.values() for r in modes[mode]}
        untested = [r for r in rules if r not in fired]
        status = "FAIL" if errors else "PASS"
        print(f"{mode}: {status} ({len(expected)} fixtures, {len(rules) - len(untested)} of "
              f"{len(rules)} rules with a known-bad pattern)")
        for e in errors:
            print(f"    {e}")
        if untested:
            print(f"    no known-bad pattern: {' '.join(untested)}")
        failed |= bool(errors)
    if failed:
        sys.exit("DRC rule fixtures failed")


if __name__ == "__main__":
    main()
