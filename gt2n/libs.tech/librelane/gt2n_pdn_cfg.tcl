# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N power grid for LibreLane (PDN_CFG).
#
# Builds the frontside PDN of gt2n_pdn_fspdn.tcl and, once LibreLane's
# pdn.tcl has run pdngen, connects the tapfspdn cell M1 pins to the M3
# stripes with gt2n_tap_to_m3.tcl (the cell rails are buried power rails
# the router cannot reach).
#
# Use in a design configuration:
#     PDN_CFG: pdk_dir::libs.tech/librelane/gt2n_pdn_cfg.tcl

set ::gt2n_librelane_dir [file normalize [file join $::env(PDK_ROOT) $::env(PDK) libs.tech librelane]]

# IO pins sit on the die edge; keep the M3 stripes inside the core so they
# cannot short with them (LibreLane has no pre-IO-placement hook).
if {![info exists ::env(GT2N_PDN_EXTEND_TO_BOUNDARY)]} {
    set ::env(GT2N_PDN_EXTEND_TO_BOUNDARY) 0
}
if {![info exists ::env(GT2N_PDN_TOP_LAYER)]} {
    set ::env(GT2N_PDN_TOP_LAYER) M9
}
source [file join $::gt2n_librelane_dir gt2n_pdn_fspdn.tcl]

# LibreLane calls pdngen right after sourcing this file: run the tap hookup
# right after it.
if {[llength [info commands gt2n_real_pdngen]] == 0} {
    rename pdngen gt2n_real_pdngen
}
proc pdngen {args} {
    gt2n_real_pdngen {*}$args
    if {![info exists ::env(REPORTS_DIR)]} {
        set ::env(REPORTS_DIR) $::env(STEP_DIR)
    }
    source [file join $::gt2n_librelane_dir gt2n_tap_to_m3.tcl]
}
