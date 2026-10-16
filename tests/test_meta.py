import pytest

from app.meta import TrackMeta, parse_title, safe_name


@pytest.mark.parametrize(
    "title, channel, expected",
    [
        ("Rick Astley - Never Gonna Give You Up (Official Music Video)", "Rick Astley",
         ("Rick Astley", "Never Gonna Give You Up")),
        ("Daft Punk – Get Lucky [Official Audio] (HD)", "DaftPunkVEVO", ("Daft Punk", "Get Lucky")),
        ("Bohemian Rhapsody", "QueenVEVO", ("Queen", "Bohemian Rhapsody")),
        ("Song Name (Lyrics)", "Some Band - Topic", ("Some Band", "Song Name")),
        ('Phoebe Bridgers - "Motion Sickness"', "Dead Oceans", ("Phoebe Bridgers", "Motion Sickness")),
        ("Track (feat. Someone) [Official Video]", "Artist", ("Artist", "Track (feat. Someone)")),
        ("", "", ("Unknown Artist", "Untitled")),
    ],
)
def test_parse_title(title, channel, expected):
    meta = parse_title(title, channel)
    assert (meta.artist, meta.title) == expected
    assert meta.album == meta.title


def test_parse_title_prefers_real_metadata():
    meta = parse_title("garbage title", "whatever", artist="Real Artist", track="Real Track", album="Real Album")
    assert meta == TrackMeta("Real Artist", "Real Track", "Real Album")


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("AC/DC", "ACDC"),
        ("What? Why: <no>", "What Why no"),
        ("..", "untitled"),
        ("../../etc/passwd", "etcpasswd"),
        ("", "untitled"),
    ],
)
def test_safe_name(raw, expected):
    assert safe_name(raw) == expected
