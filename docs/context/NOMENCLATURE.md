# Nomenclature

## Timescales

Every clock is bound to a timescale for counting its ticks.
Thus referencing a "timestamp taken on a clock" implies that the
timestamp was taken on the clock's timescale.
This shorthand is most often used with the reference oscillator and
capture (host) clocks.

### GNSS

* Abbreviated "GNS", "gns", or "Gns" in identifiers
* Has PPS
* UTC derived from GPS time by F9T
* PPS is wired to TICC channel B

### Disciplined Oscillator

* Abbreviated "DSC", "dsc", or "Dsc" in identifiers
* Nominaly 10 MHz
* Also divided by 10e7 to get PPS
* PPS is wired to TICC channel A
* Steerable by DAC

### Reference Oscillator

* Abbreviated "REF", "ref", or "Ref" in identifiers
* Nominally ~10000000.005 Hz
* Continuously changing phase offset relative to disciplined oscillator to
  remove common mode errors
* Drives TICC as reference clock
* Provides tansfer timescale for phase error measurement

### Capture

* Abbreviated "CAP", "cap", or "Cap" in identifiers
* Host clock when timestamp was captured
* Likely UTC, but could be steered or even discontinuous due to host time daemon action
  * Hence unsuitable for long-term observation
  * Limtitations judged acceptable for the convenience of a human-relatable scale

## Messaging

* Topics, publish, subscribe

## Subtraction

* difference = minuend - subtrahend
* difference = subtrahend.subFrom(minuend)
* elapsed = finish - start
* elapsed = start.subFrom(finish)
* elapsed = prevTs.subFrom(thisTs)
* Avoid: value.sub() for ambiguous ordering, confusion with subscribe

## Statistics

* Absolute error: abs(measuredValue - trueValue)
* Signed error: measuredValue - trueValue
  * Dsc deviation = Dsc timestamp - Gns timestamp
* Relative error: (measuredValue - trueValue) / trueValue
* Avoid: "delta" for ambiguous sign
