# Google Colab

**Tier 2** — documented best-effort, verified manually before each release.

## Install

- `!pip install pymyio`

## Known gotcha

- Colab's output iframe sandboxes `import.meta.url`.
- Asset URLs may resolve against the iframe `srcdoc` origin rather than the Colab asset server.
- If d3/engine assets fail to load, set the `_base_url` trait on the widget instance to an absolute URL of the pymyio static directory served by Colab.
- Advanced use only.
