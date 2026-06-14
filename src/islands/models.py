import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np


@dataclass(frozen=True)
class Episode:
    guid: str
    title: str
    description: str
    pub_date: str
    mp3_url: str
    transcript_url: str


@dataclass
class Podcast:
    title: str
    description: str
    pfp_url: str
    rss_url: str
    text_references: list[str]
    audio_references: list[np.ndarray]


@dataclass
class ReadyForProcessing:
    episodes: list[Episode]
    podcast: Podcast

    def __post_init__(self) -> None:
        if not self.episodes:
            raise ValueError("episodes must be populated")

        if not self.podcast.audio_references:
            raise ValueError("podcast.audio_reference must be populated")

        if not self.podcast.text_references:
            raise ValueError("podcast.text_references must be populated")


EpisodeFilter = Callable[[ET.Element], bool]


class MediaKind(Enum):
    AUDIO = "audio/mpeg"
    JPEG = "image/jpeg"


class TranscriptKind(Enum):
    VTT = "text/vtt"
    SRT = "application/srt"
    TEXT = "text/plain"


class SupportedPodcasts(Enum):
    SURVEILLANCE = "surveillance"


class SurveillanceKind(Enum):
    FERRO = "ferro"
    TK_IDEA = "tk_idea"
    MONEY = "money"
    TK_CANDIDATE = "tk"
