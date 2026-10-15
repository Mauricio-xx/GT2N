# GT2N KLayout support

Set `KLAYOUT_PATH=$PDK_ROOT/gt2n/libs.tech/klayout` to register the `gt2n`
technology (`tech/gt2n.lyt`, layer properties `tech/gt2n.lyp`, LEF/DEF layer
map `tech/gt2n.map`).

## DRC (`tech/drc/gt2n.lydrc`)

KLayout port of `icv_runset/gt2_main.drc.rs` plus tech-LEF rules for M7..RDL
and the backside stack (minimum width in every direction, euclidian spacing,
V6..V8 enclosure, via coverage) and a 0.5 nm manufacturing-grid check
(`GRID.1`).

```
klayout -b -r tech/drc/gt2n.lydrc -rd input=chip.gds -rd topcell=TOP \
        -rd report=chip.lyrdb -rd drc_mode=route -rd threads=8
```

- `drc_mode=route` (default): routing layers only (what P&R writes).
- `drc_mode=full`: also device/local layers (BPR, ACT, GATE, SDCON, M0, ...),
  with net-aware checks; use for cell work. It also runs on placed blocks
  (the example macro: about 2 min, 1 GB).
- `run_mode_gt2n` is an alias of `drc_mode`; an unknown mode is an error.

Aliases `in_gds`/`report_file`/`top_cell` keep it compatible with
OpenROAD-flow-scripts; LibreLane passes `input`, `topcell`, `report`,
`threads` and the entries of `KLAYOUT_DRC_OPTIONS` (the PDK sets
`drc_mode=route`).

`make -C gt2n test-drc-rules` checks the deck against known-bad and
known-good patterns for its rules (`libs.qa/drc`), in route and full mode.

## LVS (`tech/lvs/gt2n.lylvs`)

```
klayout -b -r tech/lvs/gt2n.lylvs -rd input=cell.gds -rd topcell=CELL \
        -rd schematic=cell.cdl -rd lvs_mode=transistor -rd report=cell.lvsdb
```

- `lvs_mode=transistor`: extracts nanosheet devices (`nmos_<vt>`,
  `pmos_<vt>`) as 3-terminal MOS. As in the ICV runset, the bulk is not
  compared, and the 4-terminal CDL MOS elements are read the same way. W and
  L are compared exactly. Floating-gate dummy devices are dropped. Works for
  single cells and for placed-and-routed blocks (see `make lvs` in
  `examples/gt2n-librelane-macro`):
  - supply nets come only from the drawn rails, vias and labels (cell labels
    `vdd`/`vss`, override with `lvs_power_net`/`lvs_ground_net`), so a cell
    whose rails do not reach the labelled VDD/VSS is reported. After the
    compare, every top-level supply net of the schematic must also pair with
    a layout net labelled as the same supply (`ERROR : Supply net mismatch
    ...`);
  - same-named supply labels are joined only inside the double-height cells
    with two vss rails (`lvs_implicit_cells`, default
    `gt2_6t_dffasync*,gt2_6t_mux2*`); a block that leaves one of their rails
    unconnected fails (`Split supply rails not connected`);
  - device-less cells (filler, tap cells) have empty CDL subcircuits; run
    alone, they get a supply check instead (vdd and vss each one net, not
    shorted);
  - filler instances (`lvs_flatten_cells`, default `gt2_6t_filler*`) are
    merged into the top cell before extraction. OpenROAD `write_cdl` writes
    the fillers too (their LEF class is CORE, not CORE SPACER), and the empty
    filler subcircuit is flattened away on the schematic side;
  - standard cells whose CDL instantiates other cells (`dffasync`) are
    flattened to devices on the schematic side, as their layouts are flat.
- `lvs_mode=abstract` (default): standard cells are black boxes; compares the
  routed connectivity of a placed-and-routed block, including filler and tap
  instances (the schematic lists them, as `write_cdl` does), with the same
  supply checks. Options for full-chip runs from OpenROAD-flow-scripts:
  `def_file`, `signal_only_lvs`.

It prints `INFO : Congratulations! Netlists match.` /
`ERROR : Netlists don't match`, the same messages LibreLane's `KLayout.LVS`
step parses. Supply errors are printed as `ERROR : ...` lines, added to the
report (category `GT2N_SUPPLY`) and turn the verdict into `ERROR : Netlists
don't match`. `make -C gt2n test-lvs-cases` (`libs.qa/lvs`) runs positive and
negative cases (broken tap, floating rails, shorted supplies, W/L off by
1 nm).
