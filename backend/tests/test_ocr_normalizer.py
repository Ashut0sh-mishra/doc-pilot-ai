from ocr_worker.normalizer import normalize_paddle_results


def test_normalizes_lines_and_flags_low_confidence():
    raw = [{"res": {"page_index": 0, "rec_texts": ["Metformin 500 mg", "Illegible note"], "rec_scores": [0.98, 0.62], "rec_boxes": [[1, 2, 30, 12], [1, 15, 40, 28]]}}]
    result = normalize_paddle_results(raw, "record-1")
    assert result["schema_version"] == "1.0"
    assert result["document"]["page_count"] == 1
    assert result["pages"][0]["lines"][1]["needs_review"] is True
    assert result["metrics"]["low_confidence_lines"] == 1
    assert "Metformin" in result["full_text"]
