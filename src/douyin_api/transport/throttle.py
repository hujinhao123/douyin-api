"""Conservative pacing for a single browser session."""

from __future__ import annotations

import asyncio
import random
import time


class Throttle:
    """Serialize requests, add human-scale gaps, and cool down after blocks."""

    def __init__(
        self,
        *,
        min_interval: float = 1.2,
        jitter: float = 0.8,
        cooldown_base: float = 15.0,
        cooldown_max: float = 300.0,
    ) -> None:
        self.min_interval = max(0.0, float(min_interval))
        self.jitter = max(0.0, float(jitter))
        self.cooldown_base = max(1.0, float(cooldown_base))
        self.cooldown_max = max(self.cooldown_base, float(cooldown_max))
        self._last_finished = 0.0
        self._cooldown_until = 0.0
        self._blocked_streak = 0
        self._lock = asyncio.Lock()

    @property
    def blocked_streak(self) -> int:
        return self._blocked_streak

    @property
    def cooling_down_for(self) -> float:
        return max(0.0, self._cooldown_until - time.monotonic())

    async def wait(self) -> None:
        """Wait until a request may start."""
        await self.acquire()
        self.release()

    async def acquire(self) -> None:
        """Acquire the request gate and keep it through the network call."""
        await self._lock.acquire()
        now = time.monotonic()
        if now < self._cooldown_until:
            await asyncio.sleep(self._cooldown_until - now)
            now = time.monotonic()
        gap = self.min_interval + random.uniform(0.0, self.jitter)
        remaining = gap - (now - self._last_finished)
        if remaining > 0:
            await asyncio.sleep(remaining)

    def release(self) -> None:
        """Finish the current request and release the gate."""
        self.mark_finished()
        self._lock.release()

    def mark_finished(self) -> None:
        self._last_finished = time.monotonic()

    def penalise(self, retry_after: float | None = None) -> float:
        self._blocked_streak += 1
        if retry_after is None:
            delay = min(
                self.cooldown_max,
                self.cooldown_base * (2 ** (self._blocked_streak - 1)),
            )
            delay *= 1.0 + random.uniform(0.0, 0.25)
        else:
            delay = max(1.0, min(self.cooldown_max, float(retry_after)))
        self._cooldown_until = max(self._cooldown_until, time.monotonic() + delay)
        return delay

    def reward(self) -> None:
        if self._blocked_streak:
            self._blocked_streak -= 1

    def reset(self) -> None:
        self._blocked_streak = 0
        self._cooldown_until = 0.0
