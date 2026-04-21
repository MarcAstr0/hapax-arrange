# Test before commit

Before every `git commit`, run both:

```bash
uv run pytest -q
uv run ruff check
```

Both must pass. If either fails, fix the underlying issue — do not commit
with failing tests, and do not bypass with `--no-verify`.

**Why**: this repo has no CI yet. The local pytest + ruff pass is the only
pre-merge gate. Shipping a failing main branch silently is the main risk.

**How to apply**: applies to any commit on `main`. For exploratory
work-in-progress, use a feature branch and amend freely — but squash or
rebase to green before merging.
