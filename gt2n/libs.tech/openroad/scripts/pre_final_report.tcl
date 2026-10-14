# SPDX-License-Identifier: BSD-3-Clause
#
# GT2N PRE_FINAL_REPORT_TCL hook.
#
# 1. Clears stale PDNSim/PSM markers from the ODB so that VDD/VSS reports of
#    earlier checks are not carried into the final report (no geometry change).
# 2. Applies a vectorless switching activity (scripts/power_activity_vectorless
#    .tcl) so report_power gives a non-zero switching component when no
#    SAIF/VCD is available. Set GT2N_POWER_ACTIVITY=0 to skip.

set block [ord::get_db_block]
set cat [$block findMarkerCategory PSM]
if {$cat != "NULL" && $cat != ""} {
  puts "GT2N: clearing stale PSM marker category ([$cat getMarkerCount] markers)"
  ::odb::dbMarkerCategory_destroy $cat
}
foreach net {VDD VSS} {
  file delete -force [file join $::env(REPORTS_DIR) ${net}.rpt]
  file delete -force [file join $::env(REPORTS_DIR) ${net}_check.rpt]
}

if {![info exists ::env(GT2N_POWER_ACTIVITY)] || $::env(GT2N_POWER_ACTIVITY) ne "0"} {
  source [file join [file dirname [info script]] power_activity_vectorless.tcl]
}
