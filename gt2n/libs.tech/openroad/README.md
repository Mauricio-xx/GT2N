# GT2N OpenROAD-flow-scripts platform (experimental)

> **Status: experimental, not validated.** The supported digital flow for
> GT2N is LibreLane (`../librelane`). This platform is kept as an option for
> OpenROAD-flow-scripts (ORFS) users.

It is derived from the GT2N ORFS example (`Openroad_example/` at the
repository root) and generalised: library flavour selection, collateral taken
from `../../libs.ref`, KLayout decks from `../klayout/tech`, and the PDN/tap
scripts shared with LibreLane (`../librelane/gt2n_pdn_fspdn.tcl`,
`../librelane/gt2n_tap_to_m3.tcl`).

```make
export PLATFORM     = gt2n
export PLATFORM_DIR = $(PDK_ROOT)/gt2n/libs.tech/openroad
export GT2N_WIDTH   = w31        # w13 | w31
export GT2N_VT      = svt        # elvt | ulvt | lvt | svt | hvt
export GT2N_EXTRA_VTS = lvt      # optional multi-VT
export GT2N_PDN     = fspdn      # fspdn | bspdn (backside proxy, see below)
```

`GT2N_PDN=bspdn` routes without a PDN in OpenROAD and adds the backside grid
to the streamed GDS with `scripts/add_bspdn_signoff_grid.rb` (KLayout), as in
the GT2N AES example.

Unlike the IHP platform this directory is not shipped with ORFS: point
`PLATFORM_DIR` at it (or symlink it as `flow/platforms/gt2n`).
