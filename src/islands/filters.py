import xml.etree.ElementTree as ET


def surveillance_filter(item: ET.Element) -> bool:
    """Custom function to filter out certain sub-shows from the Bloomberg Surveillance feed based on title. For use in rss.get_n_new_episodes().

    Complies with the models.EpisodeFilter contract. Returns True for episodes we want to keep.
    """

    title = item.findtext("title", "")

    excluded_surveillance_titles = {
        "Bloomberg Surveillance TV",
        "Single Best Idea",
        "Tom Keene",
        "The Money Show",
        "Bloomberg Money",
    }

    if any(item in title for item in excluded_surveillance_titles):
        return False
    else:
        return True
