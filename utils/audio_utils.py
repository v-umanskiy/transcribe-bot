
def extract_audio_info(
    voice: dict | None,
    document: dict | None,
    audio: dict | None,
) -> tuple[str | None, str | None, str | None, str | None, int | None, int | None, str | None]:
    if voice:
        file_id = voice.get("file_id")
        if not file_id:
            return None, None, None, None, None, None, "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg)."
        duration = voice.get("duration")
        file_size = voice.get("file_size")
        file_key = f"voices/{file_id}.ogg"
        return file_id, file_key, "ogg", "ogg", duration, file_size, None

    source = document or audio
    if not source:
        return None, None, None, None, None, None, "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg)."
    file_id = source.get("file_id")
    file_name = (source.get("file_name") or "").lower()
    mime_type = (source.get("mime_type") or "").lower()
    duration = source.get("duration")
    file_size = source.get("file_size")
    ext = ""
    if "." in file_name:
        ext = file_name.rsplit(".", 1)[-1]

    mime_to_ext = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/flac": "flac",
        "audio/ogg": "ogg",
        "audio/mp4": "mp4",
        "audio/x-m4a": "m4a",
        "audio/m4a": "m4a",
    }
    if not ext and mime_type in mime_to_ext:
        ext = mime_to_ext[mime_type]

    supported = {"mp3": "mp3", "wav": "wav", "flac": "flac", "ogg": "ogg", "m4a": "mp4", "mp4": "mp4"}
    if ext not in supported or not file_id:
        return None, None, None, None, None, None, "Please send a voice message or an audio file (.wav, .mp3, .m4a, .flac, .ogg)."

    file_key = f"audiofiles/{file_id}.{ext}"
    return file_id, file_key, supported[ext], ext, duration, file_size, None