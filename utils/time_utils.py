import logging


logger = logging.getLogger("Utils.Time")


def duration_to_str(seconds: int, long_format: bool = False) -> str:
    """
    Converts a time duration in seconds to a human-readable string.

    :param seconds: Duration in seconds.
    :type seconds: int
    :return: Human-readable duration string.
    :rtype: str
    """
    logger.debug("Converting duration: %d (long_format=%s)",
                 seconds, long_format)
    units_separator = ' ' if long_format else ''
    if not long_format:
        time_intervals = (
            ('w', 604800),
            ('d', 86400),
            ('h', 3600),
            ('m', 60),
            #            ('s', 1),
        )
    else:
        time_intervals = (
            ('weeks', 604800),
            ('days', 86400),
            ('hours', 3600),
            ('minutes', 60),
            ('seconds', 1),
        )
    result_builder = []
    for desc, amount in time_intervals:
        value = seconds // amount
        if value:
            seconds -= value * amount
            if value == 1:
                desc = desc.rstrip('s')
            result_builder.append(f"{int(value)}{units_separator}{desc}")
    return ', '.join(result_builder) if result_builder else '0'
