import logging
import xml.etree.ElementTree as ET
from enum import Enum

from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(
            rich_tracebacks=True,
            log_time_format="[%m/%d/%y %H:%M:%S.%f]",
        )
    ],
)


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

            for media in item.findall("media:content", namespaces):
                if media.attrib.get("type") == MediaKind.AUDIO.value:
                    mp3_link = media.attrib.get("url")

            for transcript in item.findall("podcast:transcript", namespaces):
                if transcript.attrib.get("type") == TranscriptKind.TEXT.value:
                    transcript_url = transcript.attrib.get("url")

            desired_episodes.append(
                Episode(title, description, pub_date, mp3_link, transcript_url)
            )

    return desired_episodes


namespaces = {
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}

episodes = filter_n_episodes()

for episode in episodes:
    logging.info(episode.transcript)

"""
waveform
-> STFT
-> magnitude spectrogram
-> mel filterbank
-> log scaling
-> log-mel spectrogram
"""
