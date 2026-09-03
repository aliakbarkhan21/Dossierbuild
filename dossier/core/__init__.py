"""The product, with no interface attached.

The profile contract, the file it lives in, the writing standard it is held
to, and the ids that make an entry addressable. Nothing here imports a UI
framework, and nothing here may: this package is what both the Streamlit app
and the HTTP API drive, and the day it depends on either of them is the day
the other becomes impossible.
"""
