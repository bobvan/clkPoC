from clkpoc.df.pairPps import PairPps
from clkpoc.f9t import F9T
from clkpoc.topicPublisher import TopicPublisher
from clkpoc.tsTypes import PairTs, QerrTs, TicTs


# Subscribe to timestamp pairs for the same UTC second and quantization error corrections.
# Publish timestamp pairs with qErr corrections applied to the GNSS PPS timestamp.
#
# The correction values from the F9T can vary over their full range from second to second,
# hence applying a correction to the wrong timestamp would be worse than not correcting.
# Corrections from the F9T always preceed the associated GNSS PPS timestamp, so check capture
# timestamps to ensure the correction is applied to the proper timestamp.
#
# Hold the correction when it arrives, wait for the next GNSS PPS timestamp, and if they
# are close enough in capture time, publish the pair with the correction applied.
class PairQerr:
    def __init__(self, pairPps: PairPps, f9t: F9T, pairPpsTopic: str, qErrTopic: str):
        self.qErrTs: QerrTs | None = None
        self.pub = TopicPublisher("gnsQerr", warnIfSlowMs=5.0)
        pairPps.pub.sub(pairPpsTopic, self.pairCb)
        f9t.pub.sub(qErrTopic, self.qErrCb)

    def qErrCb(self, qErrTs: QerrTs):
        self.qErrTs = qErrTs
#        print(f"PairQerr: Got qErrTs {qErrTs}")

    def pairCb(self, pairTs: PairTs):
        if self.qErrTs is None:
            # This is normal for 1/2 of all startups
            print("PairQerr: Waiting for first qErrTs")
            # XXX Should count and warn if too many pairs without corrections
            return

        qErrCapLead = pairTs.gnsTs.capTs - self.qErrTs.capTs
        qErrCapLeadPs = qErrCapLead.toPicoseconds()
        if qErrCapLeadPs>=1_000_000_000_000 or qErrCapLeadPs<0:
            # This should be logging warning
            print(f"PairQerr: Dropping pair, qErrCapLeadPs {qErrCapLead} outside expected range")
            # XXX Should count and warn if too many pairs dropped
            return

        # Apply quantization error correction to GNSS PPS reference timestamp
        corrGnsRefTs = pairTs.gnsTs.refTs + self.qErrTs.qErr
#        print(f"PairQerr: qErr {self.qErrTs.qErr.elapsedStr()} applied to gnsRefTs {pairTs.gnsTs.refTs:E} gives {corrGnsRefTs:E}")  # noqa: E501
        corrGnsTs = TicTs(capTs=pairTs.gnsTs.capTs, refTs=corrGnsRefTs)
        corrPair = PairTs(gnsTs=corrGnsTs, dscTs=pairTs.dscTs)
        self.pub.publish("pairQerr", corrPair)
