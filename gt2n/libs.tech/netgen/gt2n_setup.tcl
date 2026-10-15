# SPDX-License-Identifier: BSD-3-Clause
#---------------------------------------------------------------
# Netgen LVS setup for the GT2N 2 nm nanosheet PDK
#
# Devices: nmos_<vt> / pmos_<vt> with vt in elvt ulvt lvt svt hvt sramvt
# (4 terminals d g s b, properties w l [m]). The physical-only standard
# cells, which have supply pins only, are ignored: filler and tap cells
# carry no devices, the decap (decapcc, a cross-coupled supply-only decap)
# has one nmos and one pmos.
#---------------------------------------------------------------
permute default
property default
property parallel none

catch {format $env(NETGEN_COLUMNS)}

set cells1 [cells list -all -circuit1]
set cells2 [cells list -all -circuit2]

#-------------------------------------------
# Nanosheet transistors
#-------------------------------------------
set devices {}
foreach vt {elvt ulvt lvt svt hvt sramvt} {
    lappend devices nmos_$vt
    lappend devices pmos_$vt
}

foreach dev $devices {
    foreach circuit {1 2} {
        set cells [set cells$circuit]
        if {[lsearch $cells $dev] < 0} { continue }
        set c "-circuit$circuit $dev"
        # Source and drain are interchangeable.
        permute $c 1 3
        property $c parallel enable
        property $c parallel {l critical}
        property $c parallel {w add}
        property $c tolerance {l 0.01} {w 0.01}
        # Junction geometry and layout-only parameters are not compared.
        property $c delete as ad ps pd nrs nrd sa sb sd mult
    }
}

#-------------------------------------------
# Physical-only standard cells
#-------------------------------------------
foreach circuit {1 2} {
    foreach cell [set cells$circuit] {
        if {[regexp {^gt2_6t_(filler|tapfspdn|tapbspdn|decapcc)_} $cell]} {
            ignore class "-circuit$circuit $cell"
        }
    }
}
