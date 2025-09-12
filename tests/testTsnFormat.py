import unittest

from clkpoc.tsn import Tsn  # or: from tsn import Tsn

# AI Suggested, but didn't seem to work
# Deterministic tzlocal shim so isoLocal() doesn’t depend on host timezone
# fake = types.ModuleType("tzlocal")
# fake.get_localzone_name = lambda: "UTC"
# sys.modules["tzlocal"] = fake


class TestTsnFormat(unittest.TestCase):
    def testDefaultMatchesStr(self) -> None:
        ts = Tsn.fromParts(0, 123_456_789_012)
        self.assertEqual(f"{ts}", str(ts))
        self.assertEqual(format(ts, ""), str(ts))

    def testAFormatMatchesStr(self) -> None:
        ts = Tsn.fromParts(1, 0)
        self.assertEqual(f"{ts:A}", str(ts))

    def testUtcFormatUpperLower(self) -> None:
        ts = Tsn.fromParts(0, 987_000_000_000)
        self.assertEqual(f"{ts:U}", ts.isoUtc())
        self.assertEqual(f"{ts:u}", ts.isoUtc())

    # N.B. This will break outside of the development timezone and maybe at DST boundaries
    def testLocalFormatUsesIsoLocal(self) -> None:
        ts = Tsn.fromParts(42, 0)
        self.assertEqual(f"{ts:L}", ts.isoLocal())
        self.assertTrue(f"{ts:L}".endswith("-06:00"))

    def testElapsedFormat(self) -> None:
        ts = Tsn.fromParts(3, 250_000_000_000)  # 3.25 s
        self.assertEqual(f"{ts:E}", ts.elapsedStr())
        self.assertTrue(f"{ts:E}".endswith("s"))

    def testUnknownSpecFallsBackToStr(self) -> None:
        ts = Tsn.fromParts(0, 1)
        self.assertEqual(f"{ts:X}", str(ts))
        self.assertEqual(f"{ts:???}", str(ts))
