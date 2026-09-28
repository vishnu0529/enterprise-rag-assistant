from contextlib import ExitStack

from opentelemetry import trace
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core.tracing import get_tracer
from app.services.rag_graph import answer_question_agentic
from tests.test_rag_graph import apply_patches


def _capture_spans():
    """Adds an extra span processor to whatever tracer provider is already
    active (get_tracer() lazily creates one on first use, real code or
    tests), doesn't touch global setup, just observes. OTel supports
    multiple processors on one provider by design; this is the documented
    pattern for inspecting spans in tests without a real backend."""
    get_tracer()
    exporter = InMemorySpanExporter()
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def test_a_full_run_produces_a_span_per_node_plus_a_parent_span():
    exporter = _capture_spans()
    with ExitStack() as stack:
        apply_patches(stack)
        answer_question_agentic("How many annual leave days?", session_id="trace-test-1")

    names = {s.name for s in exporter.get_finished_spans()}
    assert names == {
        "answer_question",
        "recall_memory",
        "strategize",
        "retrieve",
        "draft",
        "critique",
        "escalate",
        "approval_gate",
        "remember",
    }


def test_spans_share_one_trace_id_and_nest_under_the_parent():
    exporter = _capture_spans()
    with ExitStack() as stack:
        apply_patches(stack)
        answer_question_agentic("How many annual leave days?", session_id="trace-test-2")

    spans = exporter.get_finished_spans()
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1  # one request, one trace

    parent = next(s for s in spans if s.name == "answer_question")
    children = [s for s in spans if s.name != "answer_question"]
    assert all(c.parent.span_id == parent.context.span_id for c in children)


def test_strategize_span_records_the_actual_search_plan():
    exporter = _capture_spans()
    with ExitStack() as stack:
        apply_patches(stack)
        answer_question_agentic("How many annual leave days?", session_id="trace-test-3")

    strategize_span = next(s for s in exporter.get_finished_spans() if s.name == "strategize")
    assert strategize_span.attributes["rag.sub_queries"] == "annual leave days"
    assert strategize_span.attributes["rag.top_k"] == 4


def test_no_documents_short_circuit_still_produces_a_trace():
    exporter = _capture_spans()
    with ExitStack() as stack:
        apply_patches(stack, search=lambda *a, **k: [])
        answer_question_agentic("Anything?", session_id="trace-test-4")

    names = {s.name for s in exporter.get_finished_spans()}
    assert "no_documents" in names
    assert "draft" not in names  # never reached, proves the trace reflects the real path taken


def test_parent_span_records_cost_and_latency():
    exporter = _capture_spans()
    with ExitStack() as stack:
        apply_patches(stack)
        answer_question_agentic("How many annual leave days?", session_id="trace-test-5")

    parent = next(s for s in exporter.get_finished_spans() if s.name == "answer_question")
    assert parent.attributes["rag.cost_usd"] >= 0
    assert parent.attributes["rag.latency_ms"] >= 0
    assert parent.attributes["rag.pending_approval"] is False
