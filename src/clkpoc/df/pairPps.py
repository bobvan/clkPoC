import copy

from clkpoc.tic import TIC
from clkpoc.topicPublisher import TopicPublisher
from clkpoc.tsTypes import PairTs, TicTs, Ts


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
        # publish only if capture timestamps are within 0.5 seconds
        halfSecInPs = 500_000_000_000
        if abs(capDelta.toPicoseconds()) >= halfSecInPs:
            # Note that this is noramal for 1/2 of all potential pairs
#            print(f"PairPps: Waiting for closeby Ts pair, {capDelta.elapsedStr()} apart")
            return
        if self.gnsTs is None or self.dscTs is None:
            return  # Additional safety check for Pyright
        pair = PairTs(gnsTs=self.gnsTs, dscTs=self.dscTs)
        self.pub.publish("pairPps", pair)
#        print(f"PairPps: {pair}")
        # Deviation of dsc from gns timestamps
#        dscDev = pair.gnsTs.refTs.subFrom(pair.dscTs.refTs)
#        print(f"PairPps: dscDev {dscDev.elapsedStr()}")

    def gnsCb(self, gnsTs: TicTs):
        self.gnsTs = copy.deepcopy(gnsTs) # XXX copy should no longer be needed
        if self.dscTs is None:
            # This is normal for 1/2 of all startups
            print("PairPps: Waiting for first dscTs")
            return
        capDelta = gnsTs.capTs.subFrom(self.dscTs.capTs)
        self.pubIfPair(capDelta)

    def dscCb(self, dscTs: TicTs):
        self.dscTs = copy.deepcopy(dscTs) # XXX copy should no longer be needed
        if self.gnsTs is None:
            # This is normal for 1/2 of all startups
            print("PairPps: Waiting for first gns:Ts")
            return
        capDelta = dscTs.capTs.subFrom(self.gnsTs.capTs)
        self.pubIfPair(capDelta)
