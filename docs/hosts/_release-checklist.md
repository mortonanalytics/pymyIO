# Pre-release Tier-2 smoke checklist

Exercised manually before each release tag to catch silent regressions on hosts whose runtime state cannot be reproduced in CI.

## Google Colab

- [ ] Install pymyio from the release candidate wheel
- [ ] Render the canonical quickstart example
- [ ] Confirm `.pymyio-chart svg` appears with at least one mark
- [ ] Confirm brush interaction visually updates the chart (where the host supports interactivity)

## marimo

- [ ] Install pymyio from the release candidate wheel
- [ ] Render the canonical quickstart example
- [ ] Confirm `.pymyio-chart svg` appears with at least one mark
- [ ] Confirm brush interaction visually updates the chart (where the host supports interactivity)

## Panel

- [ ] Install pymyio from the release candidate wheel
- [ ] Render the canonical quickstart example
- [ ] Confirm `.pymyio-chart svg` appears with at least one mark
- [ ] Confirm brush interaction visually updates the chart (where the host supports interactivity)

## Solara

- [ ] Install pymyio from the release candidate wheel
- [ ] Render the canonical quickstart example
- [ ] Confirm `.pymyio-chart svg` appears with at least one mark
- [ ] Confirm brush interaction visually updates the chart (where the host supports interactivity)

## Quarto

- [ ] Install pymyio from the release candidate wheel
- [ ] Render the canonical quickstart example
- [ ] Confirm `.pymyio-chart svg` appears with at least one mark
- [ ] Confirm brush interaction visually updates the chart (where the host supports interactivity)

## Classic Jupyter Notebook

- [ ] Install pymyio from the release candidate wheel
- [ ] Render the canonical quickstart example
- [ ] Confirm `.pymyio-chart svg` appears with at least one mark
- [ ] Confirm brush interaction visually updates the chart (where the host supports interactivity)

Release tag is blocked if any Tier-1 CI gate fails; Tier-2 checklist items should be resolved before tag but are not automatic blockers — file known-issues in the tracker when deferring.
