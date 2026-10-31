# Independent human review packet — not yet rated

The frozen20-case dataset from release validation remains unchanged (SHA256
2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1).
Its12positive sourceIDs are disjoint from earlier release/development/confirmation
qrels, but its author was an AI and relevance judgments are incomplete. It is not
human ground truth or a semantic-leakage guarantee. No threshold/ranking/prompt
selection is made using this dataset in the blocker remediation.

`human-review-packet.jsonl` pairs newly observed frozen queries, delivered answers,
exact public evidence excerpts/chunkIDs, provisional model text (separate from the
delivered final answer), and generation mode. Review raw-model quality and user-visible
final behavior separately; do not treat a withheld draft as a successfully delivered
answer. Rating fields remain
null. All packet rows must be rated, including timeouts/refusals; do not silently
exclude failed generations from denominators.

For a human review, retain the original output and have at least two independent
reviewers identify factual claims, judge each cited passage as supported,
unsupported, contradicted or insufficient, then assess answer relevance/completeness
and refusal appropriateness against the source text. Reviewers must distinguish
citation identity from passage support and abstain when the provided evidence is
insufficient. Record anonymous reviewer IDs, disagreements and adjudication; do not
show AI labels as if they were answers supplied by humans. Dataset authoring,
model pretraining contamination, near-duplicate source overlap and short excerpts
remain limitations even after human review.

No human panel participated in this run. Human groundedness, hallucination and
answer-relevance aggregate metrics remain null/NOT VERIFIED. Existing technical
spotchecks are counterexamples or diagnostics, not human accuracy rates.
