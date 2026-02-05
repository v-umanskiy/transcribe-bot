import re


def split_into_chunks(text: str, max_chars: int = 3000) -> list[str]:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for start in range(0, len(sentence), max_chars):
                part = sentence[start:start + max_chars]
                chunks.append(part.strip())
            continue

        if not current:
            current = sentence
            continue

        if len(current) + 1 + len(sentence) <= max_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current.strip())
            current = sentence

    if current:
        chunks.append(current.strip())

    return chunks
