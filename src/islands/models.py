import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

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
    clip_references: list[ClipReference]


@dataclass
class ReadyForProcessing:
    episodes: list[Episode]
    podcast: Podcast

    def __post_init__(self) -> None:
        if not self.episodes:
            raise ValueError("episodes must be populated")

        if not self.podcast.clip_references:
            raise ValueError("podcast.clip_references must be populated")


EpisodeFilter = Callable[[ET.Element], bool]


@dataclass
class ClipReference:
    transcript_text: str
    audio_mel: np.ndarray


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
