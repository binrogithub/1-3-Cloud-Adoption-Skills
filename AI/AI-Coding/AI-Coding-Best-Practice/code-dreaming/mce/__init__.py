"""maas-context-engineering: governed cross-tool memory assembled from
backbone + dream/distill/FTS subsystems."""
from .backbone import Backbone, Scope, PrivacyError
from .retrieve import retrieve_approved_context, search, build_fts_query

__all__ = [
    "Backbone", "Scope", "PrivacyError",
    "retrieve_approved_context", "search", "build_fts_query",
]
