"""Tooling for analysis you can defend.

Extracted from a football project, but nothing here knows about football. These
are the parts that turned out to be the actual product: the machinery that makes
a public claim checkable by someone who does not trust you.

    snapshot    versioned data with content hashes, so any past result can be
                re-derived offline and silent upstream revisions become visible
    citations   BibTeX with DOI content negotiation and title matching, so a
                real identifier attached to the wrong paper fails the build
    shrinkage   empirical Bayes, so small samples collapse toward the group mean
                instead of producing confident nonsense
    theme       charts that cannot be saved without stating what they measure,
                on how much data, from where, and when

The domain-specific parts — what a foul is, which league is which — stay in the
study that needs them. This package is what the next study starts from.

Named for what it is for rather than what it contains: the point is not the
statistics, it is being able to show your work.
"""

from evidence import citations, shrinkage, snapshot, theme

__all__ = ["citations", "shrinkage", "snapshot", "theme"]
__version__ = "0.1.0"
