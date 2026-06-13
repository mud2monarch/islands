from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class Episode:
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
    references: list[ClipReference]


@dataclass
class ClipReference:
    transcript_text: str
    audio_path: str | Path


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
