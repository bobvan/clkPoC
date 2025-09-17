# Status

## Modes

### Startup

Enter: From initialization
Action: Wait for first PPS pairs
Exit to Stepping: First PPS pair shows DSC deviation over CoarseThreshold
Exit to CoarseTune: First PPS pair shows DSC deviation < CoarseThreshold and > FineThreshold
Exit to FineTune: First PPS pair shows DSC deviation < FineThreshold, lucky day, assumes we have history and restored DAC setting to last known value so freq is aprroximately right

### Step

Enter: DSC deviation above CoarseThreshold
Action: Arm TADD
Exit to CoarseTune: PPS pair arrives below CoarseThreshold but above FineThreshold, warning if taking too long, possibly repeat
Exit to FineTune: PPS pair arrives below CoarseThreshold, lucky day, assumes we have history and restored DAC setting to last known value so freq is approximately right

### CoarseTune

Enter: DSC deviation below CoarseThreshold
Action: Propmptly steer DSC frequency so it's close to phase aligned with GNS
Exit to FineTune: Repeated DSC deviation below FineThreshold
Exit to Stepping: Repeated DSC deviation above CoarseThreshold

### FineTune

Enter: DSC deviation below FineThreshold
Action: Gently steer DSC frequency to precisely align phase with GNS
Exit to CoarseTune: Consecutive clinkers above FineThreshold, with warning
Exit to Stepping: Repeated DSC deviation above CoarseThreshold, with warning
