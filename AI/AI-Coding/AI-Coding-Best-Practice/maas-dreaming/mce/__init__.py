"""maas-context-engineering: governed cross-tool memory assembled from
vendored Mem0 (backbone) + MiMo-Code (dream/distill/FTS design)."""
from .backbone import Backbone, Scope, PrivacyError
from .retrieve import retrieve_approved_context, search, build_fts_query

__all__ = [
    "Backbone", "Scope", "PrivacyError",
    "retrieve_approved_context", "search", "build_fts_query",
]
