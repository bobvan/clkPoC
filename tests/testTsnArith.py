
import sys
import types
import unittest
from clkpoc.tsn import Tsn

# tzlocal shim (to keep imports happy if tsn imports it indirectly)
fake = types.ModuleType("tzlocal")
fake.get_localzone_name = lambda: "UTC"
sys.modules["tzlocal"] = fake

class TestTsnArith(unittest.TestCase):
    def testIntMultiplyExact(self) -> None:
        ts = Tsn.fromParts(1, 500_000_000_000)  # 1.5 s
        out = ts.multiply(2)
        self.assertIsInstance(out, Tsn)
        self.assertEqual(out.toDecimal(3), "3.000")

    def testIntDivideRoundEven(self) -> None:
        onePs = Tsn.fromPicoseconds(1)
        threePs = Tsn.fromPicoseconds(3)
        self.assertEqual(onePs.divide(2).toPicoseconds(), 0)   # 0.5 ps -> 0 (even tie)
        self.assertEqual(threePs.divide(2).toPicoseconds(), 2) # 1.5 ps -> 2 (even tie)

    def testFloatMultiplyRoundEven(self) -> None:
        onePs = Tsn.fromPicoseconds(1)
        threePs = Tsn.fromPicoseconds(3)
        self.assertEqual(onePs.multiply(0.5).toPicoseconds(), 0)   # 0.5 -> 0
        self.assertEqual(threePs.multiply(0.5).toPicoseconds(), 2) # 1.5 -> 2

    def testFloatDivide(self) -> None:
        ts = Tsn.fromParts(1, 500_000_000_000)  # 1.5 s
        out = ts.divide(0.5)                    # divide by 1/2 == multiply by 2
        self.assertIsInstance(out, Tsn)
        self.assertEqual(out.toDecimal(3), "3.000")

    def testDivideByTsnReturnsFloat(self) -> None:
        a = Tsn.fromParts(2, 0)                      # 2 s
        b = Tsn.fromParts(0, 500_000_000_000)        # 0.5 s
        r = a.divide(b)
        self.assertIsInstance(r, float)
        self.assertEqual(r, 4.0)

    def testNegativeValues(self) -> None:
        neg = Tsn.fromParts(-1, 500_000_000_000)   # -0.5 s
        self.assertEqual(neg.divide(2).toDecimal(12), "-0.250000000000")
        self.assertEqual(neg.multiply(3).toDecimal(3), "-1.500")

    def testChainedExactRational(self) -> None:
        tenPs = Tsn.fromPicoseconds(10)
        after = tenPs.multiply(0.1).divide(0.1)
        self.assertEqual(after.toPicoseconds(), 10)

    def testZeroDivisionInt(self) -> None:
        ts = Tsn.fromPicoseconds(1)
        with self.assertRaises(ZeroDivisionError):
            _ = ts.divide(0)

    def testZeroDivisionFloat(self) -> None:
        ts = Tsn.fromPicoseconds(1)
        with self.assertRaises(ZeroDivisionError):
            _ = ts.divide(0.0)

    def testZeroDivisionTsn(self) -> None:
        ts = Tsn.fromPicoseconds(1)
        z = Tsn.fromPicoseconds(0)
        with self.assertRaises(ZeroDivisionError):
            _ = ts.divide(z)

    def testLargeValuesNoOverflow(self) -> None:
        big = Tsn.fromPicoseconds(10**18)  # ~ 11.57 days in ps
        out = big.divide(2)
        self.assertEqual(out.toPicoseconds(), 10**18 // 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
