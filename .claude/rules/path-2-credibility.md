---
paths:
  - "src/**"
  - "app/**"
  - "docs/**"
  - "examples/**"
  - "tests/**"
  - "pyproject.toml"
  - "CHANGELOG.md"
---

# Path 2 — Credibility Moat (pymyIO)

pymyIO is the Python sibling of myIO, part of Morton Analytics' OSS credibility layer underneath the selected growth path (Path 2 — Modular Infrastructure Risk Intelligence). Full plan: `../morton-command-center/strategy/path-2-90day-plan.md`.

## Role in Path 2

pymyIO is **not a revenue product**. It's a credibility moat that compounds Path 2 in four ways — identical to myIO's role, but on the Python side:

1. **Technical credibility** in prospect conversations: PyPI-resident, maintained analytical library = proof of production-grade work.
2. **Chart layer** in GroundPulse and IONe demos, long-form posts, capabilities statements.
3. **SBIR narrative asset** — Innovation + Key Personnel + Commercialization sections cite pymyIO alongside myIO.
4. **Federal market reach.** The federal data analytics market is shifting from R to Python. Holding both languages doubles the addressable surface for the credibility moat.

## Current state (2026-07-17)

- v0.3.0 (2026-07-17): engine re-pinned to myIO 1.2.0-dev (`1dbc008`), new `lttb` transform (Python port of myIO#80)
- 34 chart types, 20 statistical transforms; tracking myIO main ahead of its ~Aug 1 1.2.0 release — re-pin + matching pymyIO release when it tags
- Gallery at pymyio.morton-analytics.com (footer version marker verifies deployed build)

## Maintenance cadence (Path 2 expectation)

- Track myIO releases — each myIO release gets a matching pymyIO release with the same surface (myIO 1.2.0 is currently unmatched)
- Maintain feature parity with myIO sibling — drift between R and Python kills the dual-language story
- Documentation site stays current (mkdocs)
- Examples and gallery demonstrate real Path 2 use cases when feasible

## What this rule allows / encourages

- Feature parity work matching myIO's surface
- Performance work (scipy-backed transforms, vectorization)
- Shiny-for-Python integration improvements (existing pattern in the repo)
- Gallery / docs examples using infrastructure-monitoring data patterns

## What this rule deprioritizes

- Python-specific feature divergence from myIO
- Marketing pymyIO as a standalone commercial product
- Time investment beyond ~2–4 hours/week
- Building integrations that have no tie to GroundPulse / IONe use cases

## Cross-repo coordination

- myIO (`../myIO/`) is the R sibling and the parity reference — when shipping a feature here, confirm coverage there
- GroundPulse (`../eo/`) and IONe (`../ione/`) consume pymyIO when their chart layer needs Python rendering; flag if they're using direct libraries instead

## When in doubt

The dual-language story is the value. Drift between myIO and pymyIO erodes the moat. If a feature would land in only one of the two libraries, ask whether it really belongs in both before shipping.
