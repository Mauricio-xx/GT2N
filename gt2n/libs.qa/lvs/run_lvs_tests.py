#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Positive and negative LVS cases for libs.tech/klayout/tech/lvs/gt2n.lylvs.

make_lvs_tests.py builds the cases from the cells of a libs.ref library in
the work directory (nothing is committed): library cells against their CDL,
mutated cells (tap without VBPR, shorted tap/filler supplies, gate length or
sheet width 1 nm off) and small blocks, in transistor and abstract mode (tap
plus abutting inverters, a filler between two inverters, cells whose rails do
not reach the labelled supply, a flip-flop with its second vss rail not
connected), some also in signal-only abstract mode, which leaves the supplies
out. Each case runs through the deck and must give the expected verdict, with
the expected reason in the log: positive cases must match and show that
something was compared, negative cases must not match.

Usage: run_lvs_tests.py [--workdir DIR] [-j N] [--deck DECK] [lib ...]   (requires klayout in PATH)
The default library is gt2_6t_w31_svt.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PDK = HERE.parents[1]
DECK = PDK / "libs.tech" / "klayout" / "tech" / "lvs" / "gt2n.lylvs"
MATCH = "INFO : Congratulations! Netlists match."
MISMATCH = "ERROR : Netlists don't match"


def run_case(case, work, deck):
    name = case["name"]
    cmd = ["klayout", "-b", "-r", str(deck), "-rd", f"input={case['gds']}", "-rd", f"topcell={case['top']}",
           "-rd", f"schematic={case['cdl']}", "-rd", f"lvs_mode={case['mode']}", "-rd", "threads=1",
           "-rd", f"report={work / (name + '.lvsdb')}"]
    for key, value in case.get("options", {}).items():
        cmd += ["-rd", f"{key}={value}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    out = res.stdout + res.stderr
    (work / f"{name}_lvs.log").write_text(out)
    verdict = MATCH if MATCH in out else MISMATCH if MISMATCH in out else None
    want = MATCH if case["expect"] == "match" else MISMATCH
    if verdict is None:
        return False, "no verdict (KLayout error?)"
    if verdict != want:
        return False, f"got '{verdict}'"
    if not re.search(case["log"], out):
        return False, f"/{case['log']}/ not in the log"
    return True, ""


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workdir", default=str(HERE.parent / "run" / "lvs_tests"))
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1)
    parser.add_argument("--deck", default=str(DECK), help="LVS deck under test (default: the PDK deck)")
    parser.add_argument("libs", nargs="*")
    args = parser.parse_args()
    failed = 0
    total = 0
    for lib in args.libs or ["gt2_6t_w31_svt"]:
        work = Path(args.workdir).resolve() / lib
        work.mkdir(parents=True, exist_ok=True)
        gen = subprocess.run(["klayout", "-b", "-r", str(HERE / "make_lvs_tests.py"),
                              "-rd", f"lib_dir={PDK / 'libs.ref' / lib}", "-rd", f"out_dir={work}"],
                             capture_output=True, text=True)
        manifest = work / "cases.json"
        if gen.returncode != 0 or not manifest.exists():
            sys.exit(f"{lib}: case generation failed\n{gen.stdout}{gen.stderr}")
        cases = json.loads(manifest.read_text())["cases"]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(lambda c: run_case(c, work, args.deck), cases))
        for case, (ok, msg) in zip(cases, results):
            total += 1
            failed += not ok
            why = f" ({case['why']})" if case["why"] else ""
            print(f"{'PASS' if ok else 'FAIL'} {lib} {case['name']}: expect {case['expect']}{why}"
                  + ("" if ok else f": {msg}"))
        sys.stdout.flush()
    print(f"{total - failed}/{total} LVS cases as expected")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
