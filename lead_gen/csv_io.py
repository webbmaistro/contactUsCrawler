"""CSV I/O: save row, load existing CSV."""

import csv
from pathlib import Path

from lead_gen import config
from lead_gen.places_merge import extract_domain


def save_row(csv_path: str, restaurant_name: str, website: str, emails: list, write_header: bool = False):
    """Append one row to CSV. Format: restaurant_name, website, emails_found (pipe-separated)."""
    row = [restaurant_name, website, "|".join(emails) if emails else ""]
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["restaurant_name", "website", "emails_found"])
        w.writerow(row)


def load_existing_csv(csv_path: str) -> tuple:
    """
    Load existing CSV if present. Returns (list of rows as dicts, set of domains).
    Empty if file missing or invalid.
    """
    path = Path(csv_path)
    if not path.exists():
        return [], set()
    try:
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        if not rows or "website" not in (rows[0] or {}):
            return [], set()
        existing = []
        seen = set()
        for row in rows:
            name = (row.get("restaurant_name") or "").strip()
            website = (row.get("website") or "").strip()
            emails_found = (row.get("emails_found") or "").strip()
            if not website:
                continue
            domain = extract_domain(website) or ""
            if domain and domain in seen:
                continue
            seen.add(domain)
            existing.append({"name": name, "website": website, "emails_found": emails_found})
        return existing, seen
    except Exception as e:
        config.logger.warning("Could not load existing CSV %s: %s", csv_path, e)
        return [], set()
