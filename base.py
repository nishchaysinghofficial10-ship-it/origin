"""Research domain interface.

ORIGIN's core (controller, state, graph, budget, critic, reports) is
domain-agnostic. A ResearchDomain plugs in the domain-specific pieces:
how to decompose a question, generate competing hypotheses, design and
build executable experiments, and analyze results into evidence.

v0.1 ships one domain (algobench: algorithm benchmarking) because it is
computationally testable end to end. Physics simulations, materials,
economics etc. are additional domains behind this same interface.
"""
from __future__ import annotations

import abc
from pathlib import Path


class ResearchDomain(abc.ABC):
    name: str = "base"

    #: Which kind of measurement each metric is. `stats.TIMING` gets the full
    #: significance gate (host-specific, noisy); `stats.EXACT` is a
    #: deterministic count where any difference is real and no noise gate
    #: applies. A domain that measures only wall-clock time can leave this be.
    metric_kinds: dict = {"mean_s": "timing"}

    # ------------------------------------------------------------ planning
    @abc.abstractmethod
    def decompose(self, question: str, config: dict) -> dict:
        """Turn the question into a dynamic research tree (nested dict)."""

    def initial_assumptions(self) -> list[str]:
        return []

    def seed_knowledge(self, state) -> None:
        """Seed prior claims/sources (Phase 2 replaces this with live acquisition)."""

    # --------------------------------------------------------- hypotheses
    @abc.abstractmethod
    def generate_hypotheses(self, state) -> list:
        """Return new competing hypotheses (may be empty when exhausted)."""

    # -------------------------------------------------------- experiments
    @abc.abstractmethod
    def design_experiment(self, primary, pending: list, state) -> dict | None:
        """Design one experiment covering the primary hypothesis (and any
        co-testable pending hypotheses). Returns a design dict or None."""

    @abc.abstractmethod
    def write_runner(self, design: dict, exp_dir: Path) -> Path:
        """Generate a self-contained, versioned run.py inside exp_dir."""

    @abc.abstractmethod
    def analyze(self, record, result: dict, state) -> dict:
        """Turn raw results into evidence, graph updates, failure-log entries,
        status changes, and possibly *new* hypotheses. Returns a summary."""

    def replication_design(self, hypothesis, state) -> dict | None:
        return None

    def estimate_cost(self, design: dict) -> float:
        return 1.0

    # ------------------------------------------------------------- gaps
    def knowledge_gaps(self, state) -> list[str]:
        return []


_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    _REGISTRY[cls.name] = cls
    return cls


def get_domain(name: str) -> ResearchDomain:
    from . import algobench  # noqa: F401  (registers itself on import)
    from . import graphbench  # noqa: F401
    if name not in _REGISTRY:
        raise KeyError(f"Unknown research domain '{name}'. Available: {sorted(_REGISTRY)}")
    return _REGISTRY[name]()
