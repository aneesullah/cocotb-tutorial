module or_gate(
	input wire a,
	input wire b,
	output wire y
);
//OR gate at dataflow-level
assign y=a|b;
endmodule
