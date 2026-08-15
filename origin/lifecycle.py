"""Mission lifecycle state machine (v1.0).

Explicit states, legal-transition validation, logged transitions, distinct
terminal states, and stop reasons. v0.1 projects (loose phase strings) are
migrated on load via MIGRATION.
"""
from __future__ import annotations

import time

# ---------------------------------------------------------------- states
CREATED = "CREATED"
VALIDATING = "VALIDATING"
PLANNING = "PLANNING"
ACQUIRING_EVIDENCE = "ACQUIRING_EVIDENCE"
FORMING_HYPOTHESES = "FORMING_HYPOTHESES"
SELECTING_NEXT_ACTION = "SELECTING_NEXT_ACTION"
DESIGNING_EXPERIMENT = "DESIGNING_EXPERIMENT"
EXECUTING = "EXECUTING"
ANALYZING = "ANALYZING"
CRITICIZING = "CRITICIZING"
REPLICATING = "REPLICATING"
FALSIFYING = "FALSIFYING"
UPDATING_KNOWLEDGE = "UPDATING_KNOWLEDGE"
PAUSED = "PAUSED"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"

TERMINAL = {COMPLETED, FAILED, CANCELLED}
NON_TERMINAL = {CREATED, VALIDATING, PLANNING, ACQUIRING_EVIDENCE,
                FORMING_HYPOTHESES, SELECTING_NEXT_ACTION,
                DESIGNING_EXPERIMENT, EXECUTING, ANALYZING, CRITICIZING,
                REPLICATING, FALSIFYING, UPDATING_KNOWLEDGE, PAUSED}
ALL = TERMINAL | NON_TERMINAL

TRANSITIONS: dict[str, set[str]] = {
    CREATED: {VALIDATING},
    VALIDATING: {PLANNING, FAILED},
    PLANNING: {ACQUIRING_EVIDENCE, FORMING_HYPOTHESES, CRITICIZING},
    ACQUIRING_EVIDENCE: {ACQUIRING_EVIDENCE, FORMING_HYPOTHESES,
                         SELECTING_NEXT_ACTION},
    FORMING_HYPOTHESES: {SELECTING_NEXT_ACTION, CRITICIZING, FAILED},
    SELECTING_NEXT_ACTION: {DESIGNING_EXPERIMENT, CRITICIZING, COMPLETED},
    DESIGNING_EXPERIMENT: {EXECUTING, SELECTING_NEXT_ACTION, CRITICIZING},
    EXECUTING: {ANALYZING, UPDATING_KNOWLEDGE, FAILED},
    ANALYZING: {UPDATING_KNOWLEDGE},
    UPDATING_KNOWLEDGE: {SELECTING_NEXT_ACTION, CRITICIZING},
    CRITICIZING: {REPLICATING, FALSIFYING, COMPLETED},
    REPLICATING: {UPDATING_KNOWLEDGE, CRITICIZING},
    FALSIFYING: {UPDATING_KNOWLEDGE, CRITICIZING},
    PAUSED: set(),          # resolved via resume(): restores paused_from
    COMPLETED: set(), FAILED: set(), CANCELLED: set(),
}

# v0.1 loose phase strings -> v1.0 states (applied on load)
MIGRATION = {
    "initialized": CREATED, "planned": FORMING_HYPOTHESES,
    "investigating": SELECTING_NEXT_ACTION, "criticized": CRITICIZING,
    "budget_exhausted": CRITICIZING, "complete": COMPLETED,
}


class IllegalTransition(Exception):
    pass


def migrate_phase(phase: str) -> str:
    return phase if phase in ALL else MIGRATION.get(phase, CREATED)


def advance(state, to: str, reason: str = "") -> None:
    """Validated, logged phase transition. Raises IllegalTransition."""
    cur = state.meta.get("phase", CREATED)
    if to not in ALL:
        raise IllegalTransition(f"unknown state {to!r}")
    if cur in TERMINAL:
        raise IllegalTransition(f"mission is terminal ({cur}); cannot move to {to}")
    allowed = TRANSITIONS.get(cur, set())
    # PAUSED and CANCELLED are reachable from any non-terminal state.
    if to not in allowed and to not in {PAUSED, CANCELLED}:
        raise IllegalTransition(f"{cur} -> {to} is not a legal transition")
    if to == PAUSED:
        state.meta["paused_from"] = cur
    state.meta["phase"] = to
    state.log_event("transition", f"{cur} -> {to}" + (f" ({reason})" if reason else ""))
    if to in TERMINAL:
        state.meta["stop_reason"] = reason or "unspecified"
        state.meta["ended_at"] = time.time()
        state.log_event("stopped", f"Mission {to}: {state.meta['stop_reason']}")


def resume(state) -> None:
    if state.meta.get("phase") != PAUSED:
        return
    back = state.meta.pop("paused_from", SELECTING_NEXT_ACTION)
    state.meta["phase"] = back
    state.log_event("transition", f"PAUSED -> {back} (resumed)")
