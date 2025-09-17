# XXX Maybe make this coarsePhaseWatch.py?
import logging

from clkpoc.df.pairPps import PairPps
from clkpoc.dsc import Dsc
from clkpoc.phaseAligner import PhaseAlignerDirect
from clkpoc.phaseStep import PhaseStep
from clkpoc.state import Mode, State
from clkpoc.tsTypes import PairTs, Ts


class PhaseWatch:
    """
    Subscribe to PairPps 'pairPps' topic and watch for
    the absolute phase difference between GNSS and disciplined PPS reference
    timestamps.
    If a coarse threshold is exceeded,
    start a PhaseStep task to step the TADD-2 Mini's phase into coarse alignment with GNSS.
    This should only happen once per boot, so log a warning if it happends more than once.
    XXX Better thining is that we shouldn't step if we ever made it to CoarseTune or FineTune mode.
    XXX finish doc here
    """
    # XXX Maybe rename to PhaseThresh? or PhaseLimit?

    def __init__(self, pairPps: PairPps, state: State,
        # CoarseThresh padded slightly over the 400 ns expected dscDev after a step
        coarseThresh: float = 510e-9, fineThresh: float = 20e-9) -> None:
        """
        pairPps: the PairPps instance publisher
        state: the State instance to update mode
        """
        self.pairPps = pairPps
        self.state = state
        assert self.state.mode == state.mode.Startup, "PhaseWatch should be started in Startup mode"

        # Store thresholds as Ts units
        self.coarseThresh = Ts.fromFloat(coarseThresh)
        self.fineThresh   = Ts.fromFloat(  fineThresh)

        # Subscribe to the PairPps publisher for paired PPS events
        pairPps.pub.sub("pairPps", self.onPairPps)

        self.phaseStep = None # PhaseStep instance created below as needed
        self.dsc = Dsc()

        f0Hz = 10_000_000.0
        hzPerLsb = -4.2034700315e-05   # Hz per code
        self.coarseTuner = PhaseAlignerDirect(
            f0Hz=f0Hz,
            hzPerLsb=hzPerLsb,
            codeMin=11400,
            codeMax=15000,
            codeInit=13200,
            maxPpb=20.0,         # your VCO pull (ppb)
            goalNs=25.0,         # handoff threshold
            sampleTime=1.0,
            holdCount=2,
        )

        self.clinkers = 0

    def doStep(self) -> None:
        # Pulse ARM pin on TADD-2 Mini via GPIO to trigger step in dscTs phase
        # Start background phase stepper if not already running
        self.phaseStep = PhaseStep()
        self.haveStepped = True

    def onPairPps(self, pair: PairTs) -> None:
        # Get deviation of Dsc PPS from Gns PPS timestamp on reference timescale
        dscDev = pair.dscTs.refTs - pair.gnsTs.refTs
        match self.state.mode:
            case Mode.Startup:
                # XXX add hack for forcing initial step here
                if abs(dscDev) > self.coarseThresh:
                    logging.info("PhaseWatch: Startup->Step |%s| > %s", dscDev.elapsedStr(),
                        self.coarseThresh)
                    self.doStep()
                    self.state.mode = Mode.Step
                elif abs(dscDev) > self.fineThresh:
                    logging.info("PhaseWatch: Startup->CoarseTune |%s| > %s", dscDev.elapsedStr(),
                        self.fineThresh)
                    # XXX Assumes we have history and restored DAC setting to last known value so
                    # freq is aprroximately right
                    self.state.mode = Mode.CoarseTune
                else:
                    logging.info("PhaseWatch: Startup->FineTune |%s| <= %s", dscDev.elapsedStr(),
                        self.fineThresh)
                    # XXX Assumes we have history and restored DAC setting to last known value so
                    # freq is aprroximately right
                    self.state.mode = Mode.FineTune

            case Mode.Step:
                if abs(dscDev) > self.coarseThresh:
                    self.clinkers += 1
                    if self.clinkers > 3:
                        self.doStep()
                        self.clinkers = 0
                        logging.info("PhaseWatch: Step Arming TADD again |%s| > %s",
                            dscDev.elapsedStr(), self.coarseThresh)
                elif abs(dscDev) > self.fineThresh:
                    # Most commmon case after stepping
                    logging.info("PhaseWatch: Step->CoarseTune |%s| > %s",
                        dscDev.elapsedStr(), self.fineThresh)
                    self.state.mode = Mode.CoarseTune
                else:
                    # Lucky day - stepped right into fine tune range
                    logging.info("PhaseWatch: Step->FineTune |%s| <= %s", dscDev.elapsedStr(),
                        self.fineThresh)
                    # XXX Assumes we have history and restored DAC setting to last known value so
                    # freq is aprroximately right
                    self.state.mode = Mode.FineTune

            case Mode.CoarseTune:
                if abs(dscDev) > self.coarseThresh:
                    self.clinkers += 1
                    if self.clinkers > 3:
                        self.doStep()
                        self.clinkers = 0
                        # XXX should be more severe logging level here, at least warning
                        logging.info("PhaseWatch: CoarseTune Arming TADD again |%s| > %s",
                            dscDev.elapsedStr(), self.coarseThresh)

                dscDevSec = dscDev.toPicoseconds()*1e-12
                newVal, done = self.coarseTuner.step(-dscDevSec)
                self.dsc.writeDac(newVal)
                # XXX should be logging.debug() here
                # print(f"PhaseWatch: CoarseTune dscDev={dscDevSec*1e9:5.1f} newVal={newVal}")
                if done:
                    logging.info("PhaseWatch: CoarseTune->FineTune")
                    self.state.mode = Mode.FineTune

            case Mode.FineTune:
                logging.info("PhaseWatch: FineTune %s", dscDev.elapsedStr())
