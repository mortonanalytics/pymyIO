# pymyIO Shiny gallery

A Shiny-for-Python app demonstrating every working chart type. Mirrors the
R-myIO gallery at [https://www.morton-analytics.com/myio/](https://www.morton-analytics.com/myio/).

## Run locally

From the repo root:

```bash
pip install -e ".[shiny]"
shiny run --reload --launch-browser app/app.py
```

Or with uv:

```bash
uv pip install -e ".[shiny]"
uv run shiny run --reload --launch-browser app/app.py
```

## Deployment

Built with the [Dockerfile](../Dockerfile) at the repo root and the
[`.do/app.yaml`](../.do/app.yaml) App Spec. Push to `main`; Digital Ocean
rebuilds and redeploys.
