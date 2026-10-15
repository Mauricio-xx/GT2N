# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N frontside power delivery network (FSPDN) for OpenROAD pdngen.
#
# Derived from the GT2N AES reference run (pdn_no_bpr_m2m3_rdl_dense.tcl):
#   * no BPR/followpin rails and no full-chip M1 stripes: the cell rails are
#     buried (BPR) and reach the frontside only through the tapfspdn cells,
#     which gt2n_tap_to_m3.tcl hooks up to the M3 stripes below;
#   * alternating VDD/VSS M2/M3 stripes (GT2N_PDN_LOW_PITCH same-net pitch),
#     then a coarser mesh up to GT2N_PDN_TOP_LAYER;
#   * a macro grid that connects the supply pins of hard macros to the
#     adjacent mesh layers, as LibreLane's default PDN does.
#
# pdngen needs room for one VDD/VSS stripe pair per layer: with the default
# pitches the core must be at least about 12.1 um wide and high (M6..M9:
# 6 um offset plus 6 um VDD-VSS spacing plus the stripe), else it stops with
# PDN-0185. Smaller pitches and offsets allow smaller cores.
#
# Knobs (environment, all optional):
#   GT2N_PDN_LOW_PITCH    same-net pitch of the M2/M3 stripes in um   (6.0)
#   GT2N_PDN_LOW_OFFSET   offset of the first M2/M3 stripe in um      (3.0)
#   GT2N_PDN_MID_PITCH    same-net pitch of the M4/M5 stripes in um   (8.0)
#   GT2N_PDN_MID_OFFSET   offset of the first M4/M5 stripe in um      (4.0)
#   GT2N_PDN_HIGH_PITCH   same-net pitch of the M6..M9 stripes in um  (12.0)
#   GT2N_PDN_HIGH_OFFSET  offset of the first M6..M9 stripe in um     (6.0)
#   GT2N_PDN_TOP_LAYER   last mesh layer: M5, M9, M11, M13 or RDL  (RDL)
#   GT2N_PDN_EXTEND_TO_BOUNDARY  1 = M3 and top stripes reach the die edge (1)
#   PDN_HORIZONTAL_HALO, PDN_VERTICAL_HALO  macro halo in um (LibreLane, 10)
#   PDN_MACRO_CONNECTIONS  extra macro supply connections (LibreLane syntax)
# Used by gt2n_pdn_cfg.tcl (LibreLane) and by the OpenROAD-flow-scripts
# platform in ../openroad (whose pre_io_avoid_pdn_stripes.tcl reads the same
# LOW_* knobs to keep IO pins off the M2/M3 stripes).

proc gt2n_pdn_env {name default} {
  if {[info exists ::env($name)] && $::env($name) ne ""} { return $::env($name) }
  return $default
}

set low_pitch   [gt2n_pdn_env GT2N_PDN_LOW_PITCH 6.0]
set low_offset  [gt2n_pdn_env GT2N_PDN_LOW_OFFSET 3.0]
set mid_pitch   [gt2n_pdn_env GT2N_PDN_MID_PITCH 8.0]
set mid_offset  [gt2n_pdn_env GT2N_PDN_MID_OFFSET 4.0]
set high_pitch  [gt2n_pdn_env GT2N_PDN_HIGH_PITCH 12.0]
set high_offset [gt2n_pdn_env GT2N_PDN_HIGH_OFFSET 6.0]
set top_layer   [gt2n_pdn_env GT2N_PDN_TOP_LAYER RDL]
set extend      [gt2n_pdn_env GT2N_PDN_EXTEND_TO_BOUNDARY 1]
# Halo around hard macros kept free of core-grid stripes; gt2n_tap_to_m3.tcl
# keeps its hookup shapes out of it as well.
set ::gt2n_pdn_macro_halo [list [gt2n_pdn_env PDN_HORIZONTAL_HALO 10] [gt2n_pdn_env PDN_VERTICAL_HALO 10]]

# layer width pitch offset (um). M3..M6 use exactly the via cut sizes: the
# self-aligned via rules (V3.3..V5.4) require the V3/V4/V5 cut edges to
# coincide with the metal edges. Upper layers use conservative widths
# relative to the tech LEF minimums (M10/M11 0.056, M12/M13 0.36, RDL 1.6).
set mesh [list \
  [list M2  0.012 $low_pitch $low_offset] \
  [list M3  0.014 $low_pitch $low_offset] \
  [list M4  0.021 $mid_pitch $mid_offset] \
  [list M5  0.021 $mid_pitch $mid_offset] \
  [list M6  0.038 $high_pitch $high_offset] \
  [list M7  0.076 $high_pitch $high_offset] \
  [list M8  0.076 $high_pitch $high_offset] \
  [list M9  0.076 $high_pitch $high_offset] \
  [list M10 0.224 8.0  4.0] \
  [list M11 0.224 8.0  4.0] \
  [list M12 0.720 12.0 6.0] \
  [list M13 0.720 12.0 6.0] \
  [list RDL 1.600 12.8 0.8] \
]

set layers {}
foreach entry $mesh {
  lappend layers [lindex $entry 0]
  if {[lindex $entry 0] eq $top_layer} { break }
}
if {[lindex $layers end] ne $top_layer} {
  error "GT2N_PDN_TOP_LAYER=$top_layer is not one of M5..M13 or RDL"
}

####################################
# global connections
####################################
add_global_connection -net {VDD} -inst_pattern {.*} -pin_pattern {^(vdd|VDD|VPWR)$} -power
add_global_connection -net {VSS} -inst_pattern {.*} -pin_pattern {^(vss|VSS|VGND)$} -ground
# In LibreLane, also apply PDN_MACRO_CONNECTIONS and the SCL supply pins with
# LibreLane's own procedure (as its default PDN script does).
if {[llength [info procs set_global_connections]] == 0 && [info exists ::env(SCRIPTS_DIR)]} {
  set gt2n_pdn_gc [file join $::env(SCRIPTS_DIR) openroad common set_global_connections.tcl]
  if {[file exists $gt2n_pdn_gc]} { source $gt2n_pdn_gc }
}
if {[llength [info procs set_global_connections]] && [info exists ::env(PDN_CONNECT_MACROS_TO_GRID)]} {
  set_global_connections
} else {
  global_connect
}

####################################
# voltage domain and core grid
####################################
set_voltage_domain -name {CORE} -power {VDD} -ground {VSS}
define_pdn_grid -name {grid} -voltage_domains {CORE} -pins [list $top_layer]

foreach entry $mesh {
  lassign $entry layer width pitch offset
  if {[lsearch -exact $layers $layer] < 0} { break }
  set extra {}
  # As in the AES reference run, the M3 and top stripes reach the die edge.
  if {$extend && ($layer eq "M3" || $layer eq $top_layer)} { set extra {-extend_to_boundary} }
  add_pdn_stripe -grid {grid} -layer $layer -width $width -pitch $pitch -offset $offset {*}$extra
}

for {set i 0} {$i < [llength $layers] - 1} {incr i} {
  add_pdn_connect -grid {grid} -layers [list [lindex $layers $i] [lindex $layers [expr {$i + 1}]]]
}

####################################
# hard macros: connect their supply pins on any mesh layer to the core-grid
# stripes of the layers above and below
####################################
define_pdn_grid -macro -default -name {macro} -voltage_domains {CORE} -halo $::gt2n_pdn_macro_halo
for {set i 0} {$i < [llength $layers] - 1} {incr i} {
  add_pdn_connect -grid {macro} -layers [list [lindex $layers $i] [lindex $layers [expr {$i + 1}]]]
}
