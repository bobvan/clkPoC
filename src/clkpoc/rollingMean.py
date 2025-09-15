from collections import deque


class RollingMean:
    def __init__(self, maxSize: int) -> None:
        if maxSize <= 0:
            raise ValueError("maxSize must be positive")
        self.maxSize: int = maxSize
        self.buffer: deque[float] = deque()
        self.runningSum: float = 0.0

    def add(self, value: float) -> float:
        self.buffer.append(value)
        self.runningSum += value
        if len(self.buffer) > self.maxSize:
            oldest = self.buffer.popleft()
            self.runningSum -= oldest
        # current window may be smaller than maxSize until filled
        return self.runningSum / float(len(self.buffer))

    def mean(self) -> float | None:
        if not self.buffer:
            return None
        return self.runningSum / float(len(self.buffer))

    def clear(self) -> None:
        self.buffer.clear()
        self.runningSum = 0.0
