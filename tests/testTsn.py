import time

import pytest

from clkpoc.tsn import Tsn


@pytest.fixture
def frac_digs() -> int:
    return Tsn.fracDigs

@pytest.fixture
def units_per_second() -> int:
    return Tsn.unitsPerSecond

@pytest.fixture
def tsn_instance():
    # Create a Tsn instance for testing
    return Tsn.fromParts(10, 123456)  # Example: 10.123456 seconds

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

def test_add(frac_digs: int, units_per_second: int):
    tsn1 = Tsn.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    tsn2 = Tsn.fromParts(5, 250 * 10**(frac_digs - 3))   # 5.250 seconds
    result = tsn1.add(tsn2)
    expected_units = tsn1.units + tsn2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (15, 750 * 10**(frac_digs - 3))  # 15.750 seconds

def test_sub(frac_digs: int, units_per_second: int):
    tsn1 = Tsn.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    tsn2 = Tsn.fromParts(5, 250 * 10**(frac_digs - 3))   # 5.250 seconds
    result = tsn1.sub(tsn2)
    expected_units = tsn1.units - tsn2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (5, 250 * 10**(frac_digs - 3))  # 5.250 seconds

def test_add_negative(frac_digs: int, units_per_second: int):
    tsn1 = Tsn.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    tsn2 = Tsn.fromParts(-5, -250 * 10**(frac_digs - 3)) # -5.250 seconds
    result = tsn1.add(tsn2)
    expected_units = tsn1.units + tsn2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (5, 250 * 10**(frac_digs - 3))  # 5.250 seconds

def test_sub_negative(frac_digs: int, units_per_second: int):
    tsn1 = Tsn.fromParts(10, 500 * 10**(frac_digs - 3))  # 10.500 seconds
    tsn2 = Tsn.fromParts(-5, -250 * 10**(frac_digs - 3)) # -5.250 seconds
    result = tsn1.sub(tsn2)
    expected_units = tsn1.units - tsn2.units
    assert result.units == expected_units
    assert result.toFloorParts() == (15, 750 * 10**(frac_digs - 3))  # 15.750 seconds

def test_toDecimal(frac_digs: int, units_per_second: int):
    # Test case 1: Exact value with full precision
    tsn = Tsn.fromParts(10, 123 * 10**(frac_digs - 3))  # 10.123 seconds
    assert tsn.toDecimal(frac_digs) == "10.123000000000"

    # Test case 2: Rounding down
    tsn = Tsn.fromParts(10, 123456 * 10**(frac_digs - 6))  # 10.123456 seconds
    assert tsn.toDecimal(3) == "10.123"  # Rounded to 3 places

    # Test case 3: Rounding up
    tsn = Tsn.fromParts(10, 123456 * 10**(frac_digs - 6))  # 10.123456 seconds
    assert tsn.toDecimal(5) == "10.12346"  # Rounded to 5 places

    # Test case 4: Round-to-even (tie-breaking)
    tsn = Tsn.fromParts(10, 125000 * 10**(frac_digs - 6))  # 10.125000 seconds
    assert tsn.toDecimal(2) == "10.12"  # Round-to-even rule applies

    tsn = Tsn.fromParts(10, 135000 * 10**(frac_digs - 6))  # 10.135000 seconds
    assert tsn.toDecimal(2) == "10.14"  # Round-to-even rule applies

    # Test case 5: Zero fractional part
    tsn = Tsn.fromParts(10, 0)  # 10.000 seconds
    assert tsn.toDecimal(frac_digs) == "10.000000000000"

    # Test case 6: Negative value
    tsn = Tsn.fromParts(-10, -123 * 10**(frac_digs - 3))  # -10.123 seconds
    assert tsn.toDecimal(frac_digs) == "-10.123000000000"

    # Test case 7: Zero value
    tsn = Tsn.fromParts(0, 0)  # 0.000 seconds
    assert tsn.toDecimal(frac_digs) == "0.000000000000"

    # Test case 8: Invalid places argument
    with pytest.raises(ValueError, match="places must be between 0 and"):
        tsn.toDecimal(-1)

    with pytest.raises(ValueError, match="places must be between 0 and"):
        tsn.toDecimal(frac_digs + 1)
