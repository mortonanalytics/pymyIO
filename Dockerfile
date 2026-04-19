FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app/

# DigitalOcean Apps clones with submodules when the spec requests it, but
# also works if the build context already has them populated. Try to init
# in case the build context lacks them; ignore failure if already populated.
RUN git submodule update --init --recursive 2>/dev/null || true

# Build the wheel — hatchling's force-include materializes the static assets
# from vendor/myIO/ into pymyio/static/, so the install does not depend on
# symlinks resolving inside site-packages.
RUN pip install --no-cache-dir build \
 && python -m build --wheel \
 && pip install --no-cache-dir dist/pymyio-*.whl \
 && pip install --no-cache-dir -r app/requirements.txt

EXPOSE 8080

CMD ["python", "-m", "shiny", "run", "--host", "0.0.0.0", "--port", "8080", "app/app.py"]
