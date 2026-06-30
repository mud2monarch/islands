import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class Episode:
    podcast: Podcast
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
class EpisodeForRss:
    guid: str
    title: str
    description: str
    pub_date: str
    output_bucket_key: str
    duration: str
    file_size_bytes: int


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


# An EpisodeFilter returns True if you WANT to keep it
EpisodeFilter = Callable[[ET.Element], bool]


class MediaKind(StrEnum):
    AUDIO = "audio/mpeg"
    JPEG = "image/jpeg"


class TranscriptKind(StrEnum):
    VTT = "text/vtt"
    SRT = "application/srt"
    TEXT = "text/plain"


class FilterMode(StrEnum):
    ALL = "all"
    ANY = "any"


class FilterField(StrEnum):
    TITLE = "title"
    DESCRIPTION = "description"


class FilterOperator(StrEnum):
    CONTAINS_ANY = "contains_any"
    CONTAINS_NONE = "contains_none"
    CONTAINS_ALL = "contains_all"


@dataclass(frozen=True)
class PodcastReference:
    config: PodcastConfig
    path: Path


@dataclass(frozen=True)
class PodcastConfig:
    rss_url: str
    start_date: date | None
    filter: FilterConfig | None


@dataclass(frozen=True)
class FilterConfig:
    mode: FilterMode
    rules: tuple[FilterRule, ...]


@dataclass(frozen=True)
class FilterRule:
    field: FilterField
    operator: FilterOperator
    values: tuple[str, ...]
