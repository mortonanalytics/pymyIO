---
name: engine-sync
description: Update pymyIO to a human-approved canonical myIO engine commit and verify compatibility, generated bundle state, and documentation before opening an unmerged PR. Use for approved pymyIO engine-sync issues.
---

# pymyIO engine sync

Require an open issue labeled `backlog-ready`, non-red `main`, no open `automation-pr`, and an isolated worktree. The issue must name an existing myIO commit and expected compatibility surface.

Verify the commit in the canonical sibling `myIO` repository and review its diff, release notes, and compatibility implications before changing the submodule or generated assets. Update only the ownership surfaces allowed by `AGENTS.md`. Run compatibility tests, verify generated bundle provenance and cleanliness, and update user-facing documentation for changed behavior.

Open one PR labeled `automation-pr` with provenance, `Closes #N`, old and new myIO SHAs, generated-state evidence, commands/results, risks, and remaining external gates. Stop before version bump, merge, release, publication, or CRAN submission.
