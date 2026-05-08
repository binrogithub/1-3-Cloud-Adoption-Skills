# Citation Prompt

Build a citation map for the answer.

For each cited claim, return:
- claim
- doc_id
- chunk_id
- title
- page or section
- quoted evidence span, if available
- effective_date
- confidence: high, medium, or low

Reject citations that do not directly support the claim.
