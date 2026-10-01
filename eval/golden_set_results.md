# Golden Set Results

Run against all 50 items in `eval/golden_set.json` (38 answerable, 12 traps) through the real corrective-RAG graph.

**Overall: 48/50 passed (12/12 traps correctly refused).**

A trap "pass" means the model refused rather than fabricating an answer. This is the metric that actually matters for a bid team, since a hallucinated commercial term in a real proposal is far more costly than a missed factual lookup.

| ID | Category | Result | Faithfulness | Context Recall | Latency (ms) |
|---|---|---|---|---|---|
| gs001 | factual | ✅ PASS | 1.00 | 1.00 | 24025 |
| gs002 | factual | ✅ PASS | 1.00 | 1.00 | 9531 |
| gs003 | factual | ✅ PASS | 1.00 | 1.00 | 6021 |
| gs004 | factual | ✅ PASS | 1.00 | 1.00 | 9889 |
| gs005 | factual | ✅ PASS | 1.00 | 1.00 | 10049 |
| gs006 | factual | ❌ FAIL | 0.50 | 0.00 | 31149 |
| gs007 | factual | ✅ PASS | 1.00 | 1.00 | 7689 |
| gs008 | factual | ✅ PASS | 1.00 | 1.00 | 10451 |
| gs009 | factual | ✅ PASS | 1.00 | 1.00 | 7744 |
| gs010 | factual | ✅ PASS | 1.00 | 1.00 | 11991 |
| gs011 | factual | ✅ PASS | 1.00 | 1.00 | 8199 |
| gs012 | factual | ✅ PASS | 1.00 | 1.00 | 6755 |
| gs013 | factual | ✅ PASS | 1.00 | 1.00 | 6127 |
| gs014 | factual | ✅ PASS | 1.00 | 1.00 | 5534 |
| gs015 | factual | ✅ PASS | 1.00 | 1.00 | 8713 |
| gs016 | factual | ✅ PASS | 1.00 | 1.00 | 7987 |
| gs017 | factual | ✅ PASS | 1.00 | 1.00 | 7485 |
| gs018 | factual | ✅ PASS | 1.00 | 1.00 | 6520 |
| gs019 | factual | ✅ PASS | 1.00 | 1.00 | 7072 |
| gs020 | factual | ✅ PASS | 1.00 | 1.00 | 25604 |
| gs021 | factual | ✅ PASS | 1.00 | 1.00 | 7484 |
| gs022 | factual | ❌ FAIL | 0.50 | 0.00 | 30651 |
| gs023 | factual | ✅ PASS | 1.00 | 1.00 | 8962 |
| gs024 | factual | ✅ PASS | 1.00 | 1.00 | 6312 |
| gs025 | factual | ✅ PASS | 1.00 | 1.00 | 6152 |
| gs026 | factual | ✅ PASS | 1.00 | 1.00 | 6025 |
| gs027 | factual | ✅ PASS | 1.00 | 1.00 | 5962 |
| gs028 | factual | ✅ PASS | 1.00 | 1.00 | 8651 |
| gs029 | factual | ✅ PASS | 1.00 | 1.00 | 5860 |
| gs030 | factual | ✅ PASS | 1.00 | 1.00 | 9383 |
| gs031 | factual | ✅ PASS | 1.00 | 1.00 | 9440 |
| gs032 | factual | ✅ PASS | 1.00 | 1.00 | 7987 |
| gs033 | factual | ✅ PASS | 1.00 | 1.00 | 7176 |
| gs034 | factual | ✅ PASS | 1.00 | 1.00 | 43915 |
| gs035 | multi_hop | ✅ PASS | 1.00 | 1.00 | 6963 |
| gs036 | multi_hop | ✅ PASS | 1.00 | 1.00 | 26512 |
| gs037 | multi_hop | ✅ PASS | 1.00 | 1.00 | 9143 |
| gs038 | multi_hop | ✅ PASS | 1.00 | 1.00 | 10046 |
| gst01 | trap | ✅ PASS | n/a | n/a | 34797 |
| gst02 | trap | ✅ PASS | n/a | n/a | 20433 |
| gst03 | trap | ✅ PASS | n/a | n/a | 33363 |
| gst04 | trap | ✅ PASS | n/a | n/a | 22753 |
| gst05 | trap | ✅ PASS | n/a | n/a | 13511 |
| gst06 | trap | ✅ PASS | n/a | n/a | 36155 |
| gst07 | trap | ✅ PASS | n/a | n/a | 12387 |
| gst08 | trap | ✅ PASS | n/a | n/a | 8436 |
| gst09 | trap | ✅ PASS | n/a | n/a | 26534 |
| gst10 | trap | ✅ PASS | n/a | n/a | 19588 |
| gst11 | trap | ✅ PASS | n/a | n/a | 21108 |
| gst12 | trap | ✅ PASS | n/a | n/a | 21813 |

**Answerable-item averages**

- Faithfulness: 0.97
- Context recall: 0.95
- Answer relevancy: 0.88

**Cost and latency**

- p50 latency: 9263 ms &middot; p95 latency: 34152 ms (mean: 14121 ms)
- Total tokens: 94865 prompt + 3574 completion
- Estimated cost (illustrative pricing, not official rates): $0.00819 total, $0.000164/task

## Failed items (for debugging)

- **gs006**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided corpus does
- **gs022**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided corpus does
