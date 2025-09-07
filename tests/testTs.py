import unittest

from clkpoc.clkTypes import Ts


class TestTs(unittest.TestCase):
    def test_normalizeByIncDec(self):
        # Test normalization with positive fractional overflow
        ts = Ts(10, 1.2)
        normalized = ts.normalizeByIncDec(ts)
        self.assertEqual(normalized.secs, 11)
        self.assertAlmostEqual(normalized.frac, 0.2)

        # Test normalization with negative fractional underflow
        ts = Ts(10, -0.5)
        normalized = ts.normalizeByIncDec(ts)
        self.assertEqual(normalized.secs, 9)
        self.assertAlmostEqual(normalized.frac, 0.5)

        # Test normalization with already normalized timestamp
        ts = Ts(10, 0.5)
        normalized = ts.normalizeByIncDec(ts)
        self.assertEqual(normalized.secs, 10)
        self.assertAlmostEqual(normalized.frac, 0.5)

    def test_subFrom(self):
        # Test subtraction with no normalization needed
        ts1 = Ts(10, 0.5)
        ts2 = Ts(15, 0.7)
        result = ts1.subFrom(ts2)
        self.assertEqual(result.secs, 5)
        self.assertAlmostEqual(result.frac, 0.2)

        # Test subtraction with normalization needed
        ts1 = Ts(10, 0.8)
        ts2 = Ts(15, 0.2)
        result = ts1.subFrom(ts2)
        self.assertEqual(result.secs, 4)
        self.assertAlmostEqual(result.frac, 0.4)

    def test_asSecAndNsec(self):
        # Test conversion to seconds and nanoseconds
        ts = Ts(10, 0.5)
        sec, nsec = ts.asSecAndNsec()
        self.assertEqual(sec, 10)
        self.assertEqual(nsec, 500_000_000)

        # Test fractional overflow
        ts = Ts(10, 1.2)
        sec, nsec = ts.asSecAndNsec()
        self.assertEqual(sec, 11)
        self.assertEqual(nsec, 200_000_000)

        # Test fractional underflow
        ts = Ts(10, -0.3)
        sec, nsec = ts.asSecAndNsec()
        self.assertEqual(sec, 9)
        self.assertEqual(nsec, 700_000_000)

    def test_isoUtc(self):
        # Test ISO UTC string generation
        ts = Ts(10, 0.5)
        iso = ts.isoUtc()
        self.assertEqual(iso, "1970-01-01T00:00:10.500000000Z")

        # Test fractional overflow
        ts = Ts(10, 1.2)
        iso = ts.isoUtc()
        self.assertEqual(iso, "1970-01-01T00:00:11.200000000Z")

        # Test fractional underflow
        ts = Ts(10, -0.3)
        iso = ts.isoUtc()
        self.assertEqual(iso, "1970-01-01T00:00:09.700000000Z")


if __name__ == "__main__":
    unittest.main()
