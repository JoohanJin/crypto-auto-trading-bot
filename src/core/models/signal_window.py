from collections import deque
from dataclasses import dataclass, field

from src.core.models.signal import TradeSignal


@dataclass
class SignalWindow:
    """
    A modular sliding window that maintains signal history and running weighted sums.
    Provides O(1) access to consensus, density, and hold ratios.
    """

    window_ms: int
    _deque: deque[tuple[int, TradeSignal, float]] = field(default_factory=deque)
    _net_weight: float = 0.0
    _abs_weight: float = 0.0
    _hold_count: int = 0

    def add(self, timestamp: int, signal: TradeSignal, weight: float) -> None:
        """
        Add a new signal to the window and update running totals.
        """
        self._deque.append((timestamp, signal, weight))
        self._net_weight += weight
        self._abs_weight += abs(weight)
        if signal == TradeSignal.HOLD:
            self._hold_count += 1

    def prune(self, now: int) -> None:
        """
        Remove signals that have aged out of the window_ms duration.
        Updates running totals accordingly.
        """
        while self._deque and (now - self._deque[0][0] > self.window_ms):
            _, sig, weight = self._deque.popleft()
            self._net_weight -= weight
            self._abs_weight -= abs(weight)
            if sig == TradeSignal.HOLD:
                self._hold_count -= 1

    @property
    def consensus(self) -> float:
        """
        Returns the weighted consensus (-1.0 to 1.0).
        """
        if self._abs_weight == 0:
            return 0.0
        return self._net_weight / self._abs_weight

    @property
    def density(self) -> int:
        """
        Returns the number of signals currently in the window.
        """
        return len(self._deque)

    @property
    def hold_ratio(self) -> float:
        """
        Returns the ratio of HOLD signals in the window (0.0 to 1.0).
        """
        if self.density == 0:
            return 0.0
        return self._hold_count / self.density

    @property
    def oldest_timestamp(self) -> int | None:
        """
        Returns the timestamp of the oldest signal in the window.
        """
        return self._deque[0][0] if self._deque else None
