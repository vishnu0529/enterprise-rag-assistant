"""Renders the real compiled corrective-RAG graph to docs/graph.png.

Generated directly from the actual StateGraph object via LangGraph's own
get_graph().draw_mermaid_png(), not hand-drawn, so it can never silently
drift out of sync with the real node/edge structure the way a manually
maintained diagram can. Rerun this after any change to build_graph() in
app/services/rag_graph.py.

Requires network access (calls the public mermaid.ink rendering service via
LangGraph's default draw method), a manual regeneration step, not wired
into CI.

Usage:
    ./venv/bin/python scripts/render_graph.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rag_graph import get_graph


def main() -> None:
    graph = get_graph()
    png_bytes = graph.get_graph().draw_mermaid_png()

    out_path = Path(__file__).resolve().parent.parent / "docs" / "graph.png"
    out_path.write_bytes(png_bytes)
    print(f"Wrote {len(png_bytes)} bytes to {out_path}")


if __name__ == "__main__":
    main()
