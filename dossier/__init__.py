"""Dossierbuild -- an AI-assisted resume builder.

Package layout:
    core/     the product, with no interface attached
    ingest/   PDF / DOCX / LinkedIn -> profile, and the merge review
    ai/       every call that leaves this machine for a model
    render/   profile + design -> HTML -> PDF
    api/      FastAPI over core, and the server that hosts the frontend

The interface is not in here. It is a React app under ``web/``, built to
static files and served by ``api/static.py``.
"""

__version__ = "0.3.0"
