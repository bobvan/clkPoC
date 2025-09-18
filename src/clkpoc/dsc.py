from enum import IntEnum, unique

from smbus2 import SMBus


# Control Disciplined Oscillator (DSC) via I2C using AD5693R DAC
class Dsc:
    def __init__(self,
            busNum: int = 1, addr: int = 0x4C, gain: int = 1, valInit: int = 9611) -> None:
        self.busNum = busNum
        self.addr = addr
        self.bus = SMBus(busNum)
        self.gain = gain
        self.writeControl(self.gain)
        self.writeDac(valInit)
        self.value = valInit

    @unique
    class CommandBytes(IntEnum):
        # AD5693 command bytes (DB7..DB4)
        CMD_WRITE_INPUT         = 0x10  # not used here
        CMD_UPDATE_DAC          = 0x20  # not used here
        CMD_WRITE_DAC_AND_INPUT = 0x30
        CMD_WRITE_CONTROL       = 0x40

    def clamp16(self, x: int) -> int:
        return max(0, min(0xFFFF, x))

    def writeDac(self, value: int) -> None:
        value = self.clamp16(value)
        dataHigh = (value >> 8) & 0xFF
        dataLow  = value & 0xFF
        self.bus.write_i2c_block_data(
            self.addr,
            self.CommandBytes.CMD_WRITE_DAC_AND_INPUT,
            [dataHigh, dataLow],
        )
#        print(f"DSC: wrote DAC value {value} (0x{value:04X})")

    # XXX I don't think this works. Sometimes seems to give old values.
    def readDac(self) -> int:
        return self.value
#        # Read back the DAC register (2 bytes)
#        data = self.bus.read_i2c_block_data(self.addr, 0x00, 2)
#        value = (data[0] << 8) | data[1]
#        return value

    def writeControl(self, gain: int = 1) -> None:
        # Control register bits are sent in the upper 5 bits of the first data byte:
        # D15 Reset, D14 PD1, D13 PD0, D12 REF, D11 Gain
        resetBit = 0
        pd1Bit = 0
        pd0Bit = 0
        # For AD5693R the REF bit controls the internal reference (0=enabled)
        refBit = 0
        if gain not in (1, 2):
            raise ValueError("gain must be 1 or 2")
        gainBit = 1 if gain == 2 else 0

        dataHigh = (resetBit << 7) | (pd1Bit << 6) | (pd0Bit << 5) | (refBit << 4) | (gainBit << 3)
        self.bus.write_i2c_block_data(
            self.addr,
            self.CommandBytes.CMD_WRITE_CONTROL,
            [dataHigh, 0x00],
        )
