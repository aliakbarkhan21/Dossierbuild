"""Reading existing career data back into the master profile schema.

Two sources, deliberately separated by how trustworthy their structure is:

``linkedin.py``
    A LinkedIn data-export ZIP. Already structured as CSVs by LinkedIn
    themselves, so parsing is deterministic -- no AI, no guessing, and the
    result is exact. This is the best source available and the one to prefer.

``extract.py``
    An existing resume as PDF or DOCX, reduced to plain text. Deterministic.
    Turning that text into a *profile* is not, and lives in ``dossier.ai``.

``merge.py``
    Folds whatever came back into the profile already on disk, without
    overwriting it. Every import route goes through here.
"""

from .merge import MergePlan, MergeCandidate, build_merge_plan, apply_merge_plan  # noqa: F401
