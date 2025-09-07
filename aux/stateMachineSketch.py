# pip install transitions
from transitions.extensions.asyncio import AsyncMachine


class GpsdoModes:
    states = ["idle", "disciplining", "holdover", "fault"]
    def __init__(self):
        self.machine = AsyncMachine(model=self, states=self.states, initial="idle")
        self.machine.add_transition("ppsGood", "idle", "disciplining")
        self.machine.add_transition("ppsLost", "disciplining", "holdover")
        self.machine.add_transition("recovered", "holdover", "disciplining")
        self.machine.add_transition("error", "*", "fault")
