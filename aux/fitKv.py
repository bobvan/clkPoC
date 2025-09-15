from typing import List, Tuple

def fitKv(dacCodes: List[int], freqErrorPpb: List[float], f0Hz: float) -> Tuple[float, float, float]:
    """
    Returns (kvHzPerLsb, slopePpbPerCode, interceptPpb).
    kvHzPerLsb = f0Hz * slopePpbPerCode * 1e-9
    """
    n = len(dacCodes)
    if n != len(freqErrorPpb) or n < 2:
        raise ValueError("Need at least two matching samples of dacCodes and freqErrorPpb")

    xMean = sum(float(x) for x in dacCodes) / float(n)
    yMean = sum(freqErrorPpb) / float(n)

    sxx = 0.0
    sxy = 0.0
    for x, y in zip(dacCodes, freqErrorPpb):
        dx = float(x) - xMean
        dy = y - yMean
        sxx += dx * dx
        sxy += dx * dy

    if sxx == 0.0:
        raise ValueError("All DAC codes are identical; cannot fit a slope")

    slopePpbPerCode = sxy / sxx
    interceptPpb = yMean - slopePpbPerCode * xMean

    kvHzPerLsb = f0Hz * slopePpbPerCode * 1e-9
    return kvHzPerLsb, slopePpbPerCode, interceptPpb

# Example numbers
f0Hz = 10_000_000.0  # 10 MHz
dacCodes = [15000, 14000, 13200, 13000, 12000]
freqErrorPpb = [-10.0, -3.0, 0.0, 1, 2.5]

kvHzPerLsb, slopePpbPerCode, interceptPpb = fitKv(dacCodes, freqErrorPpb, f0Hz)
print("Kv (Hz/LSB):", kvHzPerLsb)
print("slope (ppb/code):", slopePpbPerCode)
print("intercept (ppb):", interceptPpb)
