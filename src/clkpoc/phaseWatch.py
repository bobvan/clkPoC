import logging

from clkpoc.df.pairPps import PairPps
from clkpoc.phaseStep import PhaseStep
from clkpoc.tsTypes import PairTs, Ts


class PhaseWatch:
    """
    Subscribe to PairPps 'pairPps' topic and watch for
    the absolute phase difference between GNSS and disciplined PPS reference
    timestamps to exceed configurable thresholds. If the threshold is exceeded,
    start a PhaseStep task to step the TADD-2 Mini's phase into coarse alignment with GNSS.
    This should only happen once per boot, so log a warning if it happends more than once.
    Different thresholds can be used for the first step and subsequent steps.
    """
    # XXX Maybe rename to PhaseThresh? or PhaseLimit?

    def __init__(self, pairPps: PairPps,
        firstThresh: float = 400e-9, otherThresh: float = 1e-6) -> None:
        """
        pairPps: the PairPps instance publisher
        firstThresh: absolute Dsc deviation threshold in seconds
        """
        self.pairPps = pairPps
        # Store thresholds as Ts units
        self.firstThresh = Ts.fromFloat(firstThresh)
        self.otherThresh = Ts.fromFloat(otherThresh)
        # Subscribe to the PairPps publisher for paired PPS events
        pairPps.pub.sub("pairPps", self.onPairPps)
        self.haveStepped = False
        self.phaseStep = None

    def doStep(self) -> None:
        # Pulse ARM pin on TADD-2 Mini via GPIO to trigger step in dscTs phase
        self.phaseStep = PhaseStep() # Start background phase stepper if not already running
        self.haveStepped = True

    def onPairPps(self, pair: PairTs) -> None:
        if self.phaseStep is not None and self.phaseStep.is_running():
            # A PhaseStep task is already running; do nothing more for now
            return

        # Get deviation of Dsc PPS from Gns PPS timestamp on reference timescale
        dscDev = pair.gnsTs.refTs.subFrom(pair.dscTs.refTs)
        if not self.haveStepped and abs(dscDev.toUnits()) >= self.firstThresh.toUnits():
            # XXX note print() here vs logging.warning() below
            print("PhaseWatch: Dsc PPS deviation first threshold exceeded. Stepping Dsc phase.")
            self.doStep()

        elif self.haveStepped and abs(dscDev.toUnits()) >= self.otherThresh.toUnits():
            logging.warning(
                "PhaseWatch: Dsc PPS deviation other threshold exceeded. "
                "step: |%s| >= %s (gns=%s dsc=%s)",
                dscDev.elapsedStr(),
                self.otherThresh,
                pair.gnsTs.refTs,
                pair.dscTs.refTs,
            )
            self.doStep()
