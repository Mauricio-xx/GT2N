# SPDX-License-Identifier: BSD-3-Clause
"""Shared definitions for the GT2N open-source PDK generator scripts.

The legacy GT2N collateral (top-level lib/, lef/, gds/, cdl/, techlib/, ...)
stays the single source of truth. Everything under gt2n/libs.ref is derived
from it by the scripts in this directory, so upstream updates to the legacy
files only need a re-run of `make -C gt2n libs-ref`.
"""

from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PDK_DIR = SCRIPTS_DIR.parent            # .../GT2N/gt2n
REPO_DIR = PDK_DIR.parent               # .../GT2N
LIBS_REF = PDK_DIR / "libs.ref"
LIBS_TECH = PDK_DIR / "libs.tech"

PDK_NAME = "gt2n"

# Nanosheet widths (nm) and threshold-voltage flavors shipped by GT2N.
WIDTHS = ("w13", "w31")
VTS = ("elvt", "ulvt", "lvt", "svt", "hvt")

# Supply nets used by the standard cells (LEF/Liberty/CDL pin names).
POWER_PIN = "vdd"
GROUND_PIN = "vss"
NOMINAL_VDD = 0.7

SITE_NAME = "gt2_6t"


def flavors():
    """Yield (width, vt) pairs in a stable order."""
    for width in WIDTHS:
        for vt in VTS:
            yield width, vt


def lib_name(width, vt):
    """Name of a standard-cell library (one per W/VT flavor)."""
    return f"gt2_6t_{width}_{vt}"


def all_libs():
    return [lib_name(w, v) for w, v in flavors()]


def corners():
    """Process corners available in the legacy lib/ directory."""
    return sorted(p.name for p in (REPO_DIR / "lib").iterdir() if p.is_dir())
