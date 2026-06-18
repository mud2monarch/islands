import logging
import string
from pathlib import Path

import librosa

from .analysis import find_similar_mel_ts
from .audio import (
    MEL_FPS,
    MEL_HOP_LENGTH,
    SAMPLE_RATE,
    clip_audio,
    merge_clips,
)
from .models import Episode, Podcast
from .network import download_audio, fetch_text
from .text import chunk_transcript, fuzzy_contains_phrase, int_to_ts, normalize_title

logger = logging.getLogger(__name__)


def strip_episode(episode: Episode, podcast: Podcast) -> Path | None:
    """Function to strip ads from an Episode

    Args:
        episode: Episode you want to strip
        references: set of ClipReferences against which to match
    Returns:
        Filepath to the output file
    """

    MEL_MATCH_CONFIDENCE = 0.6
    TEST_CLIP_SECONDS = 240

    audio_path = download_audio(
        episode.mp3_url, Path(f"output/dirty/episodes/{episode.title}.mp3")
    )
    cumulative_ads: int = 0
    ad_spans: list[int] = []
    end_ts: int = 0
    candidates: list[int] = []

    chunks = chunk_transcript(fetch_text(episode.transcript_url))
    for i, chunk in enumerate(chunks):
        ts, text = chunk

        if any(
            fuzzy_contains_phrase(text, phrase) for phrase in podcast.text_references
        ):
            candidates.append(ts)

        if i == len(chunks) - 1:
            end_ts = ts

    logger.info(f"found {len(candidates)} candidates")
    if len(candidates) == 0:
        return None

    return_timestamps: list[int] = []

    for i, ts in enumerate(candidates):
        previous_cumulative_ads = cumulative_ads
        clip_start = max(ts + cumulative_ads - 5, 0)

        logger.info(
            f"processing candidate {i}, starting clip at {int_to_ts(clip_start)}. accumulated ad time is {int_to_ts(cumulative_ads)}"
        )

        clip_audio(
            clip_start,
            TEST_CLIP_SECONDS,
            str(audio_path),
            f"output/dirty/comparison/clip_{i}.wav",
        )

        clip_y, _ = librosa.load(f"output/dirty/comparison/clip_{i}.wav")
        clip_mel = librosa.feature.melspectrogram(
            y=clip_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
        )

        return_secs: int
        confidence: float

        matches = [
            find_similar_mel_ts(clip_mel, ref_mel, MEL_FPS)
            for ref_mel in podcast.audio_references
        ]
        return_secs, confidence = max(matches, key=lambda match: match[1])

        real_ts = clip_start + return_secs

        if confidence > MEL_MATCH_CONFIDENCE:
            # Register the new return point
            return_timestamps.append(real_ts)
            # Update the total drift in timestamps
            cumulative_ads = real_ts - ts
            # Register the length of the ad break
            ad_spans.append(cumulative_ads - previous_cumulative_ads)
        else:
            logger.warning(
                f"confidence ({confidence}) below threshold, skipping. Window was at {int_to_ts(real_ts)}"
            )

    end_ts += cumulative_ads

    for i, stamp in enumerate(return_timestamps):
        if i == len(return_timestamps) - 1:
            logger.info(
                f"Clipping {end_ts - stamp} seconds starting at {int_to_ts(stamp)}."
            )
            clip_audio(
                stamp,
                end_ts - stamp,
                str(audio_path),
                f"output/dirty/cuts/cut_{i}.wav",
            )
        else:
            logger.info(
                f"Clipping {return_timestamps[i + 1] - return_timestamps[i] - ad_spans[i + 1]} seconds starting at {int_to_ts(stamp)}."
            )
            clip_audio(
                stamp,
                return_timestamps[i + 1] - return_timestamps[i] - ad_spans[i + 1],
                str(audio_path),
                f"output/dirty/cuts/cut_{i}.wav",
            )

    logger.info("Merging clips...")

    destination = f"output/clean/{normalize_title(podcast.title)}/{normalize_title(episode.title)}_clean.mp3"

    merge_clips(
        "output/dirty/cuts",
        len(return_timestamps),
        destination,
    )
    logger.info("Done merging.")

    return Path(destination)
