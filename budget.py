"""ORIGIN research economy.

ORIGIN operates under finite resources. Every investigation must justify its
cost, which turns the system into an active research agent rather than an
endless browser.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class Budget:
    experiments_total: int = 12
    experiments_used: int = 0
    compute_seconds_total: float = 1800.0
    compute_seconds_used: float = 0.0
    searches_total: int = 0        # reserved for live acquisition (deferred)
    searches_used: int = 0
    elapsed_seconds_total: float = 0.0   # 0 = unlimited mission wall time
    elapsed_seconds_used: float = 0.0
    provider_calls_total: int = 0        # LLM provider call cap (0 = brain disabled/unlimited mock)
    provider_calls_used: int = 0
    retries_total: int = 8               # global failed-execution retry cap
    retries_used: int = 0

    def can_run_experiment(self, est_seconds: float = 0.0) -> bool:
        if self.experiments_used >= self.experiments_total:
            return False
        return (self.compute_seconds_used + est_seconds) <= self.compute_seconds_total

    def charge_experiment(self, seconds: float) -> None:
        self.experiments_used += 1
        self.compute_seconds_used += seconds

    def can_call_provider(self) -> bool:
        return (self.provider_calls_total <= 0
                or self.provider_calls_used < self.provider_calls_total)

    def charge_provider_call(self) -> None:
        self.provider_calls_used += 1

    def can_retry(self) -> bool:
        return self.retries_used < self.retries_total

    def charge_retry(self) -> None:
        self.retries_used += 1

    def charge_elapsed(self, seconds: float) -> None:
        self.elapsed_seconds_used += seconds

    def exhausted_reason(self) -> str | None:
        """First exhausted dimension, or None if work may continue."""
        if self.experiments_used >= self.experiments_total:
            return f"experiment budget exhausted ({self.experiments_used}/{self.experiments_total})"
        if self.compute_seconds_used >= self.compute_seconds_total:
            return (f"compute budget exhausted "
                    f"({self.compute_seconds_used:.1f}/{self.compute_seconds_total:.0f}s)")
        if 0 < self.elapsed_seconds_total <= self.elapsed_seconds_used:
            return (f"mission wall-time budget exhausted "
                    f"({self.elapsed_seconds_used:.0f}/{self.elapsed_seconds_total:.0f}s)")
        return None

    def remaining(self) -> dict:
        return {
            "experiments": self.experiments_total - self.experiments_used,
            "compute_seconds": round(self.compute_seconds_total - self.compute_seconds_used, 1),
            "searches": self.searches_total - self.searches_used,
            "provider_calls": (self.provider_calls_total - self.provider_calls_used
                               if self.provider_calls_total else "unlimited"),
            "retries": self.retries_total - self.retries_used,
        }

    def fraction_used(self) -> float:
        parts = []
        if self.experiments_total:
            parts.append(self.experiments_used / self.experiments_total)
        if self.compute_seconds_total:
            parts.append(self.compute_seconds_used / self.compute_seconds_total)
        return max(parts) if parts else 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Budget":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})
