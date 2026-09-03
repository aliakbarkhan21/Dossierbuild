# Dossier in a container.
#
# Two stages, because the interface and the product need different toolchains.
# Node builds the frontend into static files and is then thrown away -- the
# runtime image has no Node in it, which is the whole point of serving
# web/dist from uvicorn rather than running a second server.
#
# The awkward dependency is Chromium: the PDF pipeline prints through
# Playwright, so the image needs a real browser and its shared libraries, not
# just the Python package. `--with-deps` installs those system libraries, and
# doing it in the same layer as the Python install keeps the two versions from
# drifting apart on a rebuild.

FROM node:22-slim AS web

WORKDIR /web

# The lockfile first, so editing a component does not re-resolve every package.
COPY web/package.json web/package-lock.json* ./
RUN npm ci

COPY web/ ./
RUN npm run build


FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Everything the user owns lives here, mounted as a volume below.
    DOSSIER_DATA_DIR=/data \
    # The built frontend, copied from the stage above rather than built here.
    DOSSIER_WEB_DIR=/app/web/dist \
    # Playwright's browsers default to a per-user cache directory; pinning it
    # keeps them in the image rather than in a layer that a different runtime
    # user cannot read.
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright

WORKDIR /app

# Dependencies first, so editing application code does not re-download
# Chromium on every build.
COPY requirements.txt ./
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY dossier/ ./dossier/
COPY --from=web /web/dist/ ./web/dist/

# The volume is declared after the copy so an empty /data in the image does
# not shadow a bind mount at run time.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

# Reports "up and able to do its job" rather than just "listening": the health
# endpoint checks that Chromium starts and that the data directory is readable.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD python -c "import urllib.request, json; \
assert json.load(urllib.request.urlopen('http://localhost:8000/api/health'))['ok']"

CMD ["python", "-m", "uvicorn", "dossier.api:app", \
     "--host", "0.0.0.0", "--port", "8000"]
