import unittest

from clkpoc.tsTypes import Ts


class TestTsArith(unittest.TestCase):
    def testIntMultiplyExact(self) -> None:
        ts = Ts.fromParts(1, 500_000_000_000)  # 1.5 s
        out = ts.multiply(2)
        self.assertIsInstance(out, Ts)
        self.assertEqual(out.toDecimal(3), "3.000")

    def testIntDivideRoundEven(self) -> None:
        onePs = Ts.fromPicoseconds(1)
        threePs = Ts.fromPicoseconds(3)
        self.assertEqual(onePs.divide(2).toPicoseconds(), 0)   # 0.5 ps -> 0 (even tie)
        self.assertEqual(threePs.divide(2).toPicoseconds(), 2) # 1.5 ps -> 2 (even tie)

    def testFloatMultiplyRoundEven(self) -> None:
        onePs = Ts.fromPicoseconds(1)
        threePs = Ts.fromPicoseconds(3)
        self.assertEqual(onePs.multiply(0.5).toPicoseconds(), 0)   # 0.5 -> 0
        self.assertEqual(threePs.multiply(0.5).toPicoseconds(), 2) # 1.5 -> 2

    def testFloatDivide(self) -> None:
        ts = Ts.fromParts(1, 500_000_000_000)  # 1.5 s
        out = ts.divide(0.5)                    # divide by 1/2 == multiply by 2
        self.assertIsInstance(out, Ts)
        self.assertEqual(out.toDecimal(3), "3.000")

    def testDivideByTsReturnsFloat(self) -> None:
        a = Ts.fromParts(2, 0)                      # 2 s
        b = Ts.fromParts(0, 500_000_000_000)        # 0.5 s
        r = a.divide(b)
        self.assertIsInstance(r, float)
        self.assertEqual(r, 4.0)

    def testNegativeValues(self) -> None:
        neg = Ts.fromParts(-1, 500_000_000_000)   # -0.5 s
        self.assertEqual(neg.divide(2).toDecimal(12), "-0.250000000000")
        self.assertEqual(neg.multiply(3).toDecimal(3), "-1.500")

    def testChainedExactRational(self) -> None:
        tenPs = Ts.fromPicoseconds(10)
        after = tenPs.multiply(0.1).divide(0.1)
        self.assertEqual(after.toPicoseconds(), 10)

    def testZeroDivisionInt(self) -> None:
        ts = Ts.fromPicoseconds(1)
        with self.assertRaises(ZeroDivisionError):
            _ = ts.divide(0)

    def testZeroDivisionFloat(self) -> None:
        ts = Ts.fromPicoseconds(1)
        with self.assertRaises(ZeroDivisionError):
            _ = ts.divide(0.0)

    def testZeroDivisionTs(self) -> None:
        ts = Ts.fromPicoseconds(1)
        z = Ts.fromPicoseconds(0)
        with self.assertRaises(ZeroDivisionError):
            _ = ts.divide(z)

    def testLargeValuesNoOverflow(self) -> None:
        big = Ts.fromPicoseconds(10**18)  # ~ 11.57 days in ps
        out = big.divide(2)
        self.assertEqual(out.toPicoseconds(), 10**18 // 2)

if __name__ == "__main__":
    unittest.main(verbosity=2)
