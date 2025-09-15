import logging

from clkpoc.df.pairPps import PairPps
from clkpoc.phaseStep import PhaseStep
from clkpoc.tsTypes import PairTs, Ts


class PhaseWatch:
    """
    Subscribe to PairPps 'pairPps' topic and watch for
    the absolute phase difference between GNSS and disciplined PPS reference
    timestamps to exceed a configurable threshold. If the threshold is exceeded,
    start a PhaseStep task to step the TADD-2 Mini's phase into coarse alignment with GNSS.
    This should only happen once per boot, so log a warning if it happends more than once.
    """
    # XXX Maybe rename to PhaseThresh? or PhaseLimit?

    def __init__(self, pairPps: PairPps, thresholdSec: float = 1e-6) -> None:
        """
        pairPps: the PairPps instance publisher
        thresholdSec: absolute Dsc deviation threshold in seconds
        """
        self.pairPps = pairPps
        # Store threshold as Ts units (picoseconds by default in Ts)
        self.threshold = Ts.fromFloat(thresholdSec)
        # Subscribe to the PairPps publisher for paired PPS events
        pairPps.pub.sub("pairPps", self.onPairPps)
        self.haveStepped = False
        self.phaseStep = None

    def onPairPps(self, pair: PairTs) -> None:
        # Get deviation of Dsc PPS from Gns PPS timestamp on reference timescale
        dscDev = pair.gnsTs.refTs.subFrom(pair.dscTs.refTs)
        if abs(dscDev.units) >= self.threshold.units:
            if self.phaseStep is not None and self.phaseStep.is_running():
                # A PhaseStep task is already running; do nothing more for now
                return
            if self.haveStepped:
                logging.warning(
                    "PhaseWatch: Dsc PPS deviation threshold exceeded again. "
                    "step: |%s| >= %s (gns=%s dsc=%s)",
                    dscDev.elapsedStr(),
                    self.threshold,
                    pair.gnsTs.refTs,
                    pair.dscTs.refTs,
                )
            # Pulse ARM pin on TADD-2 Mini via GPIO to trigger step in dscTs phase
            print("PhaseWatch: Dsc PPS deviation threshold exceeded. Stepping Dsc phase.")
            self.phaseStep = PhaseStep() # Start background phase stepper if not already running
            self.haveStepped = True
