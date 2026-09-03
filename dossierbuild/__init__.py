"""Dossierbuild -- an AI-assisted resume builder.

Package layout:
    schema.py    the master profile data contract (Pydantic models)
    storage.py   loading, validating and safely writing profile.json
    quality.py   the bullet-writing standard, enforced as code
    ids.py       stable short identifiers for entries and bullets
    ui/          Streamlit interface
    importer/    reading an existing resume back into the schema
"""

__version__ = "0.1.0"
