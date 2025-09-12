
import sys
import types
import unittest
from datetime import UTC, datetime
from clkpoc.tsn import Tsn


# Provide a lightweight tzlocal shim so importing tsn doesn't fail if tzlocal isn't installed here
fake = types.ModuleType("tzlocal")
fake.get_localzone_name = lambda: "UTC"
sys.modules["tzlocal"] = fake


class TestToIso8601(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Nothing to set up beyond the tzlocal shim above
        return None

    def testUtcEpochNoFraction(self) -> None:
        ts = Tsn.fromParts(0, 0)
        self.assertEqual(ts.toIso8601(0, "Z"), "1970-01-01T00:00:00Z")

    def testUtcFullPrecision(self) -> None:
        ts = Tsn.fromParts(0, 123_456_789_012)
        self.assertEqual(ts.toIso8601(12, "Z"), "1970-01-01T00:00:00.123456789012Z")

    def testHalfEvenUp(self) -> None:
        # 0.15 s -> 0.2 s at 1 decimal (ties to even: 1 -> round up)
        ts = Tsn.fromParts(0, 150_000_000_000)
        self.assertEqual(ts.toIso8601(1, "Z"), "1970-01-01T00:00:00.2Z")

    def testHalfEvenDown(self) -> None:
        # 0.25 s -> 0.2 s at 1 decimal (ties to even: 2 -> stay)
        ts = Tsn.fromParts(0, 250_000_000_000)
        self.assertEqual(ts.toIso8601(1, "Z"), "1970-01-01T00:00:00.2Z")

    def testRoundingCarryToNextSecond(self) -> None:
        # 0.999500 s at millisecond precision rounds to 1.000 and carries
        ts = Tsn.fromParts(0, 999_500_000_000)
        self.assertEqual(ts.toIso8601(3, "Z"), "1970-01-01T00:00:01.000Z")

    def testNegativeHalfSecond(self) -> None:
        ts = Tsn.fromPicoseconds(-500_000_000_000)
        self.assertEqual(ts.toIso8601(3, "Z"), "1969-12-31T23:59:59.500Z")

    def testChicagoEpochOffset(self) -> None:
        # Epoch in America/Chicago is 1969-12-31 18:00:00 with -06:00 offset
        ts = Tsn.fromParts(0, 0)
        self.assertEqual(ts.toIso8601(0, "America/Chicago"), "1969-12-31T18:00:00-06:00")

    def testChicagoDstOffsetSummer(self) -> None:
        # 2024-06-01 00:00:00 UTC => 2024-05-31 19:00:00-05:00 in America/Chicago
        sec = int(datetime(2024, 6, 1, 0, 0, 0, tzinfo=UTC).timestamp())
        ts = Tsn.fromParts(sec, 0)
        self.assertEqual(ts.toIso8601(0, "America/Chicago"), "2024-05-31T19:00:00-05:00")

    def testZoneNoneDefaultsToZ(self) -> None:
        ts = Tsn.fromParts(0, 0)
        self.assertEqual(ts.toIso8601(0, None), "1970-01-01T00:00:00Z")

    def testInvalidPlacesTooSmall(self) -> None:
        ts = Tsn.fromParts(0, 0)
        with self.assertRaises(ValueError):
            _ = ts.toIso8601(-1, "Z")

    def testInvalidPlacesTooLarge(self) -> None:
        ts = Tsn.fromParts(0, 0)
        with self.assertRaises(ValueError):
            _ = ts.toIso8601(Tsn.fracDigs + 1, "Z")

if __name__ == "__main__":
    unittest.main(verbosity=2)
