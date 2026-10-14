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
make sim                           # RTL simulation
make sim-gl                        # gate-level simulation of final/nl
```

## What is GT2N-specific

- **Buried power rails.** The cell rails are BPR, a layer the router cannot
  use (`gt2_fspdn_tech.lef` declares it MASTERSLICE). They reach the
  frontside only through the `gt2_6t_tapfspdn_*` tap cells. The PDK's
  `PDN_CFG` (`gt2n/libs.tech/librelane/gt2n_pdn_cfg.tcl`) builds an M2..M9
  mesh and then ties every tap pin to the M3 stripes.
- **Units.** The GT2N Liberty files use ps/ohm. `gt2n_base.sdc` switches the
  SDC command units to the ns/kOhm values LibreLane passes (`CLOCK_PERIOD`
  is in ns, as usual).
- **LVS.** The GT2N Magic technology is layout level (no nanosheet device
  extraction), so `Magic.SpiceExtraction`/`Netgen.LVS` are disabled in
  `config.yaml`. Transistor-level LVS uses the KLayout deck of the PDK,
  `gt2n/libs.tech/klayout/tech/lvs/gt2n.lylvs`.

## Status

Results of `make librelane` (`gt2_6t_w31_svt`, 30 x 30 um die, 1 GHz clock):

| Check | Result |
| --- | --- |
| Detailed routing (TritonRoute) | 0 violations |
| KLayout DRC (`gt2n.lydrc`, route mode) | 0 errors |
| Magic DRC | 0 errors |
| Magic vs KLayout stream-out XOR | 0 differences |
| Antenna | 0 violating nets |
| Setup / hold (tt 0.7 V 25 C) | met (setup WNS +0.48 ns) |
| Max slew / max cap | 0 violations |

438 logic and clock cells (32 flip-flops) plus filler and tap cells; the
whole flow runs in about three minutes.

- RTL and gate-level simulation (Icarus + cocotb) pass against the Python
  reference model.
- The LibreLane configuration loads for all ten libraries
  (`gt2n/libs.qa/librelane/check_config.py`).
- OpenROAD PSM reports every standard cell as unconnected because the cell
  supply pins are on BPR, which it cannot trace; `ERROR_ON_PDN_VIOLATIONS` is
  off for that reason (see `config.yaml`).
