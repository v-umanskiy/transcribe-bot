from utils import text_utils


def test_split_by_length_round_trip():
    text = "a" * 9001
    parts = text_utils.split_by_length(text, max_len=3500)
    assert all(0 < len(p) <= 3500 for p in parts)
    assert "".join(parts) == text
