# Dossier in a container.
#
# The awkward dependency is Chromium: the PDF pipeline prints through
# Playwright, so the image needs a real browser and its shared libraries, not
# just the Python package. `--with-deps` installs those system libraries, and
# doing it in the same layer as the Python install keeps the two versions from
# drifting apart on a rebuild.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Everything the user owns lives here, mounted as a volume below.
    DOSSIER_DATA_DIR=/data \
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

COPY . .

# The volume is declared after the copy so an empty /data in the image does
# not shadow a bind mount at run time.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8501

# Streamlit's own health endpoint, so an orchestrator can tell "still booting"
# from "wedged".
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

CMD ["python", "-m", "streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
