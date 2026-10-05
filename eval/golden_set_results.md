# Golden Set Results

Run against all 50 items in `eval/golden_set.json` (38 answerable, 12 traps) through the real corrective-RAG graph.

**Overall: 50/50 passed (12/12 traps correctly refused).**

A trap "pass" means the model refused rather than fabricating an answer. This is the metric that actually matters for a bid team, since a hallucinated commercial term in a real proposal is far more costly than a missed factual lookup.

| ID | Category | Result | Faithfulness | Context Recall | Latency (ms) |
|---|---|---|---|---|---|
| gs001 | factual | ✅ PASS | 1.00 | 1.00 | 8774 |
| gs002 | factual | ✅ PASS | 1.00 | 1.00 | 5595 |
| gs003 | factual | ✅ PASS | 1.00 | 1.00 | 5639 |
| gs004 | factual | ✅ PASS | 1.00 | 1.00 | 6074 |
| gs005 | factual | ✅ PASS | 1.00 | 1.00 | 9103 |
| gs006 | factual | ✅ PASS | 1.00 | 1.00 | 15082 |
| gs007 | factual | ✅ PASS | 1.00 | 1.00 | 6128 |
| gs008 | factual | ✅ PASS | 1.00 | 1.00 | 5627 |
| gs009 | factual | ✅ PASS | 1.00 | 1.00 | 6600 |
| gs010 | factual | ✅ PASS | 1.00 | 1.00 | 7119 |
| gs011 | factual | ✅ PASS | 1.00 | 1.00 | 7802 |
| gs012 | factual | ✅ PASS | 1.00 | 1.00 | 5854 |
| gs013 | factual | ✅ PASS | 1.00 | 1.00 | 5156 |
| gs014 | factual | ✅ PASS | 1.00 | 1.00 | 5842 |
| gs015 | factual | ✅ PASS | 1.00 | 1.00 | 5978 |
| gs016 | factual | ✅ PASS | 1.00 | 1.00 | 5875 |
| gs017 | factual | ✅ PASS | 1.00 | 1.00 | 7506 |
| gs018 | factual | ✅ PASS | 1.00 | 1.00 | 4734 |
| gs019 | factual | ✅ PASS | 1.00 | 1.00 | 6284 |
| gs020 | factual | ✅ PASS | 1.00 | 1.00 | 16126 |
| gs021 | factual | ✅ PASS | 1.00 | 1.00 | 4822 |
| gs022 | factual | ✅ PASS | 1.00 | 1.00 | 25819 |
| gs023 | factual | ✅ PASS | 1.00 | 1.00 | 7455 |
| gs024 | factual | ✅ PASS | 1.00 | 1.00 | 7383 |
| gs025 | factual | ✅ PASS | 1.00 | 1.00 | 6128 |
| gs026 | factual | ✅ PASS | 1.00 | 1.00 | 5414 |
| gs027 | factual | ✅ PASS | 1.00 | 1.00 | 6719 |
| gs028 | factual | ✅ PASS | 1.00 | 1.00 | 9230 |
| gs029 | factual | ✅ PASS | 1.00 | 1.00 | 6010 |
| gs030 | factual | ✅ PASS | 1.00 | 1.00 | 8026 |
| gs031 | factual | ✅ PASS | 1.00 | 1.00 | 6309 |
| gs032 | factual | ✅ PASS | 1.00 | 1.00 | 8064 |
| gs033 | factual | ✅ PASS | 1.00 | 1.00 | 6492 |
| gs034 | factual | ✅ PASS | 1.00 | 1.00 | 5815 |
| gs035 | multi_hop | ✅ PASS | 1.00 | 1.00 | 8167 |
| gs036 | multi_hop | ✅ PASS | 1.00 | 1.00 | 8083 |
| gs037 | multi_hop | ✅ PASS | 1.00 | 1.00 | 8437 |
| gs038 | multi_hop | ✅ PASS | 1.00 | 1.00 | 8086 |
| gst01 | trap | ✅ PASS | n/a | n/a | 33085 |
| gst02 | trap | ✅ PASS | n/a | n/a | 17817 |
| gst03 | trap | ✅ PASS | n/a | n/a | 23137 |
| gst04 | trap | ✅ PASS | n/a | n/a | 19148 |
| gst05 | trap | ✅ PASS | n/a | n/a | 20499 |
| gst06 | trap | ✅ PASS | n/a | n/a | 24603 |
| gst07 | trap | ✅ PASS | n/a | n/a | 19244 |
| gst08 | trap | ✅ PASS | n/a | n/a | 9658 |
| gst09 | trap | ✅ PASS | n/a | n/a | 14751 |
| gst10 | trap | ✅ PASS | n/a | n/a | 22224 |
| gst11 | trap | ✅ PASS | n/a | n/a | 19037 |
| gst12 | trap | ✅ PASS | n/a | n/a | 18431 |

**Answerable-item averages**

- Faithfulness: 1.00
- Context recall: 1.00
- Answer relevancy: 0.88

**Cost and latency**

- p50 latency: 7654 ms &middot; p95 latency: 23943 ms (mean: 10700 ms)
- Total tokens: 83319 prompt + 3329 completion
- Estimated cost (illustrative pricing, not official rates): $0.00725 total, $0.000145/task
