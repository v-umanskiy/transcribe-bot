from utils import text_utils


def test_looks_like_drive_link():
    assert text_utils.looks_like_drive_link("") is False
    assert text_utils.looks_like_drive_link("https://drive.google.com/file/d/123") is True
    assert text_utils.looks_like_drive_link("https://docs.google.com/document/d/123") is True
    assert text_utils.looks_like_drive_link("https://example.com") is False


def test_split_into_chunks_empty():
    assert text_utils.split_into_chunks("") == []


def test_split_into_chunks_short():
    text = "Hello world."
    assert text_utils.split_into_chunks(text, max_chars=3000) == [text]


def test_split_into_chunks_long():
    text = "Hello world. " * 400
    chunks = text_utils.split_into_chunks(text, max_chars=300)
    assert all(0 < len(chunk) <= 300 for chunk in chunks)
    assert " ".join(chunk.strip() for chunk in chunks).replace("  ", " ").startswith("Hello world")


def test_split_by_length_round_trip():
    text = "a" * 9001
    parts = text_utils.split_by_length(text, max_len=3500)
    assert all(0 < len(p) <= 3500 for p in parts)
    assert "".join(parts) == text
