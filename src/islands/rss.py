import logging
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from islands.database import get_all_episode_guids, get_rss_relevant_episode_details
from islands.network import get_public_object_url
from islands.text import normalize_title

from .models import (
    Episode,
    EpisodeFilter,
    MediaKind,
    Podcast,
    SurveillanceKind,
    TranscriptKind,
)

logger = logging.getLogger(__name__)

NAMESPACES = {
    "media": "http://search.yahoo.com/mrss/",
    "podcast": "https://podcastindex.org/namespace/1.0",
}


def get_podcast_info(rss_url: str) -> Podcast:
    """Parse Podcast metadata from an RSS feed

    args:
        rss_url: the RSS feed identifying a podcast
    returns:
        A built Podcast object less reference clips
    """
    with urllib.request.urlopen(rss_url) as feed:
        tree = ET.parse(feed)
    root = tree.getroot()

    title = root.findtext("./channel/title", "")
    description = root.findtext("./channel/description", "")
    pfp_url = root.findtext("./channel/image/url", "")

    return Podcast(
        title,
        description,
        pfp_url,
        rss_url,
        text_references=[],
        audio_references=[],
    )


def get_n_new_episodes(
    podcast: Podcast,
    conn: sqlite3.Connection,
    episode_filter: EpisodeFilter | None = None,
    num_episodes: int = 7,
) -> list[Episode]:
    """Get n new Episodes from a podcast

    Args:
        podcast: the Podcast you want to parse
        conn: connection to the database
        episode_filter: any predicate you'd like to meet
        num_episodes: number of matching episodes to find. will not return episodes that have already been processed
    """
    desired_episodes: list[Episode] = []
    completed_episodes = get_all_episode_guids(conn, podcast)

    with urllib.request.urlopen(podcast.rss_url) as feed:
        tree = ET.parse(feed)
    root = tree.getroot()

    for item in root.findall("./channel/item"):
        if len(desired_episodes) >= num_episodes:
            break

        if episode_filter is not None and not episode_filter(item):
            continue

        title = item.findtext("title", "")
        description = item.findtext("description", "")
        pub_date = item.findtext("pubDate", "")
        mp3_link = None
        transcript_url = None

        guid = item.findtext("guid", "").strip()
        if not guid:
            raise ValueError("guid is required")

        if guid in completed_episodes:
            logger.debug(
                f"Skipping {title} because it's already been processed, guid {guid}."
            )
            continue

        for media in item.findall("media:content", NAMESPACES):
            if media.attrib.get("type") == MediaKind.AUDIO.value:
                mp3_link = media.attrib.get("url")

        for transcript in item.findall("podcast:transcript", NAMESPACES):
            if transcript.attrib.get("type") == TranscriptKind.TEXT.value:
                transcript_url = transcript.attrib.get("url")

        if mp3_link is not None and transcript_url is not None:
            desired_episodes.append(
                Episode(
                    podcast,
                    guid,
                    title,
                    description,
                    pub_date,
                    mp3_link,
                    transcript_url,
                )
            )

    return desired_episodes


def make_surveillance_kind_filter(kind: SurveillanceKind) -> EpisodeFilter:
    """Meta-function to filter elements based on SurveillanceKind

    args:
        kind: the SurveillanceKind for which you want to filter
    returns:
        an EpisodeFilter function
    """

    def episode_matches_kind(item: ET.Element) -> bool:
        title = item.findtext("title", "")
        return guess_surveillance_kind(title) == kind

    return episode_matches_kind


def guess_surveillance_kind(title: str) -> SurveillanceKind:
    """Guess at the kind of episode based on parts of the episode title.

    Args:
        title: Title of the episode

    Returns:
        Match to a SurveillanceKind.

    TK_CANDIDATE is a *guess* because there is no brand identifier in the title of Tom Keene's radio show, while the other variants of Surveillance do have identifiers.
    """
    if "Bloomberg Surveillance TV" in title:
        return SurveillanceKind.FERRO

    if "Single Best Idea" in title or "Tom Keene" in title:
        return SurveillanceKind.TK_IDEA

    if "The Money Show" in title:
        return SurveillanceKind.MONEY

    return SurveillanceKind.TK_CANDIDATE


def write_rss_feed(conn: sqlite3.Connection, podcast: Podcast) -> Path:
    """Write an RSS feed with all episoes of a given Podcast.

    Args:
        conn: the database connection
        podcast: the Podcast to write an RSS feed for

    Returns:
        path to RSS feed.
    """
    ET.register_namespace("itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = podcast.title
    ET.SubElement(channel, "description").text = podcast.description
    ET.SubElement(channel, "link").text = podcast.rss_url
    ET.SubElement(
        channel,
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}author",
    ).text = podcast.title
    ET.SubElement(
        channel,
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}summary",
    ).text = podcast.description
    ET.SubElement(
        channel,
        "{http://www.itunes.com/dtds/podcast-1.0.dtd}explicit",
    ).text = "false"

    if podcast.pfp_url:
        ET.SubElement(
            channel,
            "{http://www.itunes.com/dtds/podcast-1.0.dtd}image",
            {"href": podcast.pfp_url},
        )

    episodes = get_rss_relevant_episode_details(conn, podcast)
    for episode in episodes:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "guid").text = episode.guid
        ET.SubElement(item, "title").text = episode.title
        ET.SubElement(item, "description").text = episode.description
        ET.SubElement(item, "pubDate").text = episode.pub_date

        ET.SubElement(
            item,
            "enclosure",
            {
                "url": get_public_object_url(episode.output_bucket_key),
                "type": "audio/mpeg",
                "length": f"{episode.file_size_bytes}",
            },
        )
        ET.SubElement(
            item,
            "{http://www.itunes.com/dtds/podcast-1.0.dtd}duration",
        ).text = episode.duration

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")

    output_path = Path(f"output/clean/{normalize_title(podcast.title)}.xml")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tree.write(output_path, encoding="utf-8", xml_declaration=True)

    return output_path
