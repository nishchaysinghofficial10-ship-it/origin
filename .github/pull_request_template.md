## What this changes

## Evidence

```
# paste the output of:
python -m unittest discover -s tests
python tools/check_artifacts_portable.py .
```

- [ ] Tests added for new behaviour (and a regression test if this fixes a bug)
- [ ] Full suite passes; test counts in any docs I touched match what I just ran
- [ ] No new third-party runtime dependency (or justified in `docs/DECISIONS.md`)
- [ ] No safety limit widened
- [ ] No claim added that isn't backed by a command in this PR
- [ ] `docs/DECISIONS.md` updated if a non-obvious design choice was made

## Limitations this leaves in place
