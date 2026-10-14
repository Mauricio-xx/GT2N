# SPDX-License-Identifier: BSD-3-Clause
# KLayout: XOR every cell of $a against the cell of the same name in $b
# (layouts may use different database units). Prints a summary line
#   GT2N_XOR <differences>
a = RBA::Layout.new; a.read($a)
b = RBA::Layout.new; b.read($b)
diffs = 0
a.each_cell do |ca|
  cb = b.cell(ca.name)
  if !cb
    puts "missing in #{$b}: #{ca.name}"
    diffs += 1
    next
  end
  a.layer_indexes.each do |li|
    info = a.get_info(li)
    lb = b.find_layer(info.layer, info.datatype)
    ra = RBA::Region.new(ca.begin_shapes_rec(li))
    rb = lb ? RBA::Region.new(cb.begin_shapes_rec(lb)).transformed(RBA::ICplxTrans.new(b.dbu / a.dbu)) : RBA::Region.new
    x = (ra ^ rb)
    # Degenerate (zero-area) pin shapes are not real differences.
    next if x.area == 0
    diffs += 1
    puts "#{ca.name} #{info}: XOR area #{x.area * a.dbu * a.dbu} um^2"
  end
end
puts "GT2N_XOR #{diffs}"
