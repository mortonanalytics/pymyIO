# AGENTS.md — pymyIO

Guidance for AI coding agents (Claude Code, Codex, etc.) working in this
repo. Read this before touching anything under `src/pymyio/static/` or
`vendor/`.

## One engine, two wrappers

`myIOapi.js` / `style.css` are the **d3 engine**. They live canonically in
the R package at:

```
mortonanalytics/myIO : inst/htmlwidgets/myIO/{myIOapi.js,style.css,lib/}
```

This repo pulls them in via a git submodule (`vendor/myIO`) and surfaces
them to Python via **symlinks**:

```
src/pymyio/static/myIOapi.js -> ../../../vendor/myIO/inst/htmlwidgets/myIO/myIOapi.js
src/pymyio/static/style.css  -> ../../../vendor/myIO/inst/htmlwidgets/myIO/style.css
```

There is exactly **one** copy of the engine on disk. Two packages wrap it.

## Hard rules

1. **Never edit the engine through the symlink.** Writing to
   `src/pymyio/static/myIOapi.js` or `style.css` from this repo silently
   modifies the `vendor/myIO/` working tree. Those edits belong in the
   myIO repo, not here. If you need an engine change:
   - Make it in `../myIO/inst/htmlwidgets/myIO/` (the R repo).
   - Commit + push it there.
   - Come back and bump the submodule pointer (see below).

2. **Never duplicate the engine.** Do not copy `myIOapi.js` into this
   repo as a regular file, do not fork it into `src/pymyio/engine/`, do
   not vendor a second copy "just for Python." The whole point of the
   submodule + symlink setup is **one source of truth**. If the symlink
   is inconvenient for a particular tool, fix the tool — don't clone the
   file.

3. **Never commit a detached/dirty submodule.** Before any commit that
   touches `vendor/myIO`, verify:
   ```
   git -C vendor/myIO status        # must be clean
   git -C vendor/myIO rev-parse HEAD # must match a pushed myIO commit
   ```
   If the submodule working tree is dirty, the edits were almost
   certainly made by mistake via the symlink — stash them, go do the fix
   properly in the myIO repo, then bump.

4. **Bumps are deliberate, reviewed commits.** To pull engine fixes:
   ```
   git submodule update --remote vendor/myIO
   git -C vendor/myIO log --oneline <old>..<new>   # read every commit
   git add vendor/myIO
   git commit -m "bump myIO engine to <sha>: <one-line summary>"
   ```
   Never do a blind `--remote` bump and commit without reading what
   changed — the R side may have shipped breaking JS that needs a paired
   Python-side update (new kwarg on `add_layer`, new traitlet, etc.).

5. **Paired changes require both repos.** If an engine change adds,
   renames, or removes a config key, the pymyIO builder **and** the R
   wrapper must be updated in lockstep. Do not ship a submodule bump
   that breaks Python API parity with the R side — parity is the
   product.

## Workflow cheatsheet

| You want to... | Do this |
|---|---|
| Fix a d3 rendering bug | Edit in `mortonanalytics/myIO`, commit, push, then bump submodule here |
| Add a new chart type | Engine change in myIO → submodule bump → add Python builder surface + test |
| Change only Python API (no JS) | Edit under `src/pymyio/` (not `static/`); do not touch `vendor/` |
| Change only `widget.js` (Python-side glue) | Edit `src/pymyio/static/widget.js` — it's a real file, not a symlink |
| Update R wrapper only | Work in the myIO repo; no change needed here unless engine moves |

## Cross-repo sync automation

- **myIO side** — opens a tracking issue here (labeled
  `engine-bump-pending`) whenever engine files change on its `main`.
- **This repo** — `.github/workflows/engine-bump-close.yaml` auto-closes
  those issues once the referenced upstream SHA is an ancestor of the
  current `vendor/myIO` HEAD. No token setup needed; uses the default
  `GITHUB_TOKEN`.

You rarely need to close a tracking issue by hand — just bump the
submodule as described above and the close-workflow handles it.

## Preflight for agents

**At session start, run:**

```
gh issue list --label engine-bump-pending
```

Any open issue with that label means the upstream myIO repo has shipped
an engine change that this repo hasn't picked up yet. The issue body
contains the upstream SHA and a checklist — prefer clearing those
before starting unrelated work, since a stale submodule is the most
common source of "works in R, broken in Python" bug reports.

Before any change that touches `vendor/`, `src/pymyio/static/`, or
engine behavior, confirm in one sentence which side of the boundary
you're editing. If the answer is "both", split the work: engine-side
commit in myIO first, then submodule bump + Python-side commit here.

If unsure, stop and ask — a silent edit through the symlink is the
single most likely way to corrupt this setup.
