"""Bounded autonomy (v1.5).

ORIGIN can continue a mission across many short sessions, restarts and pauses.
It becomes autonomous only inside explicit, inspectable, operator-controlled
limits. This module adds four things and nothing else:

    WorkItem   a durable, schema-validated record of a PERMITTED action
    Lease      single-writer protection for one mission directory
    Policy     a deterministic chooser that records why it chose
    tick()     one bounded, checkpointed, restart-safe step

What this module deliberately does not do: it never executes anything itself.
Every action is dispatched to the existing engine (`ResearchController`,
`ExperimentEngine`, `web_evidence`, `CriticEngine`), so every existing gate —
sandbox policy, budgets, proposal validation, URL/robots policy, provenance
rules, replication requirements — stays authoritative. Autonomy chooses *which*
permitted action happens next; it cannot invent a new kind of action, widen a
limit, or accept its own output as evidence.
"""
from __future__ import annotations

import json
import os
import socket
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .schema import validate

AUTONOMY_SCHEMA_VERSION = 1
POLICY_VERSION = "1.5.0"

# ---------------------------------------------------------------- statuses
QUEUED = "queued"
CLAIMED = "claimed"            # a tick took it; outcome not yet known
DONE = "done"
FAILED = "failed"              # terminal: not retryable, or retries exhausted
DEFERRED = "deferred"          # retry scheduled, `not_before` set
BLOCKED = "blocked"            # dependency unmet
NEEDS_APPROVAL = "needs_approval"
CANCELLED = "cancelled"
INTERRUPTED = "interrupted"    # claimed, then the process died: outcome unknown
ITEM_STATES = (QUEUED, CLAIMED, DONE, FAILED, DEFERRED, BLOCKED,
               NEEDS_APPROVAL, CANCELLED, INTERRUPTED)
OPEN_STATES = (QUEUED, DEFERRED, BLOCKED, NEEDS_APPROVAL)

# ------------------------------------------------------------ action types
# Every action maps to an existing, already-gated ORIGIN capability. There is
# no "run arbitrary code" action and no way to add one from data.
PLAN_MISSION = "plan_mission"
FORM_HYPOTHESES = "form_hypotheses"
RUN_EXPERIMENT = "run_experiment"
CRITICISE = "criticise"
RETRIEVE_SOURCE = "retrieve_source"
REVIEW_CONFLICT = "review_conflict"
GENERATE_REPORT = "generate_report"
AWAIT_APPROVAL = "await_operator_approval"
ACTION_TYPES = (PLAN_MISSION, FORM_HYPOTHESES, RUN_EXPERIMENT, CRITICISE,
                RETRIEVE_SOURCE, REVIEW_CONFLICT, GENERATE_REPORT,
                AWAIT_APPROVAL)

# Actions that ALWAYS reach outside the machine. `requires_network` is forced on
# for these; they are never scheduled unless the operator enabled network access
# for the run, and the plan shows them before they run.
NETWORK_ACTIONS = (RETRIEVE_SOURCE,)
# Actions that MAY call a provider — only when the mission is configured with a
# live brain. The seeder decides per mission and sets `requires_provider`
# explicitly, so a mock/offline mission is not blocked by a flag it never needed.
PROVIDER_CAPABLE_ACTIONS = (FORM_HYPOTHESES,)

# ---------------------------------------------------------------- stop reasons
COMPLETED = "completed"
PAUSED_BY_OPERATOR = "paused_by_operator"
BUDGET_EXHAUSTED = "budget_exhausted"
TIME_LIMIT = "time_limit_reached"
STEP_LIMIT = "step_limit_reached"
AWAITING_OPERATOR = "awaiting_operator_input"
NO_WORK = "no_permitted_work_remaining"
RETRY_PENDING = "retry_backoff_pending"
UNSAFE_STATE = "unsafe_or_invalid_state"
FAILURE_LIMIT = "consecutive_failure_limit_reached"
CANCELLED_STOP = "cancelled"

WORK_ITEM_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["id", "action", "status", "priority", "created_at",
                 "idempotency_key", "params", "reason"],
    "properties": {
        "id": {"type": "string", "minLength": 4, "maxLength": 60},
        "action": {"type": "string", "enum": list(ACTION_TYPES)},
        "status": {"type": "string", "enum": list(ITEM_STATES)},
        "priority": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "created_at": {"type": "number"},
        "depends_on": {"type": "array", "maxItems": 8,
                       "items": {"type": "string", "maxLength": 60}},
        "attempts": {"type": "integer", "minimum": 0, "maximum": 100},
        "not_before": {"type": "number", "minimum": 0.0},
        "cost_estimate": {"type": "number", "minimum": 0.0, "maximum": 100.0},
        "requires_network": {"type": "boolean"},
        "requires_provider": {"type": "boolean"},
        "requires_approval": {"type": "boolean"},
        "approved_by": {"type": "string", "maxLength": 80},
        "idempotency_key": {"type": "string", "minLength": 4, "maxLength": 80},
        "params": {"type": "object"},
        "reason": {"type": "string", "minLength": 3, "maxLength": 300},
        "decision_ref": {"type": "string", "maxLength": 60},
        "result_ref": {"type": "string", "maxLength": 300},
        "last_error": {"type": "string", "maxLength": 400},
        "updated_at": {"type": "number"},
    },
}


class AutonomyError(Exception):
    """Autonomy could not proceed safely."""


class LeaseHeld(AutonomyError):
    """Another process holds this mission's lease."""


@dataclass
class WorkItem:
    id: str
    action: str
    reason: str
    idempotency_key: str
    status: str = QUEUED
    priority: float = 0.5
    created_at: float = field(default_factory=time.time)
    updated_at: float = 0.0
    depends_on: list = field(default_factory=list)
    attempts: int = 0
    not_before: float = 0.0
    cost_estimate: float = 1.0
    requires_network: bool = False
    requires_provider: bool = False
    requires_approval: bool = False
    approved_by: str = ""
    params: dict = field(default_factory=dict)
    decision_ref: str = ""
    result_ref: str = ""
    last_error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "WorkItem":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


def new_item(action: str, reason: str, **kw) -> WorkItem:
    """Build a work item with a derived idempotency key.

    The key is what makes a repeated scheduler tick safe: two items describing
    the same action on the same target collapse to one, so a duplicate tick
    cannot double-run an experiment or double-charge a budget.
    """
    params = kw.pop("params", {})
    key = kw.pop("idempotency_key", None) or _derive_key(action, params)
    item = WorkItem(id="wi_" + uuid.uuid4().hex[:10], action=action,
                    reason=reason, idempotency_key=key, params=params, **kw)
    item.requires_network = item.requires_network or action in NETWORK_ACTIONS
    return item


def _derive_key(action: str, params: dict) -> str:
    import hashlib
    blob = json.dumps({"a": action, "p": params}, sort_keys=True, default=str)
    return f"{action}:{hashlib.sha256(blob.encode()).hexdigest()[:16]}"


def validate_item(raw: dict) -> list[str]:
    """Schema + policy validation. Returns problems ([] == admissible)."""
    problems = validate(raw, WORK_ITEM_SCHEMA, path="work_item")
    if problems:
        return problems
    action = raw["action"]
    params = raw.get("params", {})
    if action == RETRIEVE_SOURCE:
        url = params.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            problems.append("retrieve_source requires an https url parameter; "
                            "autonomy may not widen the URL policy")
    if action == RUN_EXPERIMENT:
        # A work item may name a hypothesis to test. It may NOT carry a design:
        # designs come from the domain and are re-validated by the sandbox.
        for banned in ("design", "command", "code", "runner", "argv"):
            if banned in params:
                problems.append(
                    f"run_experiment work items may not carry {banned!r}: "
                    f"experiment code is generated by the domain and validated "
                    f"by the sandbox, never supplied as data")
    return problems


# ------------------------------------------------------------------ lease
@dataclass
class Lease:
    owner: str
    pid: int
    host: str
    acquired_at: float
    mission: str

    def to_dict(self) -> dict:
        return asdict(self)


class MissionLease:
    """Single-writer protection for one mission directory.

    Acquisition is atomic (`O_CREAT | O_EXCL`). A lease is never stolen
    automatically, however old it looks: a stale lease and a live one are
    indistinguishable from outside, and guessing wrong means two processes
    mutating one mission. Recovery is an explicit operator action
    (`origin autonomy recover-lock`) and is audited.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / "autonomy" / "mission.lease"
        self.owner = ""

    def read(self) -> dict | None:
        try:
            return json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def acquire(self, owner: str | None = None) -> Lease:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        owner = owner or f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
        lease = Lease(owner=owner, pid=os.getpid(), host=socket.gethostname(),
                      acquired_at=time.time(), mission=str(self.root))
        payload = json.dumps(lease.to_dict(), indent=2).encode()
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            held = self.read() or {}
            age = time.time() - float(held.get("acquired_at", 0) or 0)
            raise LeaseHeld(
                f"mission is leased by {held.get('owner', 'an unknown owner')} "
                f"(pid {held.get('pid', '?')} on {held.get('host', '?')}, held "
                f"{age:.0f}s). Another autonomy process may be running. If you "
                f"are certain it is not, inspect it with 'origin autonomy "
                f"status' and release it deliberately with 'origin autonomy "
                f"recover-lock --force'. ORIGIN never steals a lease "
                f"automatically: a stale lease and a live one look identical "
                f"from here.")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            self.path.unlink(missing_ok=True)
            raise
        self.owner = owner
        return lease

    def release(self, owner: str | None = None) -> bool:
        held = self.read()
        if held is None:
            return False
        if owner and held.get("owner") != owner:
            return False
        self.path.unlink(missing_ok=True)
        return True

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release(self.owner)
        return False


# ------------------------------------------------------------------ store
class AutonomyStore:
    """Durable autonomy state: queue, decisions, run counters.

    Stored under the mission root as `autonomy/state.json` (queue + counters)
    and `autonomy/decisions.jsonl` (append-only). Both are root-relative and
    contain no absolute paths and no secrets.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.dir = self.root / "autonomy"
        self.path = self.dir / "state.json"
        self.decisions_path = self.dir / "decisions.jsonl"
        self.items: dict[str, WorkItem] = {}
        self.counters: dict = {
            "ticks": 0, "actions_completed": 0, "actions_failed": 0,
            "consecutive_failures": 0, "idle_ticks": 0,
            "retrievals": 0, "provider_calls": 0}
        self.meta: dict = {"schema_version": AUTONOMY_SCHEMA_VERSION,
                           "policy_version": POLICY_VERSION,
                           "pause_requested": False,
                           "stop_reason": "", "approvals": []}
        self.load()

    # -- persistence -------------------------------------------------------
    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            d = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise AutonomyError(
                f"autonomy state at {self.path} is unreadable ({e}). The "
                f"mission's research state is unaffected; remove or repair "
                f"this file to continue autonomously.")
        version = d.get("meta", {}).get("schema_version", 1)
        if version > AUTONOMY_SCHEMA_VERSION:
            raise AutonomyError(
                f"autonomy state schema v{version} is newer than this ORIGIN "
                f"(v{AUTONOMY_SCHEMA_VERSION}); refusing to load")
        self.items = {}
        for k, v in (d.get("items") or {}).items():
            problems = validate_item(v)
            if problems:
                # A malformed item is quarantined, not silently repaired and
                # not allowed to stop the mission loading.
                self.items[k] = WorkItem(
                    id=k, action=AWAIT_APPROVAL,
                    reason="quarantined: stored item failed validation on load",
                    idempotency_key=f"quarantine:{k}", status=FAILED,
                    last_error="; ".join(problems)[:400])
            else:
                self.items[k] = WorkItem.from_dict(v)
        self.counters.update(d.get("counters") or {})
        self.meta.update(d.get("meta") or {})
        self.meta["schema_version"] = AUTONOMY_SCHEMA_VERSION

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        payload = {"meta": self.meta, "counters": self.counters,
                   "items": {k: v.to_dict() for k, v in self.items.items()}}
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            f.write(json.dumps(payload, indent=2, default=str))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def record_decision(self, record: dict) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        record.setdefault("id", "dec_" + uuid.uuid4().hex[:10])
        record.setdefault("ts", time.time())
        record.setdefault("policy_version", POLICY_VERSION)
        with open(self.decisions_path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return record["id"]

    def decisions(self) -> list[dict]:
        if not self.decisions_path.exists():
            return []
        out = []
        for line in self.decisions_path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # -- queue -------------------------------------------------------------
    def add(self, item: WorkItem) -> tuple[WorkItem, str]:
        """Add an item unless an equivalent one already exists.

        Returns (item, note). Idempotency is by key: a repeated tick that
        proposes the same action gets the existing item back, so nothing is
        queued or charged twice.
        """
        problems = validate_item(item.to_dict())
        if problems:
            raise AutonomyError("rejected work item: " + "; ".join(problems))
        for existing in self.items.values():
            if existing.idempotency_key == item.idempotency_key:
                return existing, f"duplicate of {existing.id} ({existing.status})"
        self.items[item.id] = item
        return item, "queued"

    def open_items(self) -> list[WorkItem]:
        return [i for i in self.items.values() if i.status in OPEN_STATES]

    def by_status(self, status: str) -> list[WorkItem]:
        return [i for i in self.items.values() if i.status == status]

    def summary(self) -> dict:
        out = {s: 0 for s in ITEM_STATES}
        for i in self.items.values():
            out[i.status] = out.get(i.status, 0) + 1
        return out


# ------------------------------------------------------------------ limits
@dataclass
class RunLimits:
    """Every autonomous run is finite. There is no unbounded default."""
    max_steps: int = 10
    max_wall_s: float = 300.0
    max_experiments: int = 0        # 0 == defer to the mission budget
    max_retrievals: int = 0
    max_provider_calls: int = 0
    max_consecutive_failures: int = 3
    max_idle_ticks: int = 2
    max_attempts_per_item: int = 3
    backoff_base_s: float = 30.0
    backoff_cap_s: float = 3600.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- policy
class AutonomyPolicy:
    """Deterministic selection of the next permitted action.

    Determinism matters more than cleverness here: the operator must be able to
    run `autonomy plan`, see what would happen, and get exactly that from
    `autonomy tick`. Ties break on (priority, cost, created_at, id) — never on
    dict ordering, and never on model output.
    """
    version = POLICY_VERSION

    def __init__(self, limits: RunLimits, allow_network: bool = False,
                 allow_provider: bool = False, now: float | None = None):
        self.limits = limits
        self.allow_network = allow_network
        self.allow_provider = allow_provider
        self._now = now

    def now(self) -> float:
        return self._now if self._now is not None else time.time()

    def evaluate(self, store: AutonomyStore, state) -> dict:
        """Return a full, inspectable decision: chosen item plus every
        candidate that was rejected and why."""
        now = self.now()
        candidates, rejected = [], []
        for item in sorted(store.items.values(), key=lambda i: i.id):
            if item.status in (DONE, FAILED, CANCELLED):
                continue
            reason = self._veto(item, store, state, now)
            if reason:
                rejected.append({"id": item.id, "action": item.action,
                                 "reason": reason})
            else:
                candidates.append(item)
        chosen = None
        if candidates:
            chosen = sorted(candidates,
                            key=lambda i: (-round(i.priority, 6),
                                           round(i.cost_estimate, 6),
                                           i.created_at, i.id))[0]
        next_wake = None
        deferred = [i.not_before for i in store.items.values()
                    if i.status == DEFERRED and i.not_before > now]
        if deferred:
            next_wake = min(deferred)
        return {
            "chosen": chosen.id if chosen else None,
            "chosen_action": chosen.action if chosen else None,
            "chosen_reason": (
                f"highest priority ({chosen.priority}) among "
                f"{len(candidates)} permitted candidate(s); cost "
                f"{chosen.cost_estimate}; queued because: {chosen.reason}"
                if chosen else "no permitted work"),
            "candidates": [i.id for i in candidates],
            "rejected": rejected,
            "priority_factors": ["priority desc", "cost asc",
                                 "created_at asc", "id asc"],
            "tie_break": "deterministic: (-priority, cost, created_at, id)",
            "budget": {
                "experiments": f"{state.budget.experiments_used}/"
                               f"{state.budget.experiments_total}",
                "compute_s": round(state.budget.compute_seconds_used, 1),
                "provider_calls": state.budget.provider_calls_used,
                "retrievals": state.flags.get("retrievals_used", 0)},
            "approvals": {"network_enabled": self.allow_network,
                          "provider_enabled": self.allow_provider},
            "next_wake_at": next_wake,
            "policy_version": self.version,
        }

    def _veto(self, item: WorkItem, store: AutonomyStore, state,
              now: float) -> str:
        if item.status == CLAIMED:
            return "already claimed by a tick in progress"
        if item.status == INTERRUPTED:
            return ("interrupted: outcome unknown, needs operator review "
                    "(autonomy will not guess whether it completed)")
        if item.status == NEEDS_APPROVAL and not item.approved_by:
            return "awaiting operator approval"
        if item.status == DEFERRED and item.not_before > now:
            return (f"retry backoff pending until "
                    f"{time.strftime('%H:%M:%S', time.localtime(item.not_before))}")
        unmet = [d for d in item.depends_on
                 if store.items.get(d) is None
                 or store.items[d].status != DONE]
        if unmet:
            return f"dependencies not satisfied: {unmet}"
        if item.attempts >= self.limits.max_attempts_per_item:
            return (f"attempt limit reached "
                    f"({item.attempts}/{self.limits.max_attempts_per_item})")
        if item.requires_network and not self.allow_network:
            return ("requires network access, which is not enabled for this "
                    "run (pass --allow-network and an approved URL)")
        if item.requires_provider and not self.allow_provider:
            return ("requires an LLM provider call, which is not enabled for "
                    "this run (pass --allow-provider)")
        if item.action == RUN_EXPERIMENT:
            if not state.budget.can_run_experiment(item.cost_estimate):
                return (f"mission budget cannot afford it: "
                        f"{state.budget.exhausted_reason() or 'insufficient compute'}")
        if item.requires_network:
            used = state.flags.get("retrievals_used", 0)
            if self.limits.max_retrievals and used >= self.limits.max_retrievals:
                return (f"retrieval limit for this run reached "
                        f"({used}/{self.limits.max_retrievals})")
        if item.requires_provider and self.limits.max_provider_calls:
            if state.budget.provider_calls_used >= self.limits.max_provider_calls:
                return "provider-call limit for this run reached"
        return ""


def backoff_delay(attempts: int, limits: RunLimits) -> float:
    """Capped exponential backoff. Deterministic: no jitter, so a test can
    assert the exact next wake time."""
    return min(limits.backoff_base_s * (2 ** max(0, attempts - 1)),
               limits.backoff_cap_s)


# ------------------------------------------------------- retry classification
NON_RETRYABLE = ("PolicyViolation", "AutonomyError", "IllegalTransition",
                 "BrainConfigError", "CheckpointCorrupted", "ValueError",
                 "KeyError", "TypeError")
RETRYABLE = ("RetrievalError", "ProviderTimeout", "ProviderRateLimited",
             "ProviderUnavailable", "TimeoutError", "OSError", "BrainError")


def classify_failure(exc: Exception) -> tuple[bool, str]:
    """(retryable, class). Safety refusals are never retried: retrying a
    policy violation just violates the policy again."""
    name = type(exc).__name__
    if name in NON_RETRYABLE:
        return False, name
    if name in RETRYABLE:
        return True, name
    for base in type(exc).__mro__:
        if base.__name__ in NON_RETRYABLE:
            return False, base.__name__
        if base.__name__ in RETRYABLE:
            return True, base.__name__
    return False, name        # unknown failures are NOT retried by default
