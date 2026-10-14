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
        gds/gt2_6t_w31_lvt.gds        cell layouts, database unit 1e-10 m (*)
        cdl/gt2_6t_w31_lvt.cdl        4-terminal (bulk-explicit) netlist

(*) The legacy GDS files use a 0.5 nm (5e-10 m) database unit. Magic can
only write sub-nanometre GDS with 1 A units and, when it reads cell GDS
without rescaling (as LibreLane does), requires the same units. The copies
in libs.ref are therefore rewritten with a 1e-10 m database unit (all
coordinates multiplied by 5); the geometry is unchanged.
"""

import argparse
import filecmp
import shutil
import struct
import sys

from gt2n_common import LIBS_REF, REPO_DIR, all_libs, corners


GDS_SCALE = 5            # 5e-10 m -> 1e-10 m database unit
_GDS_UNITS = 0x0305
_GDS_XY = 0x1003


def _gds_real8(value):
    """Encode a GDSII 8-byte excess-64 base-16 real."""
    if value == 0:
        return bytes(8)
    sign = 0x80 if value < 0 else 0
    value = abs(value)
    exponent = 0
    while value >= 1:
        value /= 16
        exponent += 1
    while value < 1 / 16:
        value *= 16
        exponent -= 1
    mantissa = int(round(value * (1 << 56)))
    if mantissa >= 1 << 56:
        mantissa >>= 4
        exponent += 1
    return bytes([sign | (exponent + 64)]) + mantissa.to_bytes(7, "big")


def _gds_read_real8(raw):
    sign = -1 if raw[0] & 0x80 else 1
    exponent = (raw[0] & 0x7F) - 64
    return sign * int.from_bytes(raw[1:], "big") / (1 << 56) * 16 ** exponent


def rescale_gds(data, factor=GDS_SCALE):
    """Return GDSII bytes with the database unit divided by `factor`."""
    out = bytearray()
    pos = 0
    while pos + 4 <= len(data):
        length, rtype = struct.unpack(">HH", data[pos:pos + 4])
        if length < 4:
            out += data[pos:]
            break
        record = data[pos:pos + length]
        if rtype == _GDS_UNITS:
            user = _gds_read_real8(record[4:12]) / factor
            meters = _gds_read_real8(record[12:20]) / factor
            record = record[:4] + _gds_real8(user) + _gds_real8(meters)
        elif rtype == _GDS_XY:
            count = (length - 4) // 4
            coords = struct.unpack(f">{count}i", record[4:])
            record = record[:4] + struct.pack(f">{count}i", *(c * factor for c in coords))
        out += record
        pos += length
    return bytes(out)


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
        if dst.suffix == ".gds":
            content = rescale_gds(src.read_bytes())
            if dst.is_file() and dst.read_bytes() == content:
                continue
        elif dst.is_file() and filecmp.cmp(src, dst, shallow=False):
            continue
        stale.append(dst)
        if not args.check:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.suffix == ".gds":
                dst.write_bytes(content)
            else:
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
