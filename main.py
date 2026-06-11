import logging

import librosa
from rapidfuzz import fuzz
from rich.logging import RichHandler

from analysis import find_similar_mel_ts
from readwrite import chunk_transcript, clip_audio, int_to_ts, merge_clips

SAMPLE_RATE = 22050
MEL_HOP_LENGTH = 512
MEL_FPS = SAMPLE_RATE / MEL_HOP_LENGTH

OPENING_TRANSCRIPT = "speaker 1: bloomberg audio studios, podcasts, radio news. this is the bloomberg surveillance podcast. catch us live weekdays at seven am eastern on apple car play"

RETURN_TRANSCRIPT = "speaker 1: you're listening to the bloomberg surveillance podcast. catch us live weekday afternoons from seven to ten am eastern listen on apple karplay"

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

cumulative_ads: int = 0
previous_cumulative_ads: int = cumulative_ads
ad_spans: list[int] = []
end_ts: int = 0

file = open("samples/transcript.txt", "r")
content = file.read()
chunks = chunk_transcript(content)

candidates: list[int] = []

for i, chunk in enumerate(chunks):
    ts, text = chunk
    first_26_words = " ".join(text.strip().split()[:26])

    if (
        fuzz.ratio(OPENING_TRANSCRIPT, first_26_words) > 70
        or fuzz.ratio(RETURN_TRANSCRIPT, first_26_words) > 70
    ):
        candidates.append(ts)

    if i == len(chunks) - 1:
        end_ts = ts

# print(end_ts)

logging.info(f"found {len(candidates)} candidates")

opening_jingle_y, _ = librosa.load("samples/opening_jingle.mp3")
opening_mel = librosa.feature.melspectrogram(
    y=opening_jingle_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
)

return_jingle_y, _ = librosa.load("samples/return_jingle.mp3")
return_mel = librosa.feature.melspectrogram(
    y=return_jingle_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
)

return_timestamps: list[int] = []

for i, ts in enumerate(candidates):
    previous_cumulative_ads = cumulative_ads
    clip_start = max(ts + cumulative_ads - 5, 0)

    logging.info(
        f"processing candidate {i}, starting clip at {int_to_ts(clip_start)}. accumulated ad time is {int_to_ts(cumulative_ads)}"
    )

    clip_audio(
        clip_start,  # buffer
        180,
        "samples/US_Economic_Outlook_and_Bond_Signals.mp3",
        f"output/dirty/comparison/clip_{i}.wav",
    )

    clip_y, _ = librosa.load(f"output/dirty/comparison/clip_{i}.wav")
    clip_mel = librosa.feature.melspectrogram(
        y=clip_y, sr=SAMPLE_RATE, hop_length=MEL_HOP_LENGTH
    )

    return_secs: int = 0
    confidence: float = 0.0

    # if this is the opening ad read
    if i == 0:
        return_secs, confidence = find_similar_mel_ts(clip_mel, opening_mel, MEL_FPS)
    else:
        return_secs, confidence = find_similar_mel_ts(clip_mel, return_mel, MEL_FPS)

    # logging.info(f"Found return at {return_secs}s (confidence: {confidence})")

    real_ts = clip_start + return_secs

    if confidence > 0.7:
        # Register the new return point
        return_timestamps.append(real_ts)
        # Update the total drift in timestamps
        cumulative_ads = real_ts - ts
        # Register the length of the ad break
        ad_spans.append(cumulative_ads - previous_cumulative_ads)
    else:
        logging.warning(
            f"confidence ({confidence}) below threshold, skipping. Window was at {int_to_ts(real_ts)}"
        )

end_ts += cumulative_ads

for i, stamp in enumerate(return_timestamps):
    if i == len(return_timestamps) - 1:
        clip_audio(
            stamp,
            end_ts - stamp,
            "samples/US_Economic_Outlook_and_Bond_Signals.mp3",
            f"output/dirty/cuts/cut_{i}.wav",
        )
    else:
        clip_audio(
            stamp,
            return_timestamps[i + 1] - return_timestamps[i] - ad_spans[i + 1],
            "samples/US_Economic_Outlook_and_Bond_Signals.mp3",
            f"output/dirty/cuts/cut_{i}.wav",
        )

merge_clips("output/dirty/cuts", len(return_timestamps), "output/clean/adless_pod.wav")
