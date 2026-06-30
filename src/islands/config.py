import tomllib
from datetime import date
from pathlib import Path

from islands.models import (
    FilterConfig,
    FilterField,
    FilterMode,
    FilterOperator,
    FilterRule,
    PodcastConfig,
)


def load_podcast_config(path: Path) -> PodcastConfig:
    with path.open("rb") as file:
        data = tomllib.load(file)

    start_date = data.get("start_date")
    if start_date is not None and not isinstance(start_date, date):
        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        else:
            raise ValueError(
                f"{path}: start_date must be a date or ISO format string, "
                f"got {start_date!r}"
            )

    filter_config = None
    filter_data = data.get("filter")

    if filter_data is not None:
        rules_data = filter_data["rules"]
        if not rules_data:
            raise ValueError(
                f"{path}: filter must contain at least one [[filter.rules]] table"
            )

        rules: list[FilterRule] = []

        for index, rule in enumerate(rules_data, start=1):
            values = rule["values"]
            if not values:
                raise ValueError(
                    f"{path}: filter rule {index} must contain at least one value"
                )

            rules.append(
                FilterRule(
                    field=FilterField(rule["field"]),
                    operator=FilterOperator(rule["operator"]),
                    values=tuple(values),
                )
            )

        filter_config = FilterConfig(
            mode=FilterMode(filter_data.get("mode", "all")),
            rules=tuple(rules),
        )

    rss_url = data["rss_url"]

    return PodcastConfig(
        rss_url=rss_url,
        start_date=start_date,
        filter=filter_config,
    )
