import math
import random
import unittest
from datetime import datetime

from clkpoc.clkTypes import Ts


class TestTs(unittest.TestCase):
    def test_normalizeByIncDec(self):
        # Test normalization with positive fractional overflow
        ts = Ts(10, 1200000000000)
        ts.normalizeByIncDec()
        self.assertEqual(ts.secs, 11)
        self.assertAlmostEqual(ts.frac, 200000000000)

        # Test normalization with negative fractional underflow
        ts = Ts(10, -500000000000)
        ts.normalizeByIncDec()
        self.assertEqual(ts.secs, 9)
        self.assertAlmostEqual(ts.frac, 500000000000)

        # Test normalization with already normalized timestamp
        ts = Ts(10, 500000000000)
        ts.normalizeByIncDec()
        self.assertEqual(ts.secs, 10)
        self.assertAlmostEqual(ts.frac, 500000000000)

    def test_subFrom(self):
        # Test subtraction with no normalization needed
        ts1 = Ts(10, 500000000000)
        ts2 = Ts(15, 700000000000)
        ts1.subFrom(ts2)
        self.assertEqual(ts1.secs, 5)
        self.assertAlmostEqual(ts1.frac, 200000000000)

        # Test subtraction with normalization needed
        ts1 = Ts(10, 800000000000)
        ts2 = Ts(15, 200000000000)
        ts1.subFrom(ts2)
        self.assertEqual(ts1.secs, 4)
        self.assertAlmostEqual(ts1.frac, 400000000000)

    def test_now(self):
            ts = Ts.now()
            self.assertIsInstance(ts, Ts)
            self.assertGreaterEqual(ts.secs, 0)
            self.assertGreaterEqual(ts.frac, 0)
            self.assertLess(ts.frac, 1)

    def test_fromStr(self):
        ts = Ts.fromStr("12345", "678901234567")
        self.assertEqual(ts.secs, 12345)
        self.assertAlmostEqual(ts.frac, 678901234567)

        ts = Ts.fromStr("0", "0")
        self.assertEqual(ts.secs, 0)
        self.assertAlmostEqual(ts.frac, 0)

    def test_fracStr(self):
        ts = Ts(10, 123456789012)
        frac_str = ts.fracStr(places=12)
        self.assertEqual(frac_str, "123456789012")

        ts = Ts(10, 100000000000)
        frac_str = ts.fracStr(places=5)
        self.assertEqual(frac_str, "10000")

        ts = Ts(10, 999999999999)
        frac_str = ts.fracStr(places=6)
        self.assertEqual(frac_str, "999999")

#    def test_fracStr(self):
#        # Test with a fractional part that does not cause a carry
#        ts = Ts(10, 0.123456789012)
#        carry, frac_str = ts.fracStr(places=12)
#        self.assertEqual(carry, 0)
#        self.assertEqual(frac_str, "123456789012")
#
#        # Test with a fractional part that causes a carry into the integer part
#        ts = Ts(10, 0.999999999999)
#        carry, frac_str = ts.fracStr(places=9)
#        self.assertEqual(carry, 1)
#        self.assertEqual(frac_str, "000000000")
#
#        # Test with zero fractional part
#        ts = Ts(10, 0.0)
#        carry, frac_str = ts.fracStr(places=6)
#        self.assertEqual(carry, 0)
#        self.assertEqual(frac_str, "000000")
#
#        # Test with a fractional part that rounds up but does not carry
#        ts = Ts(10, 0.123456789876)
#        carry, frac_str = ts.fracStr(places=9)
#        self.assertEqual(carry, 0)
#        self.assertEqual(frac_str, "123456790")
#
#        # Test with a fractional part that rounds up and causes a carry
#        ts = Ts(10, 0.99999999951)
#        carry, frac_str = ts.fracStr(places=9)
#        self.assertEqual(carry, 1)
#        self.assertEqual(frac_str, "000000000")

    def test_isoUtc(self):
        # Test ISO UTC string generation
        ts = Ts(10, 500000000000)
        iso = ts.isoUtc()
        self.assertEqual(iso, "1970-01-01T00:00:10.500000000Z")

        # Test fractional overflow
        ts = Ts(10, 1200000000000)
        ts.normalizeByIncDec()
        iso = ts.isoUtc()
        self.assertEqual(iso, "1970-01-01T00:00:11.200000000Z")

        # Test fractional underflow
        ts = Ts(10, -300000000000)
        ts.normalizeByIncDec()
        iso = ts.isoUtc()
        self.assertEqual(iso, "1970-01-01T00:00:09.700000000Z")

    def test_isoLocal(self):
        # Test with a known timestamp
        ts = Ts(1672531200, 123456789000)  # 2023-01-01T00:00:00.123456789 in UTC
        iso_local = ts.isoLocal()
        dt = datetime.fromtimestamp(1672531200).astimezone()
        expected_base = dt.strftime("%Y-%m-%dT%H:%M:%S")
        expected_offset = dt.strftime("%z")
        expected_offset = expected_offset[:-2]+":" + expected_offset[-2:] if expected_offset else ""
        self.assertEqual(iso_local, f"{expected_base}.123456789{expected_offset}")

    def test_elapsedStr(self):
        # Test with a simple elapsed time
        ts = Ts(123, 456789000000)
        elapsed_str = ts.elapsedStr()
        self.assertEqual(elapsed_str, "123.456789000000s")

        # Test with zero seconds and fractional part
        ts = Ts(0, 0)
        elapsed_str = ts.elapsedStr()
        self.assertEqual(elapsed_str, "0.000000000000s")

        # Test with a large number of seconds
        ts = Ts(987654321, 987654321000)
        elapsed_str = ts.elapsedStr()
        self.assertEqual(elapsed_str, "987654321.987654321000s")


    def test_random_subtraction(self):
        for _ in range(100):
            # Generate two random floats in the range (-10, 10)
            float1 = random.uniform(-10, 10)
            float2 = random.uniform(-10, 10)

            # Create Ts objects
            ts1 = Ts.fromFloat(float1)
            ts2 = Ts.fromFloat(float2)

            # Perform subtraction using subFrom()
            ts1.subFrom(ts2)

            # Perform floating-point subtraction
            expected_result = float2 - float1
            ts3 = Ts.fromFloat(expected_result)
            expected_frac_part, expected_int_part = math.modf(expected_result)

            # Assert the results
            print(f"Testing subtraction: {float2} - {float1} = {expected_result} int {expected_int_part} frac {expected_frac_part} vs {ts1:E}")
            self.assertEqual(ts1.secs, ts3.secs)
            self.assertAlmostEqual(ts1.frac, ts3.frac, delta=1)


if __name__ == "__main__":
    unittest.main()
