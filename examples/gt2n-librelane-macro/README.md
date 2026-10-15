# GT2N LibreLane macro example

A LibreLane **Classic** flow example (hard macro, no pad ring) for the GT2N
2 nm nanosheet PDK, organised like IHP's
[ihp-sg13-librelane-template](https://github.com/IHP-GmbH/ihp-sg13-librelane-template).
GT2N has no I/O pad or SRAM library, so this example stops at the macro level.

```
src/gt2n_demo.v          RTL (16-bit LFSR + 8-bit accumulator)
librelane/config.yaml    LibreLane configuration (Classic flow)
cocotb/gt2n_demo_tb.py   cocotb testbench (RTL and gate level)
flake.nix, shell.nix     Nix shell with LibreLane and its nix-eda tools
Makefile                 entry points (make help)
```

## Prerequisites

Enter the Nix shell (LibreLane `dev` and its tools from
[nix-eda](https://github.com/fossi-foundation/nix-eda), as in the IHP template):

```
nix-shell
```

The PDK is the `gt2n/` directory of this repository; the Makefile points
LibreLane at it (`--pdk gt2n --pdk-root <repo> --manual-pdk`).

## Run

```
make librelane                     # Classic flow, final views copied to final/
make librelane SCL=gt2_6t_w31_lvt  # another W/VT flavour
make librelane-klayout             # view the last run
make lvs                           # transistor-level LVS of final/ (KLayout)
make sim                           # RTL simulation
make sim-gl                        # gate-level simulation of final/nl
```

## What is GT2N-specific

- **Buried power rails.** The cell rails are BPR, a layer the router cannot
  use (`gt2_fspdn_tech.lef` declares it MASTERSLICE). They reach the
  frontside only through the `gt2_6t_tapfspdn_*` tap cells. The PDK's
  `PDN_CFG` (`gt2n/libs.tech/librelane/gt2n_pdn_cfg.tcl`) builds an M2..M9
  mesh, checks that every rail has a tap cell (the tap cell is also the end
  cap of every row) and then ties every tap pin to the M3 stripes.
- **Units.** The GT2N Liberty files use ps/ohm. `gt2n_base.sdc` switches the
  SDC command units to ns and ohm, the units of the PDK `LAYERS_RC`/`VIAS_R`
  (`CLOCK_PERIOD` is in ns, as usual).
- **Resizer margins.** GT2N gates switch in about 10 ps, so `config.yaml`
  scales LibreLane's setup/hold repair margins down to 5-10 ps.
- **LVS.** LibreLane's `Magic.SpiceExtraction`/`Netgen.LVS` compare the
  routed design at cell level (DEF + cell LEF abstracts). For
  transistor-level LVS, LibreLane's `KLayout.LVS` step only runs for the IHP
  PDKs, so `make lvs` writes the CDL of `final/odb` with OpenROAD
  (`scripts/write_cdl.tcl`) and compares it with `final/gds` using the PDK
  deck `gt2n/libs.tech/klayout/tech/lvs/gt2n.lylvs`; it also fails when a
  cell's rails do not reach VDD/VSS through the tap cells.
- **Abstract.** `final/lef/gt2n_demo.lef` (`Magic.WriteLEF`) carries
  obstructions on BPR and M0..M8, so a parent design routes around the
  macro.
- **IR drop.** OpenROAD PSM only sees the tap cells (the cell supply pins
  are on BPR), so `OpenROAD.IRDropReport` is substituted out.

## Status

Results of `make librelane` (`gt2_6t_w31_svt`, 30 x 30 um die, 1 GHz clock):

| Check | Result |
| --- | --- |
| Detailed routing (TritonRoute) | 0 violations |
| KLayout DRC (`gt2n.lydrc`, route mode) | 0 errors |
| Magic DRC | 0 errors |
| Magic vs KLayout stream-out XOR | 0 differences |
| PDN check (`Checker.PowerGridViolations`) | 0 violations; all 201 BPR rails tapped |
| Cell-level LVS (Magic + Netgen) | circuits match uniquely, 0 illegal overlaps |
| Setup / hold (tt 0.7 V 25 C, RCX) | met (worst slack +0.65 ns / +0.025 ns) |
| Max slew (0.1 ns) / max cap / max fanout | 0 violations |
| Transistor-level LVS (`make lvs`) | netlists match (1152 devices) |
| Antenna | not checked: GT2N defines no antenna rules |

291 logic and clock cells (32 flip-flops) plus 501 tap and about 135000
filler cells, 2.1 % utilisation of the 30 x 30 um die; the flow runs in
about four minutes, the LVS in about one and a half. The routing-layer DRC
is LibreLane's; the device and MOL rules of the cells are checked by the PDK
QA (`make -C gt2n test-drc`, also on a placed block of every cell).

- RTL and gate-level simulation (Icarus + cocotb) pass against the Python
  reference model.
- The LibreLane configuration loads for all ten libraries
  (`gt2n/libs.qa/librelane/check_config.py`).
- `make sim` / `make sim-gl` exit non-zero when a test fails.
