
"""Download and validate monthly CPI-U, with a safe cached-data fallback.

Source: BLS CPI-U NSA, via FRED series CPIAUCNS.
A network failure may reuse an existing, validated CPI file.
Invalid downloaded data are never silently accepted.
"""

import csv
import datetime as dt
import io
import math
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "inflation" / "cpi_u.csv"

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCNS"

MAX_DOWNLOAD_BYTES = 5_000_000
MAX_CACHE_AGE_MONTHS = 4
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 25


def month_age(period):
    """Age of a monthly observation relative to current UTC month."""
    year, month = map(int, period.split("-"))
    today = dt.datetime.now(dt.timezone.utc).date()
    return (today.year - year) * 12 + today.month - month


def validate_observations(observations):
    """Check completeness, chronology, numerical validity and recency."""
    if len(observations) < 250:
        raise ValueError("CPI history unexpectedly sparse")

    months = list(observations)

    if months != sorted(months):
        raise ValueError("CPI months are not sorted")

    if len(months) != len(set(months)):
        raise ValueError("Duplicate CPI months")

    for period, value in observations.items():
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period):
            raise ValueError(f"Invalid CPI month: {period}")

        if not (math.isfinite(value) and 0 < value < 10000):
            raise ValueError(f"Invalid CPI value: {period}")

    latest = months[-1]
    age = month_age(latest)

    if age < 0:
        raise ValueError("CPI observations extend into the future")

    if age > MAX_CACHE_AGE_MONTHS:
        raise ValueError(
            f"CPI data too stale: latest {latest}, "
            f"{age} calendar months old"
        )

    return len(months), latest


def parse_download(text):
    """Parse FRED CSV into our standardized CPI format."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))

    if not reader.fieldnames:
        raise ValueError("Empty CPI download")

    date_key = None

    for candidate in ("observation_date", "DATE"):
        if candidate in reader.fieldnames:
            date_key = candidate
            break

    if date_key is None or "CPIAUCNS" not in reader.fieldnames:
        raise ValueError("Unexpected FRED CPI CSV schema")

    observations = {}

    for row in reader:
        date = dt.date.fromisoformat(row[date_key])

        if date.day != 1:
            raise ValueError("Invalid CPI observation date")

        value = row["CPIAUCNS"].strip()

        if value in ("", "."):
            continue

        period = date.strftime("%Y-%m")

        if period in observations:
            raise ValueError(f"Duplicate CPI month: {period}")

        observations[period] = float(value)

    count, latest = validate_observations(observations)

    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["period", "cpi"])

    for period, value in observations.items():
        writer.writerow([period, format(value, ".3f")])

    return buffer.getvalue().encode("utf-8"), count, latest


def validate_existing_cache():
    """Validate the existing normalized CPI file."""
    if not OUTPUT.is_file():
        raise ValueError("No existing CPI cache available")

    observations = {}

    with OUTPUT.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        if reader.fieldnames != ["period", "cpi"]:
            raise ValueError("Unexpected cached CPI CSV schema")

        for row in reader:
            period = row["period"]
            value = float(row["cpi"])

            if period in observations:
                raise ValueError(
                    f"Duplicate cached CPI month: {period}"
                )

            observations[period] = value

    return validate_observations(observations)


def download_cpi():
    """Download with bounded retries on network failures."""
    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "TexasSalesTaxMonitor/1.0 public research"
        },
    )

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                req, timeout=TIMEOUT_SECONDS
            ) as response:
                body = response.read(MAX_DOWNLOAD_BYTES + 1)

            if len(body) > MAX_DOWNLOAD_BYTES:
                raise ValueError("CPI download exceeds maximum size")

            return body

        except (TimeoutError, OSError) as exc:
            print(
                f"CPI download attempt {attempt}/"
                f"{MAX_ATTEMPTS} failed: {exc}",
                file=sys.stderr,
                flush=True,
            )

            if attempt == MAX_ATTEMPTS:
                raise

            time.sleep(3 * attempt)


def main():
    try:
        body = download_cpi()

    except (TimeoutError, OSError) as exc:
        print(
            f"WARNING: CPI download unavailable: {exc}",
            file=sys.stderr,
        )

        # Never assume a cached file is valid.
        count, latest = validate_existing_cache()

        print(
            f"WARNING: Using previously validated CPI cache: "
            f"{count} months, latest {latest}. "
            f"No CPI values were invented.",
            file=sys.stderr,
        )
        return

    # A malformed response is a data-integrity error,
    # not a reason to silently reuse the cache.
    result, count, latest = parse_download(
        body.decode("utf-8-sig")
    )

    if OUTPUT.exists():
        old_count, old_latest = validate_existing_cache()

        if latest < old_latest:
            raise ValueError(
                f"Downloaded CPI ends {latest}, "
                f"older than cached {old_latest}"
            )

        if count < old_count:
            raise ValueError(
                "Downloaded CPI has fewer observations "
                "than the existing validated cache"
            )

        if OUTPUT.read_bytes() == result:
            print(
                f"CPI unchanged: {count} months, latest {latest}"
            )
            return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically so an interrupted update cannot
    # leave a partially written CPI CSV.
    temp = None

    try:
        with tempfile.NamedTemporaryFile(
            dir=OUTPUT.parent,
            delete=False,
        ) as file:
            file.write(result)
            temp = Path(file.name)

        os.replace(temp, OUTPUT)

    finally:
        if temp is not None and temp.exists():
            temp.unlink()

    print(
        f"CPI updated: {count} months; "
        f"latest {latest}; {OUTPUT}"
    )


if __name__ == "__main__":
    main()
