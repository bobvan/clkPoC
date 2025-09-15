import logging

from clkpoc.df.pairPps import PairPps
from clkpoc.phaseStep import PhaseStep
from clkpoc.ts_types import PairTs
from clkpoc.tsn import Tsn


class StepWatch:
    """
    Subscribe to PairPps 'pairPps' topic and watch for
    the phase difference between GNSS and disciplined PPS reference
    timestamps to exceed a configurable threshold. If the threshold is exceeded,
    start a PhaseStep task to step the TADD-2 Mini's phase into coarse alignment with GNSS.
    This should only happen once per boot, so log a warning if it happends more than once.
    """

    def __init__(self, pairPps: PairPps, thresholdSec: float = 1e-6) -> None:
        """
        pairPps: the PairPps instance to subscribe to.
        thresholdSec: absolute delta threshold in seconds for detection.
        """
        self.pairPps = pairPps
        # Store threshold as Tsn units (picoseconds by default in Tsn)
        self.threshold = Tsn.fromFloat(thresholdSec)
        # Subscribe to the PairPps publisher for paired PPS events
        pairPps.pub.sub("pairPps", self._on_pair)
        self.haveStepped = False
        self.phaseStep = None

    def _on_pair(self, pair: PairTs) -> None:
        # Compute delta between reference timestamps
        # XXX might be better to compute ma5(delta) to avoid false positives
        delta = pair.gnsTs.refTs.sub(pair.dscTs.refTs)
        if abs(delta.units) >= self.threshold.units:
            if self.phaseStep is not None and self.phaseStep.is_running():
                # A PhaseStep task is already running; do nothing more for now
                return
            if self.haveStepped:
                logging.warning(
                    "StepWatch: GNSS PPS - Dsc PPS delta exceeded again. "
                    "step: |%s| >= %s (gns=%s dsc=%s)",
                    delta,
                    self.threshold,
                    pair.gnsTs.refTs,
                    pair.dscTs.refTs,
                )
            # Pulse ARM pin on TADD-2 Mini via GPIO to trigger step in dscTs phase
            print("StepWatch: GNSS PPS - Dsc PPS delta exceeded. Stepping dscTs phase.")
            self.phaseStep = PhaseStep() # Start background phase stepper if not already running
            self.haveStepped = True
