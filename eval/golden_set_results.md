# Golden Set Results

Run against all 50 items in `eval/golden_set.json` (38 answerable, 12 traps) through the real corrective-RAG graph.

**Overall: 44/50 passed (12/12 traps correctly refused).**

A trap "pass" means the model refused rather than fabricating an answer. This is the metric that actually matters for a bid team, since a hallucinated commercial term in a real proposal is far more costly than a missed factual lookup.

| ID | Category | Result | Faithfulness | Context Recall | Latency (ms) |
|---|---|---|---|---|---|
| gs001 | factual | ✅ PASS | 1.00 | 1.00 | 7109 |
| gs002 | factual | ✅ PASS | 1.00 | 1.00 | 7526 |
| gs003 | factual | ✅ PASS | 1.00 | 1.00 | 6000 |
| gs004 | factual | ✅ PASS | 1.00 | 1.00 | 4578 |
| gs005 | factual | ✅ PASS | 1.00 | 1.00 | 17147 |
| gs006 | factual | ❌ FAIL | 0.50 | 0.00 | 28954 |
| gs007 | factual | ✅ PASS | 1.00 | 1.00 | 10146 |
| gs008 | factual | ✅ PASS | 1.00 | 1.00 | 34351 |
| gs009 | factual | ✅ PASS | 1.00 | 1.00 | 6352 |
| gs010 | factual | ✅ PASS | 1.00 | 1.00 | 7366 |
| gs011 | factual | ✅ PASS | 1.00 | 1.00 | 20179 |
| gs012 | factual | ✅ PASS | 1.00 | 1.00 | 5692 |
| gs013 | factual | ✅ PASS | 1.00 | 1.00 | 7620 |
| gs014 | factual | ✅ PASS | 1.00 | 1.00 | 7031 |
| gs015 | factual | ✅ PASS | 1.00 | 1.00 | 7863 |
| gs016 | factual | ✅ PASS | 1.00 | 1.00 | 6190 |
| gs017 | factual | ✅ PASS | 1.00 | 1.00 | 6356 |
| gs018 | factual | ✅ PASS | 1.00 | 1.00 | 5536 |
| gs019 | factual | ✅ PASS | 1.00 | 1.00 | 7010 |
| gs020 | factual | ❌ FAIL | 0.50 | 0.00 | 31836 |
| gs021 | factual | ✅ PASS | 1.00 | 1.00 | 7789 |
| gs022 | factual | ❌ FAIL | 0.50 | 0.00 | 30964 |
| gs023 | factual | ✅ PASS | 1.00 | 1.00 | 16008 |
| gs024 | factual | ❌ FAIL | 0.50 | 0.00 | 23416 |
| gs025 | factual | ✅ PASS | 1.00 | 1.00 | 6558 |
| gs026 | factual | ✅ PASS | 1.00 | 1.00 | 6205 |
| gs027 | factual | ✅ PASS | 1.00 | 1.00 | 6404 |
| gs028 | factual | ✅ PASS | 1.00 | 1.00 | 10326 |
| gs029 | factual | ✅ PASS | 1.00 | 1.00 | 7663 |
| gs030 | factual | ✅ PASS | 1.00 | 1.00 | 7640 |
| gs031 | factual | ✅ PASS | 1.00 | 1.00 | 7895 |
| gs032 | factual | ✅ PASS | 1.00 | 1.00 | 27817 |
| gs033 | factual | ✅ PASS | 1.00 | 1.00 | 18539 |
| gs034 | factual | ❌ FAIL | 0.50 | 0.50 | 24790 |
| gs035 | multi_hop | ✅ PASS | 1.00 | 1.00 | 7801 |
| gs036 | multi_hop | ❌ FAIL | 0.50 | 1.00 | 42144 |
| gs037 | multi_hop | ✅ PASS | 1.00 | 1.00 | 8194 |
| gs038 | multi_hop | ✅ PASS | 1.00 | 1.00 | 10564 |
| gst01 | trap | ✅ PASS | n/a | n/a | 36864 |
| gst02 | trap | ✅ PASS | n/a | n/a | 21043 |
| gst03 | trap | ✅ PASS | n/a | n/a | 21938 |
| gst04 | trap | ✅ PASS | n/a | n/a | 18590 |
| gst05 | trap | ✅ PASS | n/a | n/a | 25407 |
| gst06 | trap | ✅ PASS | n/a | n/a | 17931 |
| gst07 | trap | ✅ PASS | n/a | n/a | 19254 |
| gst08 | trap | ✅ PASS | n/a | n/a | 9492 |
| gst09 | trap | ✅ PASS | n/a | n/a | 22896 |
| gst10 | trap | ✅ PASS | n/a | n/a | 21973 |
| gst11 | trap | ✅ PASS | n/a | n/a | 18986 |
| gst12 | trap | ✅ PASS | n/a | n/a | 19738 |

**Answerable-item averages**

- Faithfulness: 0.92
- Context recall: 0.88
- Answer relevancy: 0.87

**Cost and latency**

- p50 latency: 10236 ms &middot; p95 latency: 33219 ms (mean: 15193 ms)
- Total tokens: 57019 prompt + 3492 completion
- Estimated cost (illustrative pricing, not official rates): $0.00532 total, $0.000106/task

## Failed items (for debugging)

- **gs006**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided corpus does
- **gs020**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided corpus does
- **gs022**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided corpus does
- **gs024**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided corpus does
- **gs034**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The provided context doe
- **gs036**: ⚠️ **Needs bid-director review before use.** This answer was not well-grounded after 3 attempt(s) (faithfulness 0.50/1.0). Do not put it in a proposal without human sign-off.

The retail digital opera
