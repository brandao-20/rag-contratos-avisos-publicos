"""Avaliação simples do retrieval em dataset golden."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config
from src.embeddings import get_embeddings
from src.rag_pipeline import RAGPipeline
from src.vector_store import load_vector_store


def main() -> None:
    golden = json.loads(config.GOLDEN_QA_FILE.read_text(encoding="utf-8"))
    embeddings = get_embeddings(config.get_model_names()[0])
    pipeline = RAGPipeline(load_vector_store(embeddings), top_k=6)
    rows = []
    correct = 0
    for case in golden:
        result = pipeline.ask(case["query"], top_k=6)
        source_ids = [g["source_id"] for g in result.sources_grouped]
        hit = case.get("expected_source_id") in source_ids if case.get("should_answer", True) else result.confidence_label == "baixa"
        correct += int(bool(hit))
        rows.append({
            "id": case["id"],
            "query": case["query"],
            "hit": bool(hit),
            "sources": source_ids,
            "confidence": result.confidence_label,
        })
    report = {"total": len(rows), "hits": correct, "accuracy": correct / max(1, len(rows)), "rows": rows}
    out = ROOT / "tests" / "golden_report_publicos.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"accuracy": report["accuracy"], "hits": correct, "total": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
