# Golden Set Results

Run against all 50 items in `eval/golden_set.json` (38 answerable, 12 traps) through the real corrective-RAG graph.

**Overall: 50/50 passed (12/12 traps correctly refused).**

A trap "pass" means the model refused rather than fabricating an answer. This is the metric that actually matters for a bid team, since a hallucinated commercial term in a real proposal is far more costly than a missed factual lookup.

| ID | Category | Result | Faithfulness | Context Recall | Latency (ms) |
|---|---|---|---|---|---|
| gs001 | factual | ✅ PASS | 1.00 | 1.00 | 23674 |
| gs002 | factual | ✅ PASS | 1.00 | 1.00 | 7847 |
| gs003 | factual | ✅ PASS | 1.00 | 1.00 | 5494 |
| gs004 | factual | ✅ PASS | 1.00 | 1.00 | 14176 |
| gs005 | factual | ✅ PASS | 1.00 | 1.00 | 8813 |
| gs006 | factual | ✅ PASS | 1.00 | 1.00 | 17004 |
| gs007 | factual | ✅ PASS | 1.00 | 1.00 | 6252 |
| gs008 | factual | ✅ PASS | 1.00 | 1.00 | 25894 |
| gs009 | factual | ✅ PASS | 1.00 | 1.00 | 8000 |
| gs010 | factual | ✅ PASS | 1.00 | 1.00 | 6357 |
| gs011 | factual | ✅ PASS | 1.00 | 1.00 | 7871 |
| gs012 | factual | ✅ PASS | 1.00 | 1.00 | 5747 |
| gs013 | factual | ✅ PASS | 1.00 | 1.00 | 5431 |
| gs014 | factual | ✅ PASS | 1.00 | 1.00 | 5846 |
| gs015 | factual | ✅ PASS | 1.00 | 1.00 | 6002 |
| gs016 | factual | ✅ PASS | 1.00 | 1.00 | 5226 |
| gs017 | factual | ✅ PASS | 1.00 | 1.00 | 7855 |
| gs018 | factual | ✅ PASS | 1.00 | 1.00 | 7079 |
| gs019 | factual | ✅ PASS | 1.00 | 1.00 | 6731 |
| gs020 | factual | ✅ PASS | 1.00 | 1.00 | 48240 |
| gs021 | factual | ✅ PASS | 1.00 | 1.00 | 7404 |
| gs022 | factual | ✅ PASS | 1.00 | 1.00 | 24315 |
| gs023 | factual | ✅ PASS | 1.00 | 1.00 | 6960 |
| gs024 | factual | ✅ PASS | 1.00 | 1.00 | 12403 |
| gs025 | factual | ✅ PASS | 1.00 | 1.00 | 8042 |
| gs026 | factual | ✅ PASS | 1.00 | 1.00 | 5158 |
| gs027 | factual | ✅ PASS | 1.00 | 1.00 | 6391 |
| gs028 | factual | ✅ PASS | 1.00 | 1.00 | 8475 |
| gs029 | factual | ✅ PASS | 1.00 | 1.00 | 6476 |
| gs030 | factual | ✅ PASS | 1.00 | 1.00 | 7393 |
| gs031 | factual | ✅ PASS | 1.00 | 1.00 | 9750 |
| gs032 | factual | ✅ PASS | 1.00 | 1.00 | 6682 |
| gs033 | factual | ✅ PASS | 1.00 | 1.00 | 7572 |
| gs034 | factual | ✅ PASS | 1.00 | 1.00 | 6996 |
| gs035 | multi_hop | ✅ PASS | 1.00 | 1.00 | 9138 |
| gs036 | multi_hop | ✅ PASS | 1.00 | 1.00 | 9203 |
| gs037 | multi_hop | ✅ PASS | 1.00 | 1.00 | 7580 |
| gs038 | multi_hop | ✅ PASS | 1.00 | 1.00 | 8393 |
| gst01 | trap | ✅ PASS | n/a | n/a | 29199 |
| gst02 | trap | ✅ PASS | n/a | n/a | 18529 |
| gst03 | trap | ✅ PASS | n/a | n/a | 24201 |
| gst04 | trap | ✅ PASS | n/a | n/a | 22294 |
| gst05 | trap | ✅ PASS | n/a | n/a | 12490 |
| gst06 | trap | ✅ PASS | n/a | n/a | 28566 |
| gst07 | trap | ✅ PASS | n/a | n/a | 18731 |
| gst08 | trap | ✅ PASS | n/a | n/a | 8914 |
| gst09 | trap | ✅ PASS | n/a | n/a | 30200 |
| gst10 | trap | ✅ PASS | n/a | n/a | 18434 |
| gst11 | trap | ✅ PASS | n/a | n/a | 18721 |
| gst12 | trap | ✅ PASS | n/a | n/a | 21941 |

**Answerable-item averages**

- Faithfulness: 1.00
- Context recall: 1.00
- Answer relevancy: 0.89

**Cost and latency**

- p50 latency: 8218 ms &middot; p95 latency: 28914 ms (mean: 12802 ms)
- Total tokens: 87595 prompt + 3383 completion
- Estimated cost (illustrative pricing, not official rates): $0.00758 total, $0.000152/task
