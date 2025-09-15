# Nomenclature

## Timescales

### GNSS

* Has PPS
* UTC derived from GPS time by F9T
* PPS is wired to TICC channel B

### Disciplined Oscillator

* Nominaly 10 MHz
* Also divided by 10e7 to get PPS
* PPS is wired to TICC channel A
* Steerable by DAC

### Reference Oscillator

* Nominally ~10000000.005 Hz
* Continuously changing phase offset relative to disciplined oscillator to
  remove common mode errors
* Drives TICC as reference clock
* Provides tansfer timescale for phase error measurement

### Capture

* Host clock when timestamp was captured
* Likely UTC, but could be steered or even discontinuous due to host time daemon action

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
