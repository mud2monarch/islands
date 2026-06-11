import logging
import subprocess
import xml.etree.ElementTree as ET
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


class Episode:
    def __init__(self, title, description, pub_date, mp3_link, transcript):
        self.title = title
        self.description = description
        self.pub_date = pub_date
        self.mp3 = mp3_link
        self.transcript = transcript


class SurveillanceKind(Enum):
    FERRO = "ferro"
    TK = "tk"
    TK_IDEA = "tk_idea"
    MONEY = "money"


class MediaKind(Enum):
    AUDIO = "audio/mpeg"
    JPEG = "image/jpeg"


class TranscriptKind(Enum):
    VTT = "text/vtt"
    SRT = "application/srt"
    TEXT = "text/plain"


def parse_title(title: str) -> SurveillanceKind:
    if "Bloomberg Surveillance TV" in title:
        return SurveillanceKind.FERRO

    if "Single Best Idea" in title or "Tom Keene" in title:
        return SurveillanceKind.TK_IDEA

    if "Bloomberg Money" in title:
        return SurveillanceKind.MONEY

    return SurveillanceKind.TK


def filter_n_episodes(
    feed: str = "surveillance.rss",
    num_episodes: int = 10,
    episode_kind: SurveillanceKind = SurveillanceKind.TK,
) -> list[Episode]:
    desired_episodes: list[Episode] = []

    tree = ET.parse(feed)
    root = tree.getroot()

    for item in root.findall("./channel/item")[:num_episodes]:
        title = item.findtext("title", "")

        if parse_title(title) == episode_kind:
            description = item.findtext("description")
            pub_date = item.findtext("pubDate")
            mp3_link = None
            transcript_url = None

            for media in item.findall("media:content", NAMESPACES):
                if media.attrib.get("type") == MediaKind.AUDIO.value:
                    mp3_link = media.attrib.get("url")

            for transcript in item.findall("podcast:transcript", NAMESPACES):
                if transcript.attrib.get("type") == TranscriptKind.TEXT.value:
                    transcript_url = transcript.attrib.get("url")

            desired_episodes.append(
                Episode(title, description, pub_date, mp3_link, transcript_url)
            )

    return desired_episodes


def ts_to_int(text_ts: str) -> int:
    try:
        h, m, s = text_ts.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {text_ts!r}") from exc


def int_to_ts(seconds: int) -> str:
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)

    return f"{h:02d}:{m:02d}:{s:02d}"


def clip_audio(
    start_secs: int,
    duration_secs: int,
    path: str,
    output: str,
):
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            int_to_ts(start_secs),
            "-t",
            int_to_ts(duration_secs),
            "-i",
            path,
            "-ac",
            "1",
            "-ar",
            "22050",
            "-acodec",
            "pcm_s16le",
            output,
        ],
        check=True,
    )


def merge_clips(dir: str, num_cuts: int, output: str):
    cuts_dir = Path(dir)
    concat_file = cuts_dir / "cuts.txt"

    concat_file.write_text("".join(f"file 'cut_{i}.wav'\n" for i in range(num_cuts)))

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-ac",
            "1",
            "-ar",
            "22050",
            "-codec:a",
            "libmp3lame",
            "-b:a",
            "64k",
            output,
        ],
        check=True,
    )


"""
    Given a transcript as a block of text, split it into tuples of (timestamp, text).

    This assumes that the transcript is well-composed.

    params:
        transcript: str = The text you want to split
    returns:
        A tuple of (int, str) representing (number of seconds in the transcript, transcript text)
"""


def chunk_transcript(
    transcript: str,
) -> list[tuple[int, str]]:
    chunks = []
    blocks = transcript.strip().lower().split("\n\n")

    for block in blocks:
        ts, text = block.strip().split("\n")
        chunks.append((ts_to_int(ts), text))

    return chunks
