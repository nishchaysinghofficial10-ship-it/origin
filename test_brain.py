"""LLM-layer tests: the brain may only PROPOSE. Structured validation, config
errors, malformed provider output, secret redaction, and provider budgets."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import brain as B                                 # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES                               # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.models import EpistemicStatus, HypothesisStatus   # noqa: E402
from origin.state import ResearchState                        # noqa: E402


class StubBrain(B.Brain):
    """Adversarial provider for tests."""
    name = "stub"

    def __init__(self, proposals):
        self.proposals = proposals

    def propose_hypotheses(self, context, k=2):
        return self.proposals

    def extract_claims(self, text, source_title):
        return []


class TestBrainPipeline(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def _mission(self, brain, name="m"):
        st = ResearchState.create(self.tmp / name, "q", "algobench",
                                  PROFILES["fast"], Budget(), "fast")
        ctl = ResearchController(st, get_domain("algobench"), brain=brain)
        return st, ctl

    def test_mock_proposals_flow_through_full_pipeline(self):
        st, ctl = self._mission(B.MockBrain())
        ctl.run()
        llm = [h for h in st.hypotheses.values() if "llm_proposed" in h.tags]
        self.assertGreaterEqual(len(llm), 1)
        for h in llm:   # no evidential privilege: resolved by experiments
            self.assertNotEqual(h.status, HypothesisStatus.PROPOSED)
            self.assertTrue(h.tested_in)
        # There is no path from a proposal to FACT claims or graph relations.
        self.assertFalse(any(c.status == EpistemicStatus.FACT
                             and "llm" in " ".join(c.source_ids)
                             for c in st.claims.values()))

    def test_malformed_and_out_of_vocabulary_proposals_rejected(self):
        bad = [
            {"statement": "too short", "rationale": "x", "prediction": {}},
            {"statement": "Valid length statement here about sorting behavior.",
             "rationale": "well formed but unknown kind",
             "prediction": {"kind": "summon_demons", "params": {}}},
            {"statement": "Valid length statement about an unknown algorithm.",
             "rationale": "unknown algorithm should be rejected",
             "prediction": {"kind": "beats",
                            "params": {"a": "bogo_sort", "b": "merge_sort",
                                       "regime": "random"}}},
            {"statement": "Prediction on a regime outside this mission's list.",
             "rationale": "regime not in mission -> reject",
             "prediction": {"kind": "fastest_on",
                            "params": {"algorithm": "merge_sort",
                                       "regime": "adversarial_zip"}}},
            "not even a dict",
        ]
        st, ctl = self._mission(StubBrain(bad))
        ctl.run(max_steps=3)   # through FORMING_HYPOTHESES
        llm = [h for h in st.hypotheses.values() if "llm_proposed" in h.tags]
        self.assertEqual(llm, [])
        rejects = [e for e in st.read_events()
                   if e["kind"] == "proposal_rejected"]
        self.assertGreaterEqual(len(rejects), 4)

    def test_anthropic_requires_env_key(self):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with self.assertRaises(B.BrainConfigError):
            B.AnthropicBrain()

    def test_malformed_provider_output_raises_and_logs_redacted(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-not-a-real-key-123456"
        logs = []
        br = B.AnthropicBrain(logger=logs.append,
                              _transport=lambda body: "NOT JSON AT ALL {{{")
        with self.assertRaises(B.BrainError):
            br.propose_hypotheses({"algorithms": []})
        self.assertGreaterEqual(len(logs), 2)           # retried, then failed
        blob = json.dumps(logs)
        self.assertNotIn("sk-test-not-a-real-key-123456", blob)
        # Valid HTTP envelope but non-JSON text content -> BrainProposalError.
        ok_env = json.dumps({"content": [{"type": "text",
                                          "text": "I refuse to emit JSON"}]})
        br2 = B.AnthropicBrain(_transport=lambda body: ok_env)
        with self.assertRaises(B.BrainProposalError):
            br2.propose_hypotheses({"algorithms": []})

    def test_redaction_strips_key_material(self):
        s = "error at sk-ant-abc123456789 while api_key=SECRETVALUE"
        red = B.redact(s)
        self.assertNotIn("sk-ant-abc123456789", red)
        self.assertNotIn("SECRETVALUE", red)
        self.assertIn("[REDACTED]", red)

    def test_provider_call_budget_enforced(self):
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-not-a-real-key-123456"
        bud = Budget(provider_calls_total=1)
        env = json.dumps({"content": [{"type": "text", "text": "[]"}]})
        br = B.AnthropicBrain(budget=bud, _transport=lambda body: env)
        self.assertEqual(br.propose_hypotheses({}), [])
        self.assertEqual(bud.provider_calls_used, 1)
        with self.assertRaises(B.BrainError) as cm:
            br.propose_hypotheses({})
        self.assertIn("budget", str(cm.exception))

    def test_brain_failure_does_not_break_mission(self):
        class ExplodingBrain(B.Brain):
            name = "exploding"
            def propose_hypotheses(self, context, k=2):
                raise B.BrainError("provider unreachable / rate limited")
            def extract_claims(self, text, source_title):
                return []
        st, ctl = self._mission(ExplodingBrain(), "boom")
        ctl.run()
        self.assertEqual(st.meta["phase"], "COMPLETED")
        self.assertTrue(any(e["kind"] == "brain_error"
                            for e in st.read_events()))


if __name__ == "__main__":
    unittest.main()
