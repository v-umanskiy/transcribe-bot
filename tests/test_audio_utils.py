from utils import audio_utils


def test_extract_audio_info_voice():
    voice = {"file_id": "voice123", "duration": 12, "file_size": 2048}
    result = audio_utils.extract_audio_info(voice, None, None)
    assert result == ("voice123", "voices/voice123.ogg", "ogg", "ogg", 12, 2048, None)


def test_extract_audio_info_document_with_valid_extension():
    document = {"file_id": "doc123", "file_name": "sample.wav", "mime_type": "audio/wav"}
    result = audio_utils.extract_audio_info(None, document, None)
    assert result == ("doc123", "audiofiles/doc123.wav", "wav", "wav", None, None, None)


def test_extract_audio_info_audio_with_mime_type_extension():
    audio = {"file_id": "audio123", "file_name": "track", "mime_type": "audio/mpeg"}
    result = audio_utils.extract_audio_info(None, None, audio)
    assert result == ("audio123", "audiofiles/audio123.mp3", "mp3", "mp3", None, None, None)


def test_extract_audio_info_invalid_extension():
    audio = {"file_id": "audio123", "file_name": "track.txt"}
    result = audio_utils.extract_audio_info(None, None, audio)
    assert result[-1] is not None


def test_extract_audio_info_missing_file_id():
    audio = {"file_name": "track.mp3"}
    result = audio_utils.extract_audio_info(None, None, audio)
    assert result[-1] is not None
