# GT2N KLayout support

Set `KLAYOUT_PATH=$PDK_ROOT/gt2n/libs.tech/klayout` to register the `gt2n`
technology (`tech/gt2n.lyt`, layer properties `tech/gt2n.lyp`, LEF/DEF layer
map `tech/gt2n.map`).

## DRC (`tech/drc/gt2n.lydrc`)

KLayout port of `icv_runset/gt2_main.drc.rs` plus tech-LEF width/spacing
rules for M7..RDL and the backside stack.

```
klayout -b -r tech/drc/gt2n.lydrc -rd input=chip.gds -rd topcell=TOP \
        -rd report=chip.lyrdb -rd drc_mode=route -rd threads=8
```

- `drc_mode=route` (default): routing layers only (what P&R writes).
- `drc_mode=full`: also device/local layers (BPR, ACT, GATE, SDCON, M0, ...),
  with net-aware checks; use for cell work.

Aliases `in_gds`/`report_file`/`top_cell` keep it compatible with
OpenROAD-flow-scripts; LibreLane passes `input`, `topcell`, `report`,
`thr`/`threads` and `KLAYOUT_DRC_DEFINES`.

## LVS (`tech/lvs/gt2n.lylvs`)

```
klayout -b -r tech/lvs/gt2n.lylvs -rd input=cell.gds -rd topcell=CELL \
        -rd schematic=cell.cdl -rd lvs_mode=transistor -rd report=cell.lvsdb
```

- `lvs_mode=transistor`: extracts nanosheet devices (`nmos_<vt>`,
  `pmos_<vt>`); bulk terminals are tied to the cell supplies (`vss`/`vdd`,
  override with `lvs_ground_net`/`lvs_power_net`), floating-gate dummy
  devices are dropped. Works for single cells and for placed-and-routed
  blocks (see `make lvs` in `examples/gt2n-librelane-macro`):
  - same-named supply labels are joined only inside the standard cells
    (`lvs_implicit_cells`, default `gt2_6t_[^f]*`), so a supply open at
    block level is reported;
  - filler instances (`lvs_flatten_cells`, default `gt2_6t_filler*`) are
    merged into the top cell before extraction; the schematic is expected
    without fillers (OpenROAD `write_cdl` without `-include_fillers`);
  - standard cells whose CDL instantiates other cells (`dffasync`) are
    flattened to devices on the schematic side, as their layouts are flat.
- `lvs_mode=abstract` (default): standard cells are black boxes; compares the
  routed connectivity of a placed-and-routed block. Options for full-chip
  runs from OpenROAD-flow-scripts: `def_file`, `signal_only_lvs`.

It prints `INFO : Congratulations! Netlists match.` /
`ERROR : Netlists don't match`, the same messages LibreLane's `KLayout.LVS`
step parses.
