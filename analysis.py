import numpy as np


def to_mel_ts(seconds: int, fps: float) -> float:
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    return seconds * fps


def from_mel_ts(mel_ts: float, fps: float) -> int:
    if mel_ts < 0:
        raise ValueError("mel_ts must be non-negative")

    return int(mel_ts / fps)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.sum(a * b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9)


"""
Returns the timestamp (in whole seconds) of window start that most closely matches the reference.

params:
    target: np.ndarray = the melspectogram to search
    reference: np.ndarray = the melspectogram against which we're matching

returns:
    int: the timestamp, from the start of the target array, of the window that most closely matches the reference
    float: the cosine similarity of the window. A measure of confidence (higher is better)
"""


def find_similar_mel_ts(
    target: np.ndarray, reference: np.ndarray, fps: float
) -> tuple[int, float]:
    best_score = float("-inf")
    best_mel_ts = float("-inf")

    for ts in range(target.shape[1] - reference.shape[1] + 1):
        window = target[:, ts : ts + reference.shape[1]]
        score = cosine_similarity(window, reference)

        if score > best_score:
            best_score = score
            best_mel_ts = ts

    return from_mel_ts(best_mel_ts, fps), best_score
