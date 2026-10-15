// SPDX-License-Identifier: BSD-3-Clause
// Self-checking testbench for the flip-flop models. Compile with the Verilog
// model of one library, e.g.
//   iverilog -DCELL=gt2_6t_dffasync_x1_w31_lvt tb_dffasync.v \
//       ../../libs.ref/gt2_6t_w31_lvt/verilog/gt2_6t_w31_lvt.v
// and again with -DGT2N_NO_UDP for the behavioural model that Verilator
// uses. The X checks apply to the gt2n_udp_dff_sr model only.
`timescale 1ns/1ps
`ifndef CELL
  `define CELL gt2_6t_dffasync_x1_w31_lvt
`endif
module tb_dffasync;
  reg CLK = 0, D = 0, RESETN = 1, SETN = 1;
  wire Q;
  integer errors = 0;

  `CELL dut (.CLK(CLK), .D(D), .Q(Q), .RESETN(RESETN), .SETN(SETN));

  task check(input exp, input [8*40-1:0] what);
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
    RESETN = 0;              check(1'b0, "async reset");
    RESETN = 1; D = 1; tick; check(1'b1, "capture 1");
    D = 0;             tick; check(1'b0, "capture 0");
    D = 1; #2;               check(1'b0, "no capture without edge");
    SETN = 0;                check(1'b1, "async set");
    RESETN = 0;              check(1'b1, "set dominates reset");
    SETN = 1;                check(1'b0, "set released while reset held");
    D = 1;             tick; check(1'b0, "clock ignored during reset");
    RESETN = 1;              check(1'b0, "reset released, state held");
    tick;                    check(1'b1, "capture after reset release");
`ifndef GT2N_NO_UDP
`ifndef VERILATOR
    D = 0;             tick; check(1'b0, "capture 0 before X checks");
    RESETN = 1'bx;           check(1'b0, "RESETN=x while Q=0");
    D = 1;             tick; check(1'bx, "clock D=1 with RESETN=x, Q=0");
                       tick; check(1'bx, "clock D=1 with RESETN=x, Q=x");
    D = 0;             tick; check(1'b0, "clock D=0 with RESETN=x");
    RESETN = 1; D = 1; tick; check(1'b1, "capture 1 after RESETN=x");
    SETN = 1'bx;             check(1'b1, "SETN=x while Q=1");
    D = 0;             tick; check(1'bx, "clock D=0 with SETN=x, Q=1");
                       tick; check(1'bx, "clock D=0 with SETN=x, Q=x");
    D = 1;             tick; check(1'b1, "clock D=1 with SETN=x");
    SETN = 0; RESETN = 1'bx; check(1'b1, "set dominates RESETN=x");
    SETN = 1;                check(1'bx, "set released while RESETN=x");
    RESETN = 0;              check(1'b0, "reset after RESETN=x");
    RESETN = 1;              check(1'b0, "reset released after X checks");
`endif
`endif
    if (errors == 0) $display("PASS: %m");
    else $display("FAILED with %0d error(s)", errors);
    $finish;
  end
endmodule
