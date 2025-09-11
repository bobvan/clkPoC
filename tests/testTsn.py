import time

import pytest

from clkpoc.tsn import Tsn


@pytest.fixture
def frac_digs():
    return Tsn.fracDigs

@pytest.fixture
def units_per_second():
    return Tsn.unitsPerSecond

def test_from_parts(frac_digs: int, units_per_second: int):
    sec = 123
    frac = 456 * 10**(frac_digs - 3)  # Adjust fractional part to match fracDigs
    tsn = Tsn.fromParts(sec, frac)
    assert tsn.units == sec * units_per_second + frac

def test_from_picoseconds():
    total_ps = 1234567890123456
    tsn = Tsn.fromPicoseconds(total_ps)
    assert tsn.units == total_ps

def test_from_float(frac_digs: int, units_per_second: int):
    x = 123.456789
    tsn = Tsn.fromFloat(x)
    expected_units = int(round(x * units_per_second))
    assert tsn.units == expected_units

def test_from_strs(frac_digs: int, units_per_second: int):
    integer_str = "123"
    frac_str = "456789"
    tsn = Tsn.fromStrs(integer_str, frac_str)
    int_part = int(integer_str)
    sig_digs = frac_str[:frac_digs]
    frac_part = int(sig_digs) * 10**(frac_digs - len(sig_digs))
    expected_units = int_part * units_per_second + frac_part
    assert tsn == expected_units

def test_now(frac_digs: int, units_per_second: int):
    tsn = Tsn.now()
    current_time_ns = time.time_ns()
    expected_units = current_time_ns * 10**(frac_digs - 9)
    # Allow for clock to change between when Tsn.now() reads it and when we read it here
    assert abs(tsn.units - expected_units) < 10**(frac_digs - 3)

def test_to_picoseconds():
    total_ps = 1234567890123456
    tsn = Tsn.fromPicoseconds(total_ps)
    assert tsn.toPicoseconds() == total_ps
