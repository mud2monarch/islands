import numpy as np


def to_mel_ts(seconds: int, fps: float) -> float:
    """Trivial conversion of seconds to a Mel spectrogram frame count

    Args:
        seconds: Number of whole seconds
        fps: Number of frames per second for the Mel spectrogram

    Returns:
        Number of frames
    """
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    return seconds * fps


def from_mel_ts(mel_ts: float, fps: float) -> int:
    """Trivial conversion of mel spectrogram frame count to whole seconds

    Args:
        mel_ts: Number of mel spectrogram frames
        fps: Number of frames per second for the Mel spectrogram

    Returns:
        Number of whole seconds, rounded down
    """
    if mel_ts < 0:
        raise ValueError("mel_ts must be non-negative")

    return int(mel_ts / fps)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Trivial calculation of the cosine similarity of two matrices

    Args:
        a: matrix 1
        b: matrix 2

    Returns:
        Cosine similarity, between -1 and 1. Higher is more similar.
    """
    return np.sum(a * b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9)


def find_similar_mel_ts(
    target: np.ndarray, reference: np.ndarray, fps: float
) -> tuple[int, float]:
    """Returns the timestamp (in whole seconds) of window start that most closely matches the reference.

    Args:
        target: np.ndarray = the melspectogram to search
        reference: np.ndarray = the melspectogram against which we're matching

    Returns:
        int: the timestamp, from the start of the target array, of the window that most closely matches the reference
        float: the cosine similarity of the window. A measure of confidence (higher is better)
    """
    best_score = float("-inf")
    best_mel_ts = float("-inf")

    for ts in range(target.shape[1] - reference.shape[1] + 1):
        window = target[:, ts : ts + reference.shape[1]]
        score = cosine_similarity(window, reference)

        if score > best_score:
            best_score = score
            best_mel_ts = ts

    return from_mel_ts(best_mel_ts, fps), best_score
