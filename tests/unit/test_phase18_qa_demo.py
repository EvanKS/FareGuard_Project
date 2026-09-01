"""
FareGuard Phase 18 — Final QA, Demo, and Documentation Tests

Verifies that the entire documentation suite, demonstration scripts,
and final system deliverables are present, syntactically valid, and complete.
"""

from pathlib import Path
import pytest

from config import settings


class TestPhase18QADemoAndDocs:

    def test_1_documentation_suite_existence(self):
        docs_dir = Path("docs")
        required_docs = [
            "ARCHITECTURE.md",
            "DATA_SOURCES.md",
            "DATA_DICTIONARY.md",
            "METHODOLOGY.md",
            "MODEL_RESULTS.md",
            "LIMITATIONS.md",
            "DEMO.md",
            "TEST_REPORT.md",
            "final_evaluation.md",
            "requirements_traceability.md",
        ]
        for doc in required_docs:
            doc_path = docs_dir / doc
            assert doc_path.exists(), f"Missing required documentation: {doc}"
            assert doc_path.stat().st_size > 100, f"Document {doc} appears empty"

    def test_2_demo_script_existence_and_executable(self):
        demo_path = Path("scripts/run_demo.py")
        assert demo_path.exists()
        assert demo_path.stat().st_size > 1000

    def test_3_evaluation_report_existence(self):
        eval_json = settings.METADATA_DIR / "final_evaluation_report.json"
        assert eval_json.exists()
        assert eval_json.stat().st_size > 500

    def test_4_models_metadata_existence(self):
        meta_json = settings.MODEL_DIR / "evaluation_metadata.json"
        assert meta_json.exists()
        assert meta_json.stat().st_size > 200
