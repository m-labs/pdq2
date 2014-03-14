# Robert Jordens <jordens@gmail.com> 2013

from migen.fhdl.std import *
from migen.genlib.record import Record
from migen.flow.actor import *

from dac import Dac
from comm import Comm


class Soc(Module):
    def __init__(self, platform, fast=True, silence=False):
        self.clock_domains.cd_sys = ClockDomain()
        clk_p = self.cd_sys.clk
        clk_n = Signal()

        dacs = []
        for i, mem in enumerate((1<<13, 1<<13, 1<<12)):
        #for i, mem in enumerate((1<<13, (1<<12)+(1<<11), (1<<12)+(1<<11))):
            dac = Dac(mem_depth=mem)
            setattr(self.submodules, "dac{}".format(i), dac)
            dacs.append(dac)

            pads = platform.request("dac", i)
            # inverted clocks ensure setup and hold times of data
            if silence:
                self.specials += Instance("OFDDRCPE",
                        i_C0=clk_p, i_C1=clk_n, i_CE=~dac.out.silence,
                        i_D0=0, i_D1=1, i_CLR=0, i_PRE=0, o_Q=pads.clk_p)
                self.specials += Instance("OFDDRCPE",
                        i_C0=clk_p, i_C1=clk_n, i_CE=~dac.out.silence,
                        i_D0=1, i_D1=0, i_CLR=0, i_PRE=0, o_Q=pads.clk_n)
                dclk = Signal()
                self.specials += Instance("OFDDRCPE",
                        i_C0=clk_p, i_C1=clk_n, i_CE=~dac.out.silence,
                        i_D0=0, i_D1=1, i_CLR=0, i_PRE=0, o_Q=dclk)
                self.specials += Instance("OBUFDS",
                        i_I=dclk,
                        o_O=pads.data_clk_p, o_OB=pads.data_clk_n)
            else:
                self.comb += pads.clk_p.eq(clk_n), pads.clk_n.eq(clk_p)
                self.specials += Instance("OBUFDS",
                        i_I=clk_n,
                        o_O=pads.data_clk_p, o_OB=pads.data_clk_n)
            for i in range(16):
                self.specials += Instance("OBUFDS",
                        i_I=~dac.out.data[i],
                        o_O=pads.data_p[i], o_OB=pads.data_n[i])
        #TIMEGRP "dac_Out" OFFSET = OUT 10 ns AFTER "clk_dac";

        self.submodules.comm = Comm(platform.request("comm"), dacs)

        clkin = platform.request("clk50")
        clkin_period = 20

        platform.add_platform_command("""
NET "{clk50}" TNM_NET = "grp_clk50";
TIMESPEC "ts_grp_clk50" = PERIOD "grp_clk50" 20 ns HIGH 50%;
""", clk50=clkin)

        if not fast:
            self.comb += clk_p.eq(clkin), clk_n.eq(~clkin)
            self.comb += self.cd_sys.rst.eq(self.comm.ctrl.reset)
        else:
            clkin_sdr = Signal()
            self.specials += Instance("IBUFG", i_I=clkin, o_O=clkin_sdr)

            dcm_clk2x = Signal()
            dcm_clk2x180 = Signal()
            dcm_locked = Signal()
            dcm_rst = Signal()
            self.specials += Instance("DCM_SP",
                    p_CLKDV_DIVIDE=2,
                    p_CLKFX_DIVIDE=1,
                    p_CLKFX_MULTIPLY=2,
                    p_CLKIN_DIVIDE_BY_2="FALSE",
                    p_CLKIN_PERIOD=clkin_period,
                    p_CLK_FEEDBACK="2X",
                    #p_CLK_FEEDBACK="NONE",
                    p_DLL_FREQUENCY_MODE="LOW",
                    p_DFS_FREQUENCY_MODE="LOW",
                    p_STARTUP_WAIT="FALSE",
                    p_PHASE_SHIFT=0,
                    p_DUTY_CYCLE_CORRECTION="TRUE",
                    i_RST=dcm_rst,
                    i_PSEN=0,
                    i_PSINCDEC=0,
                    i_PSCLK=0,
                    i_CLKIN=clkin_sdr,
                    o_LOCKED=dcm_locked,
                    o_CLK2X=dcm_clk2x,
                    o_CLK2X180=dcm_clk2x180,
                    #o_CLKFX=dcm_clk2x,
                    #o_CLKFX180=dcm_clk2x180,
                    i_CLKFB=clk_p,
                    #i_CLKFB=clk_p,
                    )
            self.specials += Instance("BUFG", i_I=dcm_clk2x, o_O=clk_p)
            self.specials += Instance("BUFG", i_I=dcm_clk2x180, o_O=clk_n)

            self.comb += self.cd_sys.rst.eq(~dcm_locked | self.comm.ctrl.reset)
            self.clock_domains.cd_dcm = ClockDomain(reset_less=True)
            self.comb += self.cd_dcm.clk.eq(clkin_sdr)
            # 3ms max startup, lets assume it does output something...
            t_dcm_reset = max(int(50e6*3e-3), 1<<25)
            dcm_reset_counter = Signal(max=t_dcm_reset)
            self.comb += dcm_rst.eq(dcm_reset_counter != t_dcm_reset - 1)
            self.sync.dcm += [
                    If(dcm_rst,
                        dcm_reset_counter.eq(dcm_reset_counter + 1),
                    #).Elif(~dcm_locked,
                    #    dcm_reset_counter.eq(0),
                    )]


class TB(Module):
    comm_pads = [
            ("rxfl", 1),
            ("rdl", 1),
            ("rd_in", 1),
            ("rd_out", 1),
            ("data", 8),
            ("adr", 4),
            ("aux", 1),
            ("interrupt", 3),
            ("trigger", 1),
            ("reset", 1),
            ("go2_in", 1),
            ("go2_out", 1),
            ]

    def __init__(self, mem=None, top=None):
        dacs = []
        for i in range(3):
            dac = Dac()
            setattr(self.submodules, "dac{}".format(i), dac)
            dacs.append(dac)
            dac.parser.mem.init = [0] * dac.parser.mem.depth
        self.pads = Record(self.comm_pads)
        self.submodules.comm = Comm(self.pads, dacs, mem)
        self.outputs = []

    def do_simulation(self, selfp):
        if selfp.simulator.cycle_counter == 0:
            selfp.pads.interrupt = 7 # pullup
            selfp.pads.adr = 15 # active low, pullup
            selfp.pads.trigger = 1 # pullup
        self.outputs.append(selfp.dac1.out.data)


def main():
    from migen.sim.generic import run_simulation
    from migen.sim.icarus import Runner
    from matplotlib import pyplot as plt
    import numpy as np

    import pdq
    pdq.Ftdi = pdq.FileFtdi

    t = np.arange(11)*.12e-6
    v = 9*(1-np.cos(t/t[-1]*np.pi))/2
    p = pdq.Pdq()
    mem = p.single_frame(t, v, channel=1, derivatives=4,
            aux=t<.5e-6, repeat=2, wait_last=True, time_shift=0)
    mem = p.cmd("RESET_EN") + mem + p.cmd("ARM_EN")
    tb = TB(list(mem))
    n = 6000
    run_simulation(tb, vcd_name="top.vcd", ncycles=n)
    out = np.array(tb.outputs, np.uint16).view(np.int16)*20./(1<<16)
    tim = np.arange(out.shape[0])/p.freq
    plt.plot(t, v)
    plt.plot(tim, out)
    plt.show()


if __name__ == "__main__":
    main()
