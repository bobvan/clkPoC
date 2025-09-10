import copy

from clkpoc.clkTypes import PairTs, TicTs, Ts
from clkpoc.tic import TIC
from clkpoc.topicPublisher import TopicPublisher


# Subscribe to two PPS topics and publish when a pair has capture
# timestamps < 0.5 seconds apart, regarless of arrival order.
# This covers missing timestamps on either topic, and pairs up
# PPS events for the same UTC second.
class PairPps:
    def __init__(self, tic: TIC, gnsTopic: str, dscTopic: str):
        self.tic: TIC = tic
        self.gnsTopic: str = gnsTopic
        self.dscTopic: str = dscTopic
        self.gnsTs: TicTs | None = None
        self.dscTs: TicTs | None = None
        self.pub = TopicPublisher("pairPps", warnIfSlowMs=5.0)
        tic.pub.sub(gnsTopic, self.gnsCb)
        tic.pub.sub(dscTopic, self.dscCb)

    def pubIfPair(self, capDelta: Ts) -> None:
#        print(f"PairPps capDelta {capDelta}")
        # XXX this should be call back into Ts so representaion is hidden
        # XXX for now, -0.5 is represented as -1 sec + 500000000000 frac
        totalPS = capDelta.secs*Ts.fracUnitsPerSecond + capDelta.frac
        if abs(totalPS) >= 500000000000:
            return
        if self.gnsTs is None or self.dscTs is None:
            return  # Additional safety check for Pyright
        pair = PairTs(gnsTs=self.gnsTs, dscTs=self.dscTs)
        self.pub.publish("pairPps", pair)
        print(f"PairPps: {pair}")

    def gnsCb(self, gnsTs: TicTs):
        self.gnsTs = copy.deepcopy(gnsTs)
        if self.dscTs is None:
            return
        capDelta = gnsTs.capTs
        capDelta.subFrom(self.dscTs.capTs)
        self.pubIfPair(capDelta)

    def dscCb(self, dscTs: TicTs):
        self.dscTs = copy.deepcopy(dscTs)
        if self.gnsTs is None:
            return
        capDelta = dscTs.capTs
        capDelta.subFrom(self.gnsTs.capTs)
        self.pubIfPair(capDelta)
