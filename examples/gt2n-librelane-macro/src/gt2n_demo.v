// SPDX-License-Identifier: BSD-3-Clause
//
// GT2N LibreLane macro example: a small datapath with
//   * a 16-bit Fibonacci LFSR (x^16 + x^14 + x^13 + x^11 + 1),
//   * an 8-bit accumulator that adds `din` when `en` is high,
//   * a registered XOR of both, driven on `dout`.
// Replace this module with your own design; keep the top-level name in sync
// with DESIGN_NAME in librelane/config.yaml.

`default_nettype none

module gt2n_demo (
    input  wire        clk,
    input  wire        rst_n,   // active-low synchronous reset
    input  wire        en,
    input  wire [7:0]  din,
    output reg  [7:0]  dout,
    output wire [15:0] lfsr
);

    reg [15:0] lfsr_q;
    reg [7:0]  acc_q;

    wire feedback = lfsr_q[15] ^ lfsr_q[13] ^ lfsr_q[12] ^ lfsr_q[10];

    always @(posedge clk) begin
        if (!rst_n) begin
            lfsr_q <= 16'hACE1;
            acc_q  <= 8'd0;
            dout   <= 8'd0;
        end else begin
            lfsr_q <= {lfsr_q[14:0], feedback};
            if (en)
                acc_q <= acc_q + din;
            dout <= acc_q ^ lfsr_q[7:0];
        end
    end

    assign lfsr = lfsr_q;

endmodule

`default_nettype wire
