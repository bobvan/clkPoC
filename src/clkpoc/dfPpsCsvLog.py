from clkpoc.ts_types import TicTs
from clkpoc.tic import TIC


class PpsCsvLog:
    def __init__(self, tic: TIC, topic: str, fn: str):
        self.tic = tic
        self.topic = topic
        self.fn = fn
        tic.pub.sub(topic, self.logPps)

    def logPps(self, ts: TicTs):
#        print(f"PpsCsvLog, {ts}")
        pass
