import datetime

DATETIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f%z",
    "%Y-%m-%dT%H:%M:%S.%f",
    # For backwards compatibility to read timestamps created with a previous version.
    "%Y-%m-%dT%H:%M:%S.Z",
]


def datetime_to_iso8601(dt: datetime.datetime) -> str:
    return dt.strftime(DATETIME_FORMATS[0])


def iso8601_to_datetime(value: str) -> datetime.datetime:
    err: "ValueError | None" = None
    for fmt in DATETIME_FORMATS:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError as exc:
            err = exc
    assert err is not None
    raise err
