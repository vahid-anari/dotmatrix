"""Time zones: the display wants a POSIX TZ string ("EST5EDT,M3.2.0,M11.1.0"),
places come with an IANA name ("America/Toronto"). The IANA database (the
`tzdata` package) ends each zone's file with that zone's POSIX rule, so the
rule is read from there: any zone in the world, with its daylight saving."""
from importlib import resources


def posix_tz(iana: str) -> str | None:
    """The POSIX rule for an IANA zone name, or None if it isn't known."""
    if not iana or ".." in iana or iana.startswith("/"):
        return None
    try:
        data = resources.files("tzdata.zoneinfo").joinpath(*iana.split("/")).read_bytes()
    except (ModuleNotFoundError, FileNotFoundError, IsADirectoryError, NotADirectoryError, OSError):
        return None
    # TZif version 2+: the file ends with "\n<POSIX rule>\n".
    if not data.startswith(b"TZif") or not data.endswith(b"\n"):
        return None
    rule = data[:-1].rsplit(b"\n", 1)[-1].decode("ascii", "replace")
    return rule if rule and len(rule) < 64 else None
