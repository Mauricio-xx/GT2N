// SPDX-License-Identifier: BSD-3-Clause
// Self-checking Icarus testbench for the gt2n_udp_dff_sr based flip-flop
// models. Compile with the Verilog model of one library, e.g.
//   iverilog -DCELL=gt2_6t_dffasync_x1_w31_lvt tb_dffasync.v \
//       ../../libs.ref/gt2_6t_w31_lvt/verilog/gt2_6t_w31_lvt.v
`timescale 1ns/1ps
`ifndef CELL
  `define CELL gt2_6t_dffasync_x1_w31_lvt
`endif
module tb_dffasync;
  reg CLK = 0, D = 0, RESETN = 1, SETN = 1;
  wire Q;
  integer errors = 0;

  `CELL dut (.CLK(CLK), .D(D), .Q(Q), .RESETN(RESETN), .SETN(SETN));

  task expect(input exp, input [8*40-1:0] what);
    begin
      #1;
      if (Q !== exp) begin
        $display("FAIL: %0s: Q=%b expected %b", what, Q, exp);
        errors = errors + 1;
      end
    end
  endtask

  task tick;
    begin CLK = 1; #5; CLK = 0; #5; end
  endtask

  initial begin
    RESETN = 0;              expect(1'b0, "async reset");
    RESETN = 1; D = 1; tick; expect(1'b1, "capture 1");
    D = 0;             tick; expect(1'b0, "capture 0");
    D = 1; #2;               expect(1'b0, "no capture without edge");
    SETN = 0;                expect(1'b1, "async set");
    RESETN = 0;              expect(1'b1, "set dominates reset");
    SETN = 1;                expect(1'b0, "set released while reset held");
    D = 1;             tick; expect(1'b0, "clock ignored during reset");
    RESETN = 1;              expect(1'b0, "reset released, state held");
    tick;                    expect(1'b1, "capture after reset release");
    if (errors == 0) $display("PASS: %m");
    else $display("FAILED with %0d error(s)", errors);
    $finish;
  end
endmodule
