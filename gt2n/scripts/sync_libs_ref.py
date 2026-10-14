#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Populate gt2n/libs.ref/<lib>/{lef,lib,gds,cdl} from the legacy GT2N tree.

Usage:
    sync_libs_ref.py           # copy (only files whose content changed)
    sync_libs_ref.py --check   # exit 1 if libs.ref is out of date

Each W/VT flavor becomes its own standard-cell library, laid out like
IHP-Open-PDK's libs.ref/sg13g2_stdcell:

    libs.ref/gt2_6t_w31_lvt/
        lef/gt2_tech.lef              full BSPDN tech LEF (front + backside)
        lef/gt2_fspdn_tech.lef        frontside-PDN router view tech LEF
        lef/gt2_6t_w31_lvt.lef        cell abstracts
        lib/gt2_6t_w31_lvt_tt_0p7v25c.lib
        gds/gt2_6t_w31_lvt.gds
        cdl/gt2_6t_w31_lvt.cdl        4-terminal (bulk-explicit) netlist
"""

import argparse
import filecmp
import shutil
import sys

from gt2n_common import LIBS_REF, REPO_DIR, all_libs, corners


def file_map():
    """Return a list of (source, destination) pairs."""
    pairs = []
    for lib in all_libs():
        flavor = lib[len("gt2_6t_"):]           # e.g. w31_lvt
        dst = LIBS_REF / lib
        pairs += [
            (REPO_DIR / "techlib" / "gt2_tech.lef", dst / "lef" / "gt2_tech.lef"),
            (REPO_DIR / "techlib" / "gt2_fspdn_tech.lef", dst / "lef" / "gt2_fspdn_tech.lef"),
            (REPO_DIR / "lef" / "tt" / f"{lib}.lef", dst / "lef" / f"{lib}.lef"),
            (REPO_DIR / "gds" / f"gt2_6t_std_cells_{flavor}.gds", dst / "gds" / f"{lib}.gds"),
            (REPO_DIR / "cdl" / "with4nodes" / f"{lib}.cdl", dst / "cdl" / f"{lib}.cdl"),
        ]
        for corner in corners():
            for src in sorted((REPO_DIR / "lib" / corner).glob(f"{lib}_{corner}_*.lib")):
                pairs.append((src, dst / "lib" / src.name))
    return pairs


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true",
                        help="only verify that libs.ref matches the legacy sources")
    args = parser.parse_args()

    stale = []
    for src, dst in file_map():
        if not src.is_file():
            sys.exit(f"error: missing source file {src.relative_to(REPO_DIR)}")
        if dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            continue
        stale.append(dst)
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
            print(f"updated {dst.relative_to(REPO_DIR)}")

    if args.check:
        for dst in stale:
            print(f"out of date: {dst.relative_to(REPO_DIR)}")
        if stale:
            sys.exit("libs.ref is out of date; run `make -C gt2n libs-ref`")
        print("libs.ref is in sync with the legacy GT2N collateral")


if __name__ == "__main__":
    main()
