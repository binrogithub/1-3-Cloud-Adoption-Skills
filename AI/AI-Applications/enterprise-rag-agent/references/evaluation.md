# Evaluation Reference

Create an evaluation set with these minimum categories:

- 20 simple fact questions: one source, direct answer.
- 20 multi-hop questions: answer requires combining two or more permitted chunks.
- 20 citation accuracy questions: answer is simple but citation precision matters.
- 10 trap questions: missing evidence, outdated law, inaccessible source, wrong jurisdiction, or false premise.

## Required Columns

- `id`
- `category`
- `language`
- `question`
- `expected_answer`
- `required_doc_ids`
- `required_chunk_ids`
- `jurisdiction`
- `effective_date`
- `security_context`
- `pass_criteria`

## Scoring

- Answer correctness: facts match the expected answer.
- Citation correctness: cited chunks directly support the claim.
- ACL correctness: inaccessible sources are not retrieved, cited, or summarized.
- Refusal correctness: trap questions do not produce unsupported answers.
- Latency: normal queries complete in under 5 seconds.

Use multilingual test coverage across Portuguese, Spanish, and English when the deployment supports those languages.
