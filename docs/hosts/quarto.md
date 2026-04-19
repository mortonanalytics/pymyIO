# Quarto

**Tier 2** — documented best-effort, verified manually before each release.

## HTML output

- Interactive.
- Brush, rollover, and annotate work client-side via the vendored engine.

## Runtime limits

- Reactive Python callbacks require a live kernel.
- Use Shiny for Python or a live Jupyter runtime for that.

## Unsupported outputs

- PDF and docx outputs are NOT supported.
- Quarto renders static formats server-side without a JS runtime, so pymyio charts will not appear there.
- For static exports, render via `pymyio.to_standalone_html(...)` and embed the output HTML manually, or use a separate rasterization path.
