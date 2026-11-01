STAGES = ["INGESTION", "RETRIEVAL", "DRAFTING", "CRITIQUE", "ESCALATION"]

SEGMENTS = [
    {
        "id": "00_open",
        "kind": "diagram",
        "title": "Proposal-Response Assistant",
        "subtitle": "Every claim gets a trial before it reaches you",
        "active_stages": STAGES,
        "narration": (
            "Picture this architecture as a courtroom. Retrieval gathers the evidence. Drafting "
            "makes the argument. Critique cross-examines it before it ever reaches you. Escalation "
            "is the appeal, for when the evidence does not hold up. Most AI pilots skip the "
            "courtroom entirely and let the model rule in its own case. This is a proposal "
            "response assistant built for a professional services bid team, and I am going to "
            "walk four of those five stages, live, to show you where this one is built to fail "
            "safely instead of failing silently."
        ),
    },
    {
        "id": "01_beat1",
        "kind": "terminal",
        "header": "Stage: Retrieval — the evidence, examined first",
        "active_stages": ["RETRIEVAL"],
        "body": (
            '$ cat eval/golden_set.json | grep -A2 \'"id": "gst03"\'\n\n'
            '{"id": "gst03", "category": "trap",\n'
            ' "question": "What is the day rate for Consultant James Okafor?",\n'
            ' "expected_behavior": "refusal",\n'
            ' "notes": "No such individual appears anywhere in the corpus."}\n\n'
            "$ cat eval/golden_set_metrics.json\n\n"
            '{"label": "golden set", "message": "50/50 (100%)", "color": "brightgreen"}'
        ),
        "narration": (
            "Start with retrieval, the stage that decides what the model is even allowed to see. "
            "The failure case first, because that is the one that costs real money. This exact "
            "question, the day rate for a consultant who does not exist anywhere in this firm's "
            "documents, is trap item g s t zero three in the golden set, the architecture's own "
            "regression suite for grounding. A production system earns trust through a "
            "regression suite, not a one-off live demo, and that is the standard this repo holds "
            "itself to. The golden set scored fifty out of fifty on its last run, every trap "
            "question included, and the full methodology is public in the repo, not just "
            "asserted."
        ),
    },
    {
        "id": "02_beat2",
        "kind": "terminal",
        "header": "Stage: Drafting & critique — the argument and its cross-examination",
        "active_stages": ["DRAFTING", "CRITIQUE"],
        "body": (
            "$ cat sample_docs/proposal_corpus/rate_card.md\n\n"
            "| Role                 | Day rate |\n"
            "|----------------------|----------|\n"
            "| Engagement Director  | £1,450   |\n"
            "| Senior Consultant    | £1,050   |\n"
            "| Consultant           | £750     |\n\n"
            "$ grep -n _CITATION_MARKER app/services/rag_graph.py\n"
            "critique_node: checks for [Source N] on every answer before it reaches the screen"
        ),
        "narration": (
            "Now the drafting and critique stages, the question this architecture should "
            "actually answer. The real source document, the rate card, states a Senior "
            "Consultant is one thousand and fifty pounds per day, excluding VAT. Every claim "
            "this system drafts is required to trace back to a specific document like this one, "
            "not plausible sounding text. That citation is not decorative. A dedicated node in "
            "the graph, critique node, checks for it on every single answer before it ever "
            "reaches the screen. Drafting proposes, critique disposes. If the citation is "
            "missing, the system does not let it through."
        ),
    },
    {
        "id": "03_beat3",
        "kind": "terminal",
        "header": "Stage: Escalation — the appeal, when the evidence doesn't hold",
        "active_stages": ["ESCALATION"],
        "body": (
            "$ pytest tests/test_rag_graph.py -k escalation -v\n\n"
            "test_escalation_banner_added_when_retries_exhausted_still_ungrounded  PASSED\n"
            "test_escalation_banner_added_when_retries_exhausted_still_uncited     PASSED\n"
            "test_no_escalation_when_faithful_and_cited_first_time                PASSED\n\n"
            "3 passed in 3.93s"
        ),
        "narration": (
            "Citation enforcement and a faithfulness check are the gate. Escalation is the "
            "architecture's answer to what happens when that gate fails. I cannot reliably force "
            "the live model to fail on camera, that is the point, it is supposed to be rare, so "
            "here is the test suite proving the retry then escalate path actually works, not "
            "just described in a doc. Three tests: an ungrounded answer gets retried and then "
            "escalated with a review banner once the retry cap is hit, the same path triggers "
            "for a missing citation, and a well behaved answer on the first pass is never "
            "flagged at all. No silent failure state anywhere in that path."
        ),
    },
    {
        "id": "04_beat4",
        "kind": "terminal",
        "header": "Stage: Ingestion — chain of custody, before the trial starts",
        "active_stages": ["INGESTION"],
        "body": (
            "$ curl -X POST localhost:8000/documents \\\n"
            "    -F file=@synthetic_bank_details_test.txt\n\n"
            "HTTP/1.1 422 Unprocessable Entity\n\n"
            '{"detail": "Rejected: this document looks like it contains real\n'
            " personal/financial data (UK bank sort code, UK bank account\n"
            " number). Only synthetic/sample documents should be ingested\n"
            ' here. See docs/DEPLOYMENT.md."}'
        ),
        "narration": (
            "The fourth stage is not about the answer, it is about what gets ingested before "
            "retrieval ever runs. This firm's real demo once had a tuition payment letter with "
            "real bank details reach the public corpus by accident, because ingestion had no "
            "control on it at all. Here is the fix, live. Rejected, HTTP four twenty two, naming "
            "the exact pattern found, a UK sort code, before the file ever touches the vector "
            "store or the disk. On by default. Architecture, not a checklist item someone has to "
            "remember."
        ),
    },
    {
        "id": "05_close",
        "kind": "scorecard",
        "header": "The verdict: one honest scorecard",
        "active_stages": STAGES,
        "narration": (
            "Ingestion, retrieval, drafting, critique, escalation. Four of those five stages, "
            "live on camera. All four map onto a fifteen point production readiness scorecard I "
            "built for exactly this problem, the architecture decisions that separate a demo "
            "from something that survives contact with a real engagement. As of today this repo "
            "is nine demonstrated, five partial, and genuinely one open: per user access "
            "control, a single shared API key for now, not a per tenant permission model. I am "
            "not going to pretend that one is solved. An honest gap list is worth more than a "
            "perfect score nobody checked."
        ),
    },
    {
        "id": "06_signoff",
        "kind": "title",
        "title": "github.com/vishnu0529/enterprise-rag-assistant",
        "subtitle": "The full architecture, reproducible from the public repo",
        "narration": (
            "Every stage in this video is reproducible from the public repo: the tests, the "
            "golden set, the scorecard, the architecture itself. The link is in the description. "
            "No stage in this courtroom skips its evidence, its argument, or its "
            "cross-examination. If you are evaluating an agent pilot and want to know which of "
            "these fifteen architecture decisions it actually made, that is the review I offer."
        ),
    },
]
