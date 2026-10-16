import pytest

from app.youtube import extract_video_id, is_youtube_url

ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "text",
    [
        f"https://www.youtube.com/watch?v={ID}",
        f"https://youtube.com/watch?v={ID}&list=PL123&t=42",
        f"https://m.youtube.com/watch?v={ID}",
        f"https://music.youtube.com/watch?v={ID}&si=abc",
        f"https://youtu.be/{ID}?t=10",
        f"https://www.youtube.com/shorts/{ID}",
        f"https://www.youtube.com/embed/{ID}",
        f"youtube.com/watch?v={ID}",
        f"  https://youtu.be/{ID}  ",
    ],
)
def test_extracts_id(text):
    assert extract_video_id(text) == ID


@pytest.mark.parametrize(
    "text",
    [
        "https://www.youtube.com/playlist?list=PL123",
        "https://www.youtube.com/watch?v=tooshort",
        "https://www.youtube.com/@somechannel",
    ],
)
def test_youtube_url_without_video(text):
    assert is_youtube_url(text)
    assert extract_video_id(text) is None


@pytest.mark.parametrize("text", ["lofi beats", "radiohead12", "https://vimeo.com/123", "notyoutube.com/watch?v=" + ID, ""])
def test_not_youtube(text):
    assert not is_youtube_url(text)
    assert extract_video_id(text) is None
