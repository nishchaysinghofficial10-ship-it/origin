"""Portability regression tests (defects P-1, P-2).

P-1: ORIGIN <= v1.0 stored ABSOLUTE experiment-artifact paths. A copied or
unpacked project silently read the original machine's directories, so `verify`
returned a false PASS for a mission whose own artifacts were missing, and
`replay` re-ran foreign code. On any other machine both simply crashed.

P-2: `replay` asserted wall-clock timing equivalence, which is a property of
the host rather than of the recorded experiment; it flaked on shared/1-core
machines. Timing is now reported, and the verdict rests on reproducible
invariants (cell coverage, correctness, decisive ranking order).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin.cli import main as cli_main                       # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.state import ResearchState                        # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ABSOLUTE_MARKERS = ("/home/", "/Users/", "/root/", "C:\\\\Users")


def _completed_mission(root: Path, profile: str = "fast") -> ResearchState:
    cli_main(["init", "portability", "--dir", str(root), "--profile", profile,
              "--brain", "none"])
    st = ResearchState.load(root)
    ResearchController(st, get_domain(st.meta["domain"])).run()
    return st


class TestArtifactReferencesAreRelative(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_new_missions_store_root_relative_dirs(self):
        st = _completed_mission(self.tmp / "m")
        self.assertTrue(st.experiments)
        for rec in st.experiments.values():
            self.assertFalse(Path(rec.dir).is_absolute(), rec.dir)
            self.assertTrue(rec.dir.startswith("experiments/"), rec.dir)
            self.assertEqual(rec.path(st.root), st.root / rec.dir)

    def test_no_absolute_paths_in_persisted_state(self):
        st = _completed_mission(self.tmp / "m")
        for name in ("state.json", "research_state/experiments.json"):
            text = (st.root / name).read_text()
            for marker in ABSOLUTE_MARKERS:
                self.assertNotIn(marker, text, f"{name} leaks {marker}")

    def test_legacy_absolute_dirs_are_normalized_on_load(self):
        """A v1.0 checkpoint (absolute dirs, possibly from another machine)
        must load, normalize, and keep working."""
        st = _completed_mission(self.tmp / "m")
        snapshot = json.loads((st.root / "state.json").read_text())
        foreign = "/home/someone-else/origin-project/runs/m"  # portability-allow
        for rec_id, rec in snapshot["experiments"].items():
            rec["dir"] = f"{foreign}/experiments/{rec_id}"
        snapshot["schema_version"] = 2
        (st.root / "state.json").write_text(json.dumps(snapshot, indent=2))

        st2 = ResearchState.load(st.root)
        self.assertEqual(st2.flags.get("migrated_paths"), len(st2.experiments))
        for rec in st2.experiments.values():
            self.assertFalse(Path(rec.dir).is_absolute(), rec.dir)
            self.assertTrue(rec.path(st2.root).exists(), rec.dir)
        self.assertEqual(st2.verify(), [])

    def test_verify_flags_an_absolute_dir_rather_than_following_it(self):
        st = _completed_mission(self.tmp / "m")
        rec = next(iter(st.experiments.values()))
        rec.dir = str(st.root / "experiments" / rec.id)   # absolute, in-tree
        problems = st.verify()
        self.assertTrue(any("absolute artifact path" in p for p in problems),
                        problems)


class TestRelocatedMission(unittest.TestCase):
    """The core P-1 regression: a mission must be usable *only* from its own
    files, wherever those files are."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.origin_mission = self.tmp / "original"
        _completed_mission(self.origin_mission)

    def tearDown(self):
        self._td.cleanup()

    def test_copied_mission_verifies_and_replays(self):
        copy = self.tmp / "elsewhere" / "deeper" / "copied_mission"
        copy.parent.mkdir(parents=True)
        shutil.copytree(self.origin_mission, copy)
        self.assertEqual(cli_main(["verify", "--dir", str(copy)]), 0)
        st = ResearchState.load(copy)
        exp = next(r.id for r in st.experiments.values() if r.status == "completed")
        self.assertEqual(cli_main(["replay", "--dir", str(copy), "--exp", exp]), 0)

    def test_copy_without_its_own_artifacts_fails_verify(self):
        """Guards the false-PASS defect: the copy must NOT fall back to the
        original mission's directories."""
        copy = self.tmp / "gutted"
        shutil.copytree(self.origin_mission, copy)
        shutil.rmtree(copy / "experiments")
        problems = ResearchState.load(copy).verify()
        self.assertTrue(problems, "verify falsely passed on a gutted copy")
        self.assertTrue(any("missing spec.json" in p or "result.json missing" in p
                            for p in problems), problems)
        self.assertEqual(cli_main(["verify", "--dir", str(copy)]), 1)
        # ...and the original is untouched by any of this.
        self.assertEqual(ResearchState.load(self.origin_mission).verify(), [])

    def test_reports_regenerate_from_a_relocated_copy(self):
        copy = self.tmp / "moved"
        shutil.copytree(self.origin_mission, copy)
        (copy / "reports" / "dossier.md").unlink()
        self.assertEqual(cli_main(["report", "--dir", str(copy)]), 0)
        dossier = (copy / "reports" / "dossier.md").read_text()
        self.assertIn("Research question", dossier)
        # Results tables are rebuilt from the copy's own result.json files.
        self.assertIn("Results", dossier)


class TestArchiveIsSelfContained(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_zip_roundtrip_of_a_mission_verifies_and_replays(self):
        mission = self.tmp / "m"
        _completed_mission(mission)
        archive = self.tmp / "mission.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in mission.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(mission).as_posix())
        extracted = self.tmp / "unpacked" / "somewhere_else"
        extracted.mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            z.extractall(extracted)
        shutil.rmtree(mission)          # the source is gone: no fallback exists
        self.assertEqual(cli_main(["verify", "--dir", str(extracted)]), 0)
        st = ResearchState.load(extracted)
        exp = next(r.id for r in st.experiments.values() if r.status == "completed")
        self.assertEqual(cli_main(["replay", "--dir", str(extracted),
                                   "--exp", exp]), 0)

    def test_shipped_examples_are_portable(self):
        """The repository's public example missions must not embed absolute
        paths, and must verify from a relocated copy."""
        guard = REPO / "tools" / "check_artifacts_portable.py"
        proc = subprocess.run([sys.executable, str(guard), str(REPO / "examples")],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        for name in ("demo_run", "flagship_run"):
            src = REPO / "examples" / name
            if not src.exists():
                continue
            dst = self.tmp / f"relocated_{name}"
            shutil.copytree(src, dst)
            self.assertEqual(cli_main(["verify", "--dir", str(dst)]), 0, name)


class TestReplayVerdictIsStable(unittest.TestCase):
    """P-2: the verdict must not depend on host timing noise."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_timing_noise_does_not_fail_a_replay(self):
        mission = self.tmp / "m"
        st = _completed_mission(mission)
        exp = next(r.id for r in st.experiments.values() if r.status == "completed")
        # Pretend every stored cell was measured far faster than it replays:
        # pure timing deviation, identical correctness and ordering.
        rec = st.experiments[exp]
        result_path = rec.path(st.root) / "result.json"
        data = json.loads(result_path.read_text())
        for row in data["rows"]:
            row["mean_s"] = row["mean_s"] / 10.0
        result_path.write_text(json.dumps(data, indent=2))
        self.assertEqual(cli_main(["replay", "--dir", str(mission),
                                   "--exp", exp]), 0)
        # ...but the operator can still demand strict equivalence.
        self.assertEqual(cli_main(["replay", "--dir", str(mission), "--exp", exp,
                                   "--strict", "--noise-floor-ms", "0"]), 1)

    def test_correctness_change_still_fails(self):
        mission = self.tmp / "m"
        st = _completed_mission(mission)
        exp = next(r.id for r in st.experiments.values() if r.status == "completed")
        rec = st.experiments[exp]
        result_path = rec.path(st.root) / "result.json"
        data = json.loads(result_path.read_text())
        data["rows"][0]["correct"] = False
        result_path.write_text(json.dumps(data, indent=2))
        self.assertEqual(cli_main(["replay", "--dir", str(mission),
                                   "--exp", exp]), 1)

    def test_decisive_ranking_inversion_fails_under_strict(self):
        mission = self.tmp / "m"
        st = _completed_mission(mission)
        exp = next(r.id for r in st.experiments.values() if r.status == "completed")
        rec = st.experiments[exp]
        result_path = rec.path(st.root) / "result.json"
        data = json.loads(result_path.read_text())
        # Claim the slowest algorithm in a group was decisively the fastest.
        groups = {}
        for row in data["rows"]:
            groups.setdefault((row["regime"], row["n"]), []).append(row)
        target = max(groups.values(), key=len)
        target.sort(key=lambda r: r["mean_s"])
        target[-1]["mean_s"] = target[0]["mean_s"] / 100.0
        result_path.write_text(json.dumps(data, indent=2))
        # Default verdict rests on host-independent invariants only...
        self.assertEqual(cli_main(["replay", "--dir", str(mission),
                                   "--exp", exp]), 0)
        # ...and --strict promotes the ranking inversion to a failure.
        self.assertEqual(cli_main(["replay", "--dir", str(mission), "--exp", exp,
                                   "--strict", "--noise-floor-ms", "0"]), 1)


if __name__ == "__main__":
    unittest.main()
