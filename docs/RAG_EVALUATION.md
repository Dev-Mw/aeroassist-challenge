# Policy answer quality — Iteration 5

The public golden set remains authoritative for public contract regression. Run
`make evaluate-public` against a running API and `make test` for unit tests.

`make evaluate-rag` executes **offline, deterministic, RAGAS-inspired** checks over
four hand-authored synthetic questions. It reports `context_recall_at_3`,
`context_precision_at_3` and `negative_abstention`. For live output checks, run:

```bash
python -m scripts.evaluate_rag --base-url http://127.0.0.1:8080
```

Live checks additionally report `citation_precision`, `answer_topic_coverage`
and `unsupported_abstention`. These simple lexical measures are **not** actual
RAGAS scores, semantic faithfulness, or proof that generated claims are true.
The case set is small and should be expanded, including paraphrases, mixed
operational/policy questions, misleading retrieved instructions, and irrelevant
citations, before using any score as a release gate.

Generation policy: the model sees source-tagged retrieved text, writes one answer
and never assigns its own citations. The application rejects obvious unsupported
numbers, URLs and missing policy-topic coverage. On rejection, timeout or provider
error, it returns the bounded extractive source answer. The fallback is logged
without storing raw prompts or passenger data. The guards are heuristics and
**cannot detect every false claim, instruction injection, or policy misreading**.

The returned `model` indicates the configured backend, not necessarily that the
model's candidate was accepted. Logs distinguish accepted and fallback paths.
Follow-up work: add grounded claim-level review and evaluate it with labeled
human judgments; improve cited passage selection and multi-intent detection.
