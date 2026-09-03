"""Every call that leaves this machine for a language model.

Kept in one package so that the answer to "what does this app send to Google,
and when" is a directory listing rather than a search. Everything a model
returns is a *proposal*: it is shown for review and never written to the
profile without a person accepting it.
"""
