# SPDX-License-Identifier: BSD-3-Clause
# Connectivity and abstract-view checks of the GT2N Magic technology. Writes
# the .ext / .lef results into the current directory; run_connect.py runs it
# with
#   magic -dnull -noconsole -rcfile $PDK_ROOT/gt2n/libs.tech/magic/gt2n.magicrc connect.tcl
# and checks them.
drc off
crashbackups disable
locking disable

# Cuts and the two conductors each one joins.
set cuts {
    vbpr {bpr sdcon} vsd {sdcon m0} vg {gate m0} v0 {m0 m1} v1 {m1 m2}
    v2 {m2 m3} v3 {m3 m4} v4 {m4 m5} v5 {m5 m6} v6 {m6 m7} v7 {m7 m8}
    v8 {m8 m9} v9 {m9 m10} v10 {m10 m11} v11 {m11 m12} v12 {m12 m13}
    v13 {m13 rdl}
}

# abut_<a>_<b>: cuts a and b side by side, touching on the conductor they
# share and with no plain conductor between them (as the router places e.g.
# V1_0 next to V2_0). The outer conductors carry the labels A and B; the cell
# must extract as one node.
set names [dict keys $cuts]
for {set i 0} {$i < [llength $names]} {incr i} {
    for {set j [expr {$i + 1}]} {$j < [llength $names]} {incr j} {
        set a [lindex $names $i]
        set b [lindex $names $j]
        set la [dict get $cuts $a]
        set lb [dict get $cuts $b]
        set shared {}
        foreach l $la { if {$l in $lb} { set shared $l } }
        if {$shared eq {}} { continue }
        set oa [lindex [lsearch -all -inline -not -exact $la $shared] 0]
        set ob [lindex [lsearch -all -inline -not -exact $lb $shared] 0]
        load abut_${a}_${b}
        box 0 0 40 40
        paint $a
        box 40 0 80 40
        paint $b
        box -100 0 0 40
        paint $oa
        label A c $oa
        box 80 0 180 40
        paint $ob
        label B c $ob
        extract all
    }
}

# open_m1_m2: crossing M1 and M2 without a cut must stay two nodes.
load open_m1_m2
box 0 0 200 40
paint m1
label A c m1
box 80 -100 120 140
paint m2
label B c m2
extract all

# gate_cut: a GATE line cut by GCUT and, further on, covered by DUMMY, written
# to GDS and read back. The three gate pieces A, B and C must be three nodes.
load gate_cut_src
box 0 0 600 20
paint gate
box 50 0 50 20
label A c gate
box 250 0 250 20
label B c gate
box 550 0 550 20
label C c gate
box 180 -40 220 60
paint gcut
box 380 -40 420 60
paint dummy
gds write gate_cut.gds
cellname rename gate_cut_src gate_cut_painted
gds read gate_cut.gds
load gate_cut_src
extract all

# lef_obs: routing on BPR and M0..M3 plus one M2 pin. The abstract view
# ('lef write -hide', as LibreLane's Magic.WriteLEF) must obstruct every one
# of these layers.
load lef_obs
foreach {t x} {bpr 0 m0 100 m1 200 m2 300 m3 400} {
    box $x 200 [expr {$x + 40}] 1800
    paint $t
}
box 1000 0 1040 40
paint m2
label P c m2
port make
box 0 0 2000 2000
property FIXED_BBOX [box values]
lef write lef_obs.lef -hide

# lef_pin_obs: an abstract whose M2 obstruction overlaps its M2 pin (as
# OpenROAD write_abstract_lef writes them). The pin must keep its metal (one
# node), and a parent M2 wire landing on it must connect without an illegal
# overlap (LibreLane Checker.IllegalOverlap counts these).
set f [open lef_pin_obs.lef w]
puts $f "VERSION 5.7 ;
MACRO lef_pin_obs
  CLASS BLOCK ;
  FOREIGN lef_pin_obs 0 0 ;
  ORIGIN 0 0 ;
  SIZE 1 BY 1 ;
  PIN P
    DIRECTION INPUT ;
    USE SIGNAL ;
    PORT
      LAYER M2 ;
        RECT 0 0.5 0.024 0.512 ;
    END
  END P
  OBS
    LAYER M2 ;
      RECT 0.007 0.5 0.9 0.512 ;
  END
END lef_pin_obs
END LIBRARY"
close $f
lef read lef_pin_obs.lef
load lef_pin_obs_top
box 0 0 0 0
getcell lef_pin_obs
box -400 1000 48 1024
paint m2
label W c m2
feedback clear
extract all
set f [open lef_pin_obs.feedback w]
puts $f [feedback count]
close $f

# lef_cut_obs: an abstract with an OBS on V1 where its M1 pin A crosses its M2
# pin B. A cut-layer obstruction is not a cut: A and B must stay two nodes.
set f [open lef_cut_obs.lef w]
puts $f "VERSION 5.7 ;
MACRO lef_cut_obs
  CLASS BLOCK ;
  FOREIGN lef_cut_obs 0 0 ;
  ORIGIN 0 0 ;
  SIZE 1 BY 1 ;
  PIN A
    DIRECTION INPUT ;
    USE SIGNAL ;
    PORT
      LAYER M1 ;
        RECT 0.4 0 0.414 1 ;
    END
  END A
  PIN B
    DIRECTION INPUT ;
    USE SIGNAL ;
    PORT
      LAYER M2 ;
        RECT 0 0.5 1 0.512 ;
    END
  END B
  OBS
    LAYER V1 ;
      RECT 0.401 0.5 0.413 0.512 ;
  END
END lef_cut_obs
END LIBRARY"
close $f
lef read lef_cut_obs.lef
load lef_cut_obs
extract all

quit -noprompt
