# Frozen blind evaluation authoring protocol

Author: fresh isolated AI agent `/root/blind_eval`, 2026-10-30. This is a single-agent, corpus-grounded authored evaluation, not a human panel or an independent real-user study. The agent received an authoring contract, not previous retrieval rankings, scores, reports, implementation, or thresholds.

## Inputs and isolation

The only repository files read were `data/curated_resources.jsonl` and the three ID-exclusion inputs `eval/release_queries.jsonl`, `eval/engineering_queries.jsonl`, and `eval/engineering_confirmation_queries.jsonl`. The earlier evaluation files were parsed only to extract item IDs; their questions, expected answers, and other fields were not displayed or used for authoring. No previous reports, retrieval implementation, rankings, scores, or thresholds were read. No retrieval/model execution, external calls, cloud APIs, source modifications, commits, or pushes were performed. Local Python was used to inspect corpus text and validate this artifact.

Corpus: 118 public-source snapshots, SHA256 `34811da304d7e0b6645e2523c6557a84b9240345f3a420b6425c43fd4c8d3190`. Answers are tied to these stored snapshots, not claims about current live documentation or all software versions.

## Selection and source disjointness

The agent inspected the corpus title inventory and source passages, excluding every item ID encountered in prior judgments. It selected narrow documented behaviors across Docker, browser APIs/HTML, and Python modules, then phrased practical questions without copying source titles. Selection was purposive and based on answerable passages; it was not optimized against retrieval results.

Prior judged source IDs (28): 5001, 5003, 5011, 5024, 5025, 5026, 5027, 5028, 5030, 5031, 5039, 5040, 5043, 5059, 5061, 5062, 5073, 5075, 5078, 5082, 5084, 5090, 5092, 5098, 5109, 5117, 5121, 5126.

New positive source IDs (12): 5002, 5013, 5029, 5047, 5052, 5064, 5066, 5072, 5077, 5080, 5094, 5106. These sets have no overlap. Every positive has a distinct target source and an exact contiguous supporting quote from its `full_text` field, preserving newlines. There are 12 positive questions: six English and six Vietnamese. Each has explicit short factual claims to check, with natural paraphrases and Vietnamese translations allowed if meaning is preserved.

The agent scanned all corpus text for distinctive concepts in the selected questions and reviewed matching snippets for additional substantiable support. Only the recorded item judgments were substantiated for the complete factual claims. This is not exhaustive independent relevance annotation: related or partially relevant sources may remain unjudged. **Unjudged items are unknown, not automatically irrelevant.** A metric treating every unjudged retrieval as a false positive would need qualification or further blinded judgments.

There are eight negative questions, balanced four English/four Vietnamese: two outside IT, two requesting inaccessible private information, and four IT requests whose required technical answers are unsupported in this corpus. Literal corpus checks found no StatefulSet, CUDA, BGP, or cluster-id coverage; Kubernetes appears only incidentally in a Docker Desktop list, and Rust only incidentally in a Python pattern-matching comparison. Incidental names do not support the requested manifest, lifetime signature, GPU kernel, or router configuration. Negative rows have empty judgments, an explicit rationale, and the expected grounded refusal in `expected_claims`.

## Validation, freeze, and use

Before any retrieval or generation evaluation, local assertions verified 20 rows, unique case IDs, the 12/8 positive/negative split, the six/six positive language split, twelve unique positive sources, exact quote membership, and zero overlap with all 28 prior source IDs. `refusal_expected` is false for positives and true for negatives. Expected refusal means acknowledging insufficient supplied evidence or inaccessible information without inventing an answer; it does not imply these IT topics are inherently unsafe or unanswerable elsewhere.

Frozen cases SHA256: `2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1`.

The cases and protocol are made read-only and their SHA256 values are reported to the supervising agent before evaluation. They must not be edited in response to ranking or generation results. Any later adjudication should be separately versioned and report both original and amended outcomes. Read-only permissions are an operational freeze, not tamper-proof storage; the digest is the identity check.

## Limits

This small authored set is a fresh source-disjoint diagnostic sample, not a representative benchmark, external validity claim, human faithfulness assessment, or production readiness evidence. It remains AI-authored and may contain selection or language biases. Quotes establish available support, not that a generated response used that support faithfully. Evaluate generated factual claims separately from citation ID validity. No retrieval quality, generation quality, refusal performance, model behavior, or operating threshold has been tested by this authoring step.
