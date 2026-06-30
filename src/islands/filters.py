import logging
import xml.etree.ElementTree as ET

from islands.models import (
    EpisodeFilter,
    FilterConfig,
    FilterMode,
    FilterOperator,
    FilterRule,
)

logger = logging.getLogger(__name__)


def generate_filter(config: FilterConfig | None) -> EpisodeFilter | None:
    if config is None:
        return None

    def episode_matches(item: ET.Element) -> bool:
        results = (_fits_rule(item, rule) for rule in config.rules)

        match config.mode:
            case FilterMode.ALL:
                return all(results)
            case FilterMode.ANY:
                return any(results)
            case _:
                raise ValueError(f"Unknown filter mode: {config.mode}")

    return episode_matches


def _fits_rule(item: ET.Element, rule: FilterRule) -> bool:
    text = item.findtext(rule.field, "")
    if text.strip() == "":
        logger.warning(
            "Rule was invalid or couldn't be matched to contents of podcast item. Therefore the rule hasn't been matched and we return False. Please check."
        )
        return False

    matches = (value in text for value in rule.values)

    match rule.operator:
        case FilterOperator.CONTAINS_ALL:
            return all(matches)
        case FilterOperator.CONTAINS_ANY:
            return any(matches)
        case FilterOperator.CONTAINS_NONE:
            return not any(matches)
        case _:
            raise ValueError(f"Unknown filter operator: {rule.operator}")
