import time

import pytest

from clkpoc.tsTypes import Ts


@pytest.fixture
def frac_digs() -> int:
    return Ts.fracDigs

@pytest.fixture
def units_per_second() -> int:
    return Ts.unitsPerSecond

@pytest.fixture
def ts_instance():
    # Create a Ts instance for testing
    return Ts.fromParts(10, 123456)  # Example: 10.123456 seconds

def test_from_parts(frac_digs: int, units_per_second: int):
    sec = 123
    frac = 456 * 10**(frac_digs - 3)  # Adjust fractional part to match fracDigs
    ts = Ts.fromParts(sec, frac)
    assert ts.units == sec * units_per_second + frac

def test_from_picoseconds():
    total_ps = 1234567890123456
    ts = Ts.fromPicoseconds(total_ps)
    assert ts.units == total_ps

def test_from_float(frac_digs: int, units_per_second: int):
    x = 123.456789
    ts = Ts.fromFloat(x)
    expected_units = int(round(x * units_per_second))
    assert ts.units == expected_units

def test_from_strs(frac_digs: int, units_per_second: int):
    integer_str = "123"
    frac_str = "456789"
    ts = Ts.fromStrs(integer_str, frac_str)
    int_part = int(integer_str)
    sig_digs = frac_str[:frac_digs]
    frac_part = int(sig_digs) * 10**(frac_digs - len(sig_digs))
    expected_units = int_part * units_per_second + frac_part
    assert ts.units == expected_units

def test_now(frac_digs: int, units_per_second: int):
    ts = Ts.now()
    current_time_ns = time.time_ns()
    expected_units = current_time_ns * 10**(frac_digs - 9)
    # Allow for clock to change between when Ts.now() reads it and when we read it here
    assert abs(ts.units - expected_units) < 10**(frac_digs - 3)

def test_to_picoseconds():
    total_ps = 1234567890123456
    ts = Ts.fromPicoseconds(total_ps)
    assert ts.toPicoseconds() == total_ps

def test_add(frac_digs: int, units_per_second: int):
    ts1 = Ts.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    ts2 = Ts.fromParts(5, 250 * 10**(frac_digs - 3))   # 5.250 seconds
    result = ts1.add(ts2)
    expected_units = ts1.units + ts2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (15, 750 * 10**(frac_digs - 3))  # 15.750 seconds

def test_sub(frac_digs: int, units_per_second: int):
    ts1 = Ts.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    ts2 = Ts.fromParts(5, 250 * 10**(frac_digs - 3))   # 5.250 seconds
    result = ts2.subFrom(ts1)
    expected_units = ts1.units - ts2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (5, 250 * 10**(frac_digs - 3))  # 5.250 seconds

def test_add_negative(frac_digs: int, units_per_second: int):
    ts1 = Ts.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    ts2 = Ts.fromParts(-5, -250 * 10**(frac_digs - 3)) # -5.250 seconds
    result = ts1.add(ts2)
    expected_units = ts1.units + ts2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (5, 250 * 10**(frac_digs - 3))  # 5.250 seconds

def test_sub_negative(frac_digs: int, units_per_second: int):
    ts1 = Ts.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    ts2 = Ts.fromParts(-5, -250 * 10**(frac_digs - 3)) # -5.250 seconds
    result = ts2.subFrom(ts1)
    expected_units = ts1.units - ts2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (15, 750 * 10**(frac_digs - 3))  # 15.750 seconds

def test_toDecimal(frac_digs: int, units_per_second: int):
    # Test case 1: Exact value with full precision
    ts = Ts.fromParts(10, 123 * 10**(frac_digs - 3))  # 10.123 seconds
    assert ts.toDecimal(frac_digs) == "10.123000000000"

    # Test case 2: Rounding down
    ts = Ts.fromParts(10, 123456 * 10**(frac_digs - 6))  # 10.123456 seconds
    assert ts.toDecimal(3) == "10.123"  # Rounded to 3 places

    # Test case 3: Rounding up
    ts = Ts.fromParts(10, 123456 * 10**(frac_digs - 6))  # 10.123456 seconds
    assert ts.toDecimal(5) == "10.12346"  # Rounded to 5 places

    # Test case 4: Round-to-even (tie-breaking)
    ts = Ts.fromParts(10, 125000 * 10**(frac_digs - 6))  # 10.125000 seconds
    assert ts.toDecimal(2) == "10.12"  # Round-to-even rule applies

    ts = Ts.fromParts(10, 135000 * 10**(frac_digs - 6))  # 10.135000 seconds
    assert ts.toDecimal(2) == "10.14"  # Round-to-even rule applies

    # Test case 5: Zero fractional part
    ts = Ts.fromParts(10, 0)  # 10.000 seconds
    assert ts.toDecimal(frac_digs) == "10.000000000000"

    # Test case 6: Negative value
    ts = Ts.fromParts(-10, -123 * 10**(frac_digs - 3))  # -10.123 seconds
    assert ts.toDecimal(frac_digs) == "-10.123000000000"

    # Test case 7: Zero value
    ts = Ts.fromParts(0, 0)  # 0.000 seconds
    assert ts.toDecimal(frac_digs) == "0.000000000000"

    # Test case 8: Invalid places argument
    with pytest.raises(ValueError, match="places must be between 0 and"):
        ts.toDecimal(-1)

    with pytest.raises(ValueError, match="places must be between 0 and"):
        ts.toDecimal(frac_digs + 1)


def test_comparison_operators() -> None:
    earlier = Ts.fromParts(1, 0)
    later = Ts.fromParts(1, 1)
    assert earlier < later
    assert earlier <= later
    assert earlier <= earlier
    assert later > earlier
    assert later >= earlier
    assert later >= later
    with pytest.raises(TypeError):
        _ = earlier < 1  # type: ignore[operator]

