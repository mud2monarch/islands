import string

from rapidfuzz import fuzz


def chunk_transcript(
    transcript: str,
) -> list[tuple[int, str]]:
    """Splits transcript into a list of timestamps and text chunks. Assumes well-formatted transcripts

    Args:
        transcript: a single block of text in plaintext transcript format

    Returns:
        A list of (int, str) where int is the number of whole seconds of the timestamp and str is the text of the transcript for that chunk.
    """
    chunks = []
    blocks = transcript.strip().lower().split("\n\n")

    for block in blocks:
        ts, text = block.strip().split("\n")
        chunks.append((ts_to_int(ts), text))

    return chunks


def fuzzy_contains_phrase(
    target_text: str,
    reference_phrase: str,
    threshold: float | int = 85,
) -> bool:
    """Search a piece of text to see if it contains a reference phrase

    args:
        target_text: target text to test
        reference_phrase: phrase for which you're looking. Should be all lowercase
        threshold: value between 0 and 100, higher is more similar
    returns:
        whether target_text contains reference_phrase
    """
    words = target_text.strip().lower().split()
    phrase_len = len(reference_phrase.strip().split())

    for i in range(len(words) - phrase_len + 1):
        window = " ".join(words[i : i + phrase_len])
        if fuzz.ratio(window, reference_phrase) >= threshold:
            return True

    return False


def ts_to_int(text_ts: str) -> int:
    """Trivial conversion of a podcast timestamp, in the form of HH:MM:SS, to number of seconds.

    Args:
        text_ts: Text timestamp
    Returns:
        Number of seconds
    """
    try:
        h, m, s = text_ts.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError as exc:
        raise ValueError(f"Invalid timestamp: {text_ts!r}") from exc


def int_to_ts(seconds: int) -> str:
    """Trivial conversion of a number of seconds to a podcast timestamp, in the form of HH:MM:SS.

    Args:
        seconds: number of seconds
    Returns:
        Text timestamp in format HH:MM:SS
    """
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)

    return f"{h:02d}:{m:02d}:{s:02d}"


def normalize_title(title: str) -> str:
    no_punct = title.translate(str.maketrans("", "", string.punctuation)).lower()
    return "-".join(no_punct.split())
