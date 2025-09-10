import re
from datetime import timedelta

URL_REGEX = re.compile(r"https?://(?:www\.)?.+")


def format_duration(milliseconds: int | None) -> str:
    """Formats milliseconds into a HH:MM:SS or MM:SS string."""
    if milliseconds is None:
        return "N/A"
    seconds = milliseconds / 1000
    td = timedelta(seconds=seconds)
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if td.days > 0 or hours > 0:
        return f"{hours:02}:{minutes:02}:{int(seconds):02}"
    else:
        return f"{minutes:02}:{int(seconds):02}"
