module and_test(a,b,c);
input a;
input b;
output c;

and_gate and_gate(a,b,c);

initial begin
	$dumpfile("and.vcd");
	$dumpvars;
end

endmodule 