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
| Yosys | Liberty, Verilog models | Verilog models formally equivalent to Liberty (all 680 logic cells) |
| Icarus / Verilator / cocotb | `libs.ref/*/verilog` | flip-flop testbench, RTL/GL simulation of the example macro |
| LibreLane (Classic) | `libs.tech/librelane` | configuration loads for all 10 libraries; example macro runs RTL to GDS with 0 DRC (KLayout, Magic), 0 XOR, 0 antenna, timing met |
| OpenROAD | via LibreLane (PDN, tap hookup, tracks, RC) | see LibreLane |
| KLayout | `libs.tech/klayout/tech` | DRC clean on all libraries (2 documented upstream waivers); transistor-level LVS matches all 720 cells |
| Magic | `libs.tech/magic` | GDS round trip exact for all libraries; no device extraction |
| Netgen | `libs.tech/netgen` | nanosheet MOS permutation/property rules |
| ngspice / Xyce | `libs.ref/*/spice` | netlists only; BSIM-CMG model cards not ported yet |
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
  ns / kOhm. The `libs.ref` GDS use a 0.1 nm database unit; the legacy files
  use 0.5 nm, which LibreLane's Magic stream-out rejects. The geometry is
  identical (`scripts/sync_libs_ref.py` rescales the coordinates).
- **Flavours.** One library per nanosheet width (13 nm, 31 nm) and threshold
  voltage (ELVT < ULVT < LVT < SVT < HVT). Cell names carry the flavour
  suffix, e.g. `gt2_6t_nand2_x1_w31_svt`.
- **Corners.** Only the typical corner (tt, 0.7 V, 25 C) is characterised.

## Known limitations

- Magic: the backside layers (GDS 910-1000) are not representable (Magic only
  supports GDS layer numbers up to 255), and there is no nanosheet device
  extraction, so LibreLane's Magic/Netgen LVS path is disabled.
- LibreLane's `KLayout.LVS` step is currently enabled only for the IHP PDKs;
  the GT2N deck is compatible with its interface (`input`, `schematic`,
  `report`, `target_netlist`, same pass/fail messages).
- KLayout DRC waivers (`libs.qa/stdcells/drc_waivers.txt`): `mux2_x1` V0.M1.1
  and the 13 nm `decapcc` VG.ACT.1 are findings in the upstream cell layouts.
- LibreLane inserts decap cells after routing; the GT2N decaps carry M1
  shapes, so the PDK configuration uses only the M1-free filler there.
- OpenROAD PSM cannot trace the BPR supply pins, so LibreLane designs must
  set `ERROR_ON_PDN_VIOLATIONS: false` (see `libs.tech/librelane/README.md`).
- No I/O pad, SRAM or SPICE model support yet.

## Regenerating and testing

```
make generate          # refresh libs.ref and the generated libs.tech files
make check-generated   # verify that the committed files are up to date
make test-fast         # views, Verilog equivalence, flip-flop testbench
make test              # + KLayout DRC/LVS, Magic round trip, LibreLane config
```

The regressions need `yosys`, `iverilog`, `klayout`, `magic` and the
`librelane` Python package in `PATH`.

## License

Same as the GT2N repository (BSD 3-Clause, see `../LICENSE`). The
OpenROAD-derived scripts keep their original notices.
