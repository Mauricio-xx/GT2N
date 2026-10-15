# SPDX-License-Identifier: BSD-3-Clause
# KLayout: compare every cell of $a with the cell of the same name in $b
# (layouts may use different database units): XOR of the shapes and equality
# of the texts on every layer/datatype of either layout. A text is compared
# by its string and the shape of $a it lies on (Magic moves a pin text to the
# centre of its pin shape), or its position if it lies on none. Cells of $b
# that are not in $a are reported too, except the names in $extra (comma
# separated, e.g. a wrapper top cell). Prints a summary line
#   GT2N_XOR <differences>
a = RBA::Layout.new; a.read($a)
b = RBA::Layout.new; b.read($b)
extra = ($extra || "").split(",")
to_a = RBA::ICplxTrans.new(b.dbu / a.dbu)
layers = [a, b].flat_map { |l| l.layer_indexes.map { |li| l.get_info(li) } }
layers = layers.map { |i| [i.layer, i.datatype] }.uniq.sort

def texts(cell, li, trans, shapes)
  return [] unless li
  RBA::Texts.new(cell.begin_shapes_rec(li)).transformed(trans).each.map do |t|
    pt = RBA::Point.new(t.x, t.y)
    on = shapes.find { |poly| poly.inside?(pt) }
    [t.string, on ? on.to_s : pt.to_s]
  end.uniq.sort
end

diffs = 0
b.each_cell do |cb|
  next if a.cell(cb.name) || extra.include?(cb.name)
  puts "missing in #{$a}: #{cb.name}"
  diffs += 1
end
a.each_cell do |ca|
  cb = b.cell(ca.name)
  if !cb
    puts "missing in #{$b}: #{ca.name}"
    diffs += 1
    next
  end
  layers.each do |layer, datatype|
    la = a.find_layer(layer, datatype)
    lb = b.find_layer(layer, datatype)
    ra = la ? RBA::Region.new(ca.begin_shapes_rec(la)) : RBA::Region.new
    rb = lb ? RBA::Region.new(cb.begin_shapes_rec(lb)).transformed(to_a) : RBA::Region.new
    x = (ra ^ rb)
    # Degenerate (zero-area) pin shapes are not real differences.
    if x.area != 0
      diffs += 1
      puts "#{ca.name} #{layer}/#{datatype}: XOR area #{x.area * a.dbu * a.dbu} um^2"
    end
    shapes = ra.merged.each.to_a
    ta = texts(ca, la, RBA::ICplxTrans.new, shapes)
    tb = texts(cb, lb, to_a, shapes)
    next if ta == tb
    diffs += 1
    puts "#{ca.name} #{layer}/#{datatype}: texts only in a #{(ta - tb).first(3)}, only in b #{(tb - ta).first(3)} (#{(ta - tb).size}/#{(tb - ta).size})"
  end
end
puts "GT2N_XOR #{diffs}"
