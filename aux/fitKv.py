#!/usr/bin/env python3

def fitKv(dacCodes: list[int], freqErrorPpb: list[float],
        f0Hz: float) -> tuple[float, float, float, float | None, float]:
    """
    Returns (kvHzPerLsb, slopePpbPerCode, interceptPpb, codeIntercept, rSquared).
    kvHzPerLsb = f0Hz * slopePpbPerCode * 1e-9
    """
    n = len(dacCodes)
    if n != len(freqErrorPpb) or n < 2:
        raise ValueError("Need at least two matching samples of dacCodes and freqErrorPpb")

    xMean = sum(float(x) for x in dacCodes) / float(n)
    yMean = sum(freqErrorPpb) / float(n)

    sxx = 0.0
    sxy = 0.0
    ssTot = 0.0
    for x, y in zip(dacCodes, freqErrorPpb, strict=False):
        dx = float(x) - xMean
        dy = y - yMean
        sxx += dx * dx
        sxy += dx * dy
        ssTot += dy * dy

    if sxx == 0.0:
        raise ValueError("All DAC codes are identical; cannot fit a slope")

    slopePpbPerCode = sxy / sxx
    interceptPpb = yMean - slopePpbPerCode * xMean

    if slopePpbPerCode == 0.0:
        codeIntercept = None
    else:
        codeIntercept = -interceptPpb / slopePpbPerCode

    ssRes = 0.0
    for x, y in zip(dacCodes, freqErrorPpb, strict=False):
        yHat = slopePpbPerCode * float(x) + interceptPpb
        resid = y - yHat
        ssRes += resid * resid

    if ssTot == 0.0:
        rSquared = 1.0 if ssRes == 0.0 else 0.0
    else:
        rSquared = 1.0 - ssRes / ssTot

    kvHzPerLsb = f0Hz * slopePpbPerCode * 1e-9
    return kvHzPerLsb, slopePpbPerCode, interceptPpb, codeIntercept, rSquared

# Example numbers
f0Hz = 10_000_000.0  # 10 MHz
# clkPoC1 ~ 9/10/2025
#dacCodes = [15000, 14000, 13200, 13000, 12000]
#freqErrorPpb = [-10.0, -3.0, 0.0, 1, 2.5]
# clkPoC1 9/18/2025
dacCodes = [13000, 12000, 11000, 10000, 9000, 8000, 7000]
freqErrorPpb = [-19.3, -13.6, -7.9, -2.3, 3.5, 9.3, 14.8]

kvHzPerLsb, slopePpbPerCode, interceptPpb, codeIntercept, rSquared = fitKv(dacCodes, freqErrorPpb, f0Hz)  # noqa: E501
print("Kv (Hz/LSB):", kvHzPerLsb)
print("slope (ppb/code):", slopePpbPerCode)
print("intercept (ppb):", interceptPpb)
print("code intercept (DAC code @ 0 ppb):", codeIntercept)
print("R^2:", rSquared)
