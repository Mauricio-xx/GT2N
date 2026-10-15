# SPDX-FileCopyrightText: 2025 LibreLane Template Contributors
# SPDX-License-Identifier: Apache-2.0
# Adapted from IHP-GmbH/ihp-sg13-librelane-template (Apache-2.0).
#
# cocotb testbench of the GT2N LibreLane macro example.
#
#   python3 gt2n_demo_tb.py          RTL simulation (src/gt2n_demo.v)
#   GL=1 python3 gt2n_demo_tb.py     gate-level simulation of final/nl/ using the
#                                    GT2N standard-cell Verilog models
#                                    (GL_NETLIST=<file> selects another netlist)
#
# Environment: PDK_ROOT (directory containing gt2n/), PDK (gt2n),
# SCL (standard-cell library, default gt2_6t_w31_svt), SIM (icarus).
# The exit status is non-zero when a test fails or none ran.

import os
import random
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, FallingEdge, RisingEdge
from cocotb_tools.check_results import get_results
from cocotb_tools.runner import get_runner

PROJ = Path(__file__).resolve().parent.parent
sim = os.getenv("SIM", "icarus")
pdk_root = Path(os.getenv("PDK_ROOT", PROJ.parent.parent))
pdk = os.getenv("PDK", "gt2n")
scl = os.getenv("SCL", "gt2_6t_w31_svt")
gl = os.getenv("GL", "") not in ("", "0")

hdl_toplevel = "gt2n_demo"


class Model:
    """Cycle-accurate reference model of gt2n_demo."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.lfsr, self.acc, self.dout = 0xACE1, 0, 0

    def clock(self, rst_n, en, din):
        if not rst_n:
            self.reset()
            return
        fb = ((self.lfsr >> 15) ^ (self.lfsr >> 13) ^ (self.lfsr >> 12) ^ (self.lfsr >> 10)) & 1
        lfsr, acc = self.lfsr, self.acc
        self.lfsr = ((lfsr << 1) | fb) & 0xFFFF
        if en:
            self.acc = (acc + din) & 0xFF
        self.dout = (acc ^ lfsr) & 0xFF


@cocotb.test()
async def test_random_stimulus(dut):
    """Compare the design against the reference model for random inputs."""
    cocotb.start_soon(Clock(dut.clk, 2, unit="ns").start())
    model = Model()
    rng = random.Random(2026)

    dut.rst_n.value = 0
    dut.en.value = 0
    dut.din.value = 0
    await ClockCycles(dut.clk, 3)
    await FallingEdge(dut.clk)

    for cycle in range(500):
        rst_n = 0 if rng.random() < 0.02 else 1
        en = rng.getrandbits(1)
        din = rng.getrandbits(8)
        dut.rst_n.value = rst_n
        dut.en.value = en
        dut.din.value = din
        await RisingEdge(dut.clk)
        model.clock(rst_n, en, din)
        await FallingEdge(dut.clk)
        assert int(dut.lfsr.value) == model.lfsr, f"cycle {cycle}: lfsr"
        assert int(dut.dout.value) == model.dout, f"cycle {cycle}: dout"


def gt2n_demo_runner():
    if gl:
        scl_dir = pdk_root / pdk / "libs.ref" / scl
        netlist = Path(os.getenv("GL_NETLIST", PROJ / "final" / "nl" / f"{hdl_toplevel}.nl.v"))
        sources = [scl_dir / "verilog" / f"{scl}.v", netlist]
    else:
        sources = [PROJ / "src" / f"{hdl_toplevel}.v"]

    runner = get_runner(sim)
    runner.build(
        sources=sources,
        hdl_toplevel=hdl_toplevel,
        always=True,
        waves=True,
        timescale=("1ns", "1ps"),
        build_dir=PROJ / "cocotb" / "sim_build",
    )
    results = runner.test(
        hdl_toplevel=hdl_toplevel,
        test_module="gt2n_demo_tb",
        test_dir=PROJ / "cocotb",
        waves=True,
    )
    # Runner.test() only returns the results file outside pytest.
    num_tests, num_failed = get_results(results)
    return num_tests > 0 and num_failed == 0


if __name__ == "__main__":
    sys.exit(0 if gt2n_demo_runner() else 1)
