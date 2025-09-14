import copy

from clkpoc.ts_types import PairTs, TicTs
from clkpoc.tsn import Tsn
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

    def pubIfPair(self, capDelta: Tsn) -> None:
#        print(f"PairPps capDelta {capDelta}")
        # publish only if capture timestamps are within 0.5 seconds
        half_sec_units = Tsn.unitsPerSecond // 2
        if abs(capDelta.units) >= half_sec_units:
            print(f"PairPps: Waiting for Ts pair")
            return
        if self.gnsTs is None or self.dscTs is None:
            return  # Additional safety check for Pyright
        pair = PairTs(gnsTs=self.gnsTs, dscTs=self.dscTs)
        self.pub.publish("pairPps", pair)
#        print(f"PairPps: {pair}")
        tsDelta = pair.gnsTs.refTs.sub(pair.dscTs.refTs)
        print(f"PairPps: capDelta {capDelta}, tsDelta {tsDelta}")

    def gnsCb(self, gnsTs: TicTs):
        self.gnsTs = copy.deepcopy(gnsTs)
        if self.dscTs is None:
            print("PairPps: Waiting for first dscTs")
            return
        capDelta = gnsTs.capTs.sub(self.dscTs.capTs)
        self.pubIfPair(capDelta)

    def dscCb(self, dscTs: TicTs):
        self.dscTs = copy.deepcopy(dscTs)
        if self.gnsTs is None:
            print("PairPps: Waiting for first gns:Ts")
            return
        capDelta = dscTs.capTs.sub(self.gnsTs.capTs)
        self.pubIfPair(capDelta)
