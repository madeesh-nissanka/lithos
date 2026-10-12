# LITHOS screening benchmark: synthetic_soil_consolidation_v1

- Records: 72  Relevant (ground truth): 42
- Fully synthetic, hand-labeled benchmark; measures screening, not live retrieval.

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Auto-screened | Work saved |
|---|---|---|---|---|---|---|---|---|---|
| rules | 34 | 2 | 2 | 15 | 0.944 | 0.944 | 0.944 | 53 | 73.6% |
| bm25_top_k | 36 | 6 | 6 | 24 | 0.857 | 0.857 | 0.857 | 60 | 83.3% |
| rules_then_bm25 | 40 | 2 | 2 | 28 | 0.952 | 0.952 | 0.952 | 59 | 81.9% |
