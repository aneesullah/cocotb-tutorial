import cocotb
from cocotb.triggers import Timer, RisingEdge, ReadOnly, NextTimeStep, FallingEdge
from cocotb_bus.drivers import BusDriver
from cocotb_coverage.coverage import CoverCross, CoverPoint, coverage_db
from cocotb_bus.monitors import BusMonitor
import os
import random


def sb_fn(actual_value): #defination of the call back function 
    global expected_value
    assert actual_value == expected_value.pop(0), "Scoreboard Matching Failed"

#unit-level coverage points
@CoverPoint("top.a",  # noqa F405
            xf=lambda x, y: x,
            bins=[0, 1]
            )
@CoverPoint("top.b",  # noqa F405
            xf=lambda x, y: y,
            bins=[0, 1]
            )
@CoverCross("top.cross.ab",
            items=["top.a",
                   "top.b"
                   ]
            )
def ab_cover(a, b):#dummy function doing nothing 
    pass

#protocol-level coverage cover points 
@CoverPoint("top.prot.a.current",  # noqa F405
            xf=lambda x: x['current'],
            bins=['Idle', 'Rdy', 'Txn'],
            )
@CoverPoint("top.prot.a.previous",  # noqa F405
            xf=lambda x: x['previous'],
            bins=['Idle', 'Rdy', 'Txn'],
            )
@CoverCross("top.cross.a_prot.cross",
            items=["top.prot.a.previous",
                   "top.prot.a.current" 
                   ],
            ign_bins=[('Rdy', 'Idle')] #adding waiver for the cross-coverage 
            )

def a_prot_cover(txn):
    pass


@cocotb.test()
async def ifc_test(dut):
    global expected_value
    expected_value = []
    dut.RST_N.value = 1 #handle async reset on both pos and neg edge 
    await Timer(1, 'ns')
    dut.RST_N.value = 0 #handle async reset on both pos and neg edge
    await Timer(1, 'ns')
    await RisingEdge(dut.CLK)
    dut.RST_N.value = 1
    adrv = InputDriver(dut, 'a', dut.CLK) #instantiate the input drivers 
    IO_Monitor(dut, 'a', dut.CLK, callback=a_prot_cover) #putting monitor 
    bdrv = InputDriver(dut, 'b', dut.CLK) #instantiate the input driver 
    OutputDriver(dut, 'y', dut.CLK, sb_fn) #instantiate the output driver , sb_fn is callback function defined above 

    for i in range(20): #here we apply the input vectors 
        a = random.randint(0, 1) #randomize to get coverage of remaining cover points 
        b = random.randint(0, 1)
        expected_value.append(a | b) #golden model generation 
        adrv.append(a)
        bdrv.append(b)
        ab_cover(a, b) #invoke the cross-coverage
    while len(expected_value) > 0: #wait until all the elemented are applied 
        await Timer(2, 'ns')

    coverage_db.report_coverage(cocotb.log.info, bins=True)#generate coverage report 
    coverage_file = os.path.join(
        os.getenv('RESULT_PATH', "./"), 'coverage.xml')
    coverage_db.export_to_xml(filename=coverage_file) #generates coverage report 


class InputDriver(BusDriver):#our input driver derivation from the bus class , Remeber QUEUE, Signals (Prefixing of it),Driver 
    _signals = ['rdy', 'en', 'data'] #our signals names 

    def __init__(self, dut, name, clk):#initialization function 
        BusDriver.__init__(self, dut, name, clk)
        self.bus.en.value = 0
        self.clk = clk

    async def _driver_send(self, value, sync=True):#this method is provided by the BusDriver to pick up the data from the queue output
        for i in range(random.randint(0, 20)): #still required to cover the remaining cover point
            await RisingEdge(self.clk)
        if self.bus.rdy.value != 1: #rdy is on the input (producer) side, en is on the output (consumer) side 
            await RisingEdge(self.bus.rdy)
        self.bus.en.value = 1
        self.bus.data.value = value
        await ReadOnly() #wait of delta dely cycle when multiple always are running 
        await RisingEdge(self.clk)
        self.bus.en.value = 0
        await NextTimeStep()# wait for time step before we go and sample the ready signal again  


class IO_Monitor(BusMonitor): #protocol-level coverage 
    _signals = ['rdy', 'en', 'data'] #same signals as inputdriver

    async def _monitor_recv(self):
        fallingedge = FallingEdge(self.clock)
        rdonly = ReadOnly()
        phases = { #transaction phases 
            0: 'Idle',
            1: 'Rdy',
            3: 'Txn' #2 is not a valid case, En=1, RDY=0 
        }
        prev = 'Idle'
        while True:
            await fallingedge
            await rdonly
            txn = (self.bus.en.value << 1) | self.bus.rdy.value
            self._recv({'previous': prev, 'current': phases[txn]})
            prev = phases[txn]


class OutputDriver(BusDriver):#Can be derived from the BusDriver or the InputDriver from above
    _signals = ['rdy', 'en', 'data']

    def __init__(self, dut, name, clk, sb_callback):
        BusDriver.__init__(self, dut, name, clk)
        self.bus.en.value = 0
        self.clk = clk
        self.callback = sb_callback
        self.append(0) # we don't use append, only on the input side 

    async def _driver_send(self, value, sync=True):
        while True: #never exit this routing 
            for i in range(random.randint(0, 20)): #required to cover the missing cases 
                await RisingEdge(self.clk)
            if self.bus.rdy.value != 1:
                await RisingEdge(self.bus.rdy)
            self.bus.en.value = 1
            await ReadOnly()
            self.callback(self.bus.data.value)#whatever we get send it out
            await RisingEdge(self.clk)
            await NextTimeStep()
            self.bus.en.value = 0
