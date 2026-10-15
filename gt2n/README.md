# GT2N open-source PDK (`gt2n/`)

Open-source tool support for the GT2N 2 nm nanosheet (GAAFET, backside power
delivery) PDK, organised like the PDKs of
[IHP-Open-PDK](https://github.com/IHP-GmbH/IHP-Open-PDK) (`ihp-sg13g2/`).
The legacy GT2N collateral at the repository root (`lib/`, `lef/`, `gds/`,
`cdl/`, `techlib/`, ... for the proprietary flow) is untouched and remains the
single source of truth: everything under `libs.ref/` is copied or derived from
it by the scripts in `scripts/`.

Point the tools at this PDK with `PDK_ROOT=<repository>` and `PDK=gt2n`.

## Layout

```
gt2n/
├── libs.ref/                 standard-cell libraries, one per W/VT flavour
│   └── gt2_6t_<w13|w31>_<elvt|ulvt|lvt|svt|hvt>/
│       ├── lef/              cell LEF + gt2_tech.lef (full stack)
│       │                     + gt2_fspdn_tech.lef (frontside router view)
│       ├── lib/              Liberty (tt, 0.7 V, 25 C)
│       ├── gds/              cell layouts
│       ├── cdl/              4-terminal netlist (LVS reference)
│       ├── spice/            netlist for ngspice/Xyce (X instances)
│       ├── verilog/          simulation models (generated from Liberty)
│       └── doc/              cell list
├── libs.tech/
│   ├── librelane/            LibreLane PDK + per-library configs, PDN, SDC, OpenRCX
│   ├── klayout/tech/         gt2n.lyt/.lyp/.map, drc/gt2n.lydrc, lvs/gt2n.lylvs
│   ├── magic/                layout-level Magic technology
│   ├── netgen/               Netgen LVS setup
│   └── openroad/             OpenROAD-flow-scripts platform (experimental)
├── libs.qa/                  regressions (make test)
└── scripts/                  generators (make generate)
```

## Tool support

| Tool | Collateral | Status |
| --- | --- | --- |
| Yosys | Liberty, Verilog models | Verilog models formally equivalent to Liberty (all 680 logic cells; flip-flop set and reset paths proven separately) |
| Icarus / Verilator / cocotb | `libs.ref/*/verilog` | flip-flop testbench (UDP and `GT2N_NO_UDP` models, X checks), RTL/GL simulation of the example macro |
| LibreLane (Classic) | `libs.tech/librelane` | configuration loads for all 10 libraries; example macro runs RTL to GDS with 0 routing-layer DRC (KLayout, Magic), 0 XOR, 0 PDN violations, timing met, Netgen cell-level LVS and KLayout transistor-level LVS clean |
| OpenROAD | via LibreLane (PDN, tap hookup, tracks, RC) | see LibreLane |
| KLayout | `libs.tech/klayout/tech` | DRC clean on all libraries, also in a placed block of mirrored rows (2 documented upstream waivers); rule fixtures (`libs.qa/drc`) check that the rules fire. Transistor-level LVS: 690 cells match at device level and the 30 device-less cells (filler, tap cells) pass a supply check; the placed-and-routed example macro matches; positive and negative LVS cases in `libs.qa/lvs` |
| Magic | `libs.tech/magic` | GDS round trip exact (shapes, texts, cells) for all libraries; abutting-cut connectivity, GATE cut by GCUT/DUMMY, LEF OBS for macro abstracts; no device extraction |
| Netgen | `libs.tech/netgen` | nanosheet MOS permutation/property rules; cell-level LVS of the example macro (LibreLane `Netgen.LVS`) matches |
| ngspice / Xyce | `libs.ref/*/spice` | netlists only; the `nmos_<vt>`/`pmos_<vt>` wrappers around the legacy BSIM-CMG cards in `device/tt/` are not provided yet |
| OpenROAD-flow-scripts | `libs.tech/openroad` | experimental, not validated |

## Using the PDK

- **LibreLane**: see `examples/gt2n-librelane-macro/` at the repository root
  and `libs.tech/librelane/README.md`.
- **KLayout**: `KLAYOUT_PATH=$PDK_ROOT/gt2n/libs.tech/klayout klayout`, or run
  the decks in batch, see `libs.tech/klayout/README.md`.
- **Magic**: `magic -rcfile $PDK_ROOT/gt2n/libs.tech/magic/gt2n.magicrc`.

## GT2N specifics

- **Backside power delivery.** Cell rails are buried power rails (`BPR`).
  The router uses the frontside view `gt2_fspdn_tech.lef`, where BPR is a
  MASTERSLICE layer and the backside metals are absent; the rails reach the
  frontside PDN only through the `gt2_6t_tapfspdn_*` tap cells, which the
  PDK's PDN script ties to M3. `gt2_tech.lef` describes the full
  front+backside stack.
- **Units.** Liberty files use ps / ohm / pF. LibreLane designs should use
  `libs.tech/librelane/gt2n_base.sdc`, which switches the SDC command units to
  ns / ohm (ohm is also the unit of the PDK `LAYERS_RC`/`VIAS_R`; a custom SDC
  must start with the same `set_cmd_units` line). The `libs.ref` GDS use a 0.1 nm database unit; the legacy files
  use 0.5 nm, which LibreLane's Magic stream-out rejects. The geometry is
  identical (`scripts/sync_libs_ref.py` rescales the coordinates).
- **Flavours.** One library per nanosheet width (13 nm, 31 nm) and threshold
  voltage (ELVT < ULVT < LVT < SVT < HVT). Cell names carry the flavour
  suffix, e.g. `gt2_6t_nand2_x1_w31_svt`.
- **Corners.** Only the typical corner (tt, 0.7 V, 25 C) is characterised.
- **Double-height cells.** `dffasync_*` and `mux2_*` span two rows with
  vss-vdd-vss rails. Their `libs.ref` LEF declares `SYMMETRY Y` (the legacy
  LEF has `X Y`), which keeps OpenROAD's placer from flipping them onto rows
  with the opposite rail order, a supply short through the BPR.

## Known limitations

- Magic: the backside layers (GDS 910-1000) are not representable (Magic only
  supports GDS layer numbers up to 255), and there is no nanosheet device
  extraction (LibreLane's Magic/Netgen LVS compares at cell level from LEF
  abstracts; transistor-level LVS uses the KLayout deck).
- LibreLane's `KLayout.LVS` step is currently enabled only for the IHP PDKs;
  the GT2N deck is compatible with its interface (`input`, `schematic`,
  `report`, `target_netlist`, same pass/fail messages). The example runs it
  with `make lvs`.
- KLayout DRC waivers (`libs.qa/stdcells/drc_waivers.txt`): `mux2_x1` V0.M1.1
  and the 13 nm `decapcc` VG.ACT.1 are findings in the upstream cell layouts.
  LibreLane keeps both cells out of synthesis. LibreLane runs the DRC deck in
  route mode (routing layers); the device/MOL rules are checked per cell and
  on a placed block of all cells (`make test-drc`).
- LibreLane inserts decap cells after routing; the GT2N decaps carry M1
  shapes, so the PDK configuration uses only the M1-free filler there.
- OpenROAD PSM cannot see BPR. The tap-to-rail coverage is checked by
  `gt2n_tap_to_m3.tcl` (every BPR rail segment must touch a tapfspdn cell)
  and by KLayout LVS, not by PSM; LibreLane's PDN violation metric covers the
  frontside grid and is 0 for a correct GT2N PDN. The IR-drop report is not
  meaningful (it only sees the tap cells).
- No antenna rules: neither the GT2N tech LEF nor the ICV runset defines
  any, so OpenROAD's antenna checks cannot report anything.
- No I/O pad, SRAM or SPICE model support yet.

## Regenerating and testing

```
make generate          # refresh libs.ref and the generated libs.tech files
make check-generated   # verify that the committed files are up to date
make test-fast         # views, Verilog equivalence, flip-flop testbench, DRC rule fixtures
make test              # + KLayout DRC/LVS (cells and LVS cases), Magic, LibreLane config and RC units
```

The regressions need `yosys`, `iverilog`, `klayout`, `magic`, `openroad` and
the `librelane` Python package in `PATH` (the Nix shell of the example
provides all of them).

## License

Same as the GT2N repository (BSD 3-Clause, see `../LICENSE`). The
OpenROAD-derived scripts keep their original notices.
