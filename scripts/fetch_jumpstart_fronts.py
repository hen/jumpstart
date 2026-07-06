#!/usr/bin/env python3

import argparse
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.scryfall.com/cards/search"
COLOR_ORDER = ("W", "U", "B", "R", "G")
COLOR_NAMES = {
    "W": "White",
    "U": "Blue",
    "B": "Black",
    "R": "Red",
    "G": "Green",
}


def build_search_url(set_code: str) -> str:
    return f"{API_ROOT}?{urlencode({'q': f'e:{set_code}', 'unique': 'prints', 'include_extras': 'true', 'order': 'set'})}"


def fetch_json(url: str) -> dict:
    request = Request(
        url,
        headers={
            "User-Agent": "jumpstart-randomizer-prototype/1.0",
            "Accept": "application/json",
        },
    )
    with urlopen(request) as response:
        return json.load(response)


def fetch_cards(set_code: str) -> list[dict]:
    url = build_search_url(set_code)
    cards: list[dict] = []

    while url:
        payload = fetch_json(url)
        cards.extend(payload.get("data", []))
        url = payload.get("next_page") if payload.get("has_more") else None

    return cards


@dataclass(frozen=True)
class OwnedEntry:
    raw_value: str
    normalized_name: str | None
    collector_number: str | None


def parse_owned_entry(line: str) -> OwnedEntry:
    value = line.strip()
    match = re.match(r"^(.*?)\s*#\s*([0-9]+[a-zA-Z]*)$", value)
    if match:
        name_part = match.group(1).strip()
        return OwnedEntry(
            raw_value=value,
            normalized_name=normalize_name(name_part) if name_part else None,
            collector_number=match.group(2),
        )

    return OwnedEntry(
        raw_value=value,
        normalized_name=normalize_name(value),
        collector_number=None,
    )


def load_owned_entries(project_root: Path, set_code: str) -> list[OwnedEntry] | None:
    owned_path = project_root / f"{set_code}-owned.txt"
    if not owned_path.exists():
        return None

    return [
        parse_owned_entry(line)
        for line in owned_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_name(value: str) -> str:
    return value.strip().casefold()


def validate_owned_entries(cards: list[dict], owned_entries: list[OwnedEntry] | None, set_code: str) -> None:
    if owned_entries is None:
        return

    cards_by_number = {card["collector_number"]: card for card in cards}
    available_names = {normalize_name(card["name"]) for card in cards}
    invalid_entries: list[str] = []

    for entry in owned_entries:
        if entry.collector_number is not None:
            card = cards_by_number.get(entry.collector_number)
            if card is None:
                invalid_entries.append(f"{entry.raw_value} (unknown collector number)")
                continue

            if entry.normalized_name is not None and normalize_name(card["name"]) != entry.normalized_name:
                invalid_entries.append(
                    f"{entry.raw_value} (collector #{entry.collector_number} is {card['name']})"
                )
            continue

        if entry.normalized_name not in available_names:
            invalid_entries.append(f"{entry.raw_value} (unknown pack name)")

    if invalid_entries:
        raise ValueError(f"Invalid owned pack entries for {set_code}: {', '.join(invalid_entries)}")


def owned_card_ids(cards: list[dict], owned_entries: list[OwnedEntry] | None) -> set[str]:
    if owned_entries is None:
        return {card["id"] for card in cards}

    cards_by_number = {card["collector_number"]: card for card in cards}
    cards_by_name: dict[str, list[dict]] = {}
    for card in cards:
        cards_by_name.setdefault(normalize_name(card["name"]), []).append(card)

    owned_ids: set[str] = set()
    for entry in owned_entries:
        if entry.collector_number is not None:
            owned_ids.add(cards_by_number[entry.collector_number]["id"])
            continue

        for card in cards_by_name.get(entry.normalized_name or "", []):
            owned_ids.add(card["id"])

    return owned_ids


def image_url_for(card_id: str) -> str:
    return f"https://cards.scryfall.io/normal/front/{card_id[0]}/{card_id[1]}/{card_id}.jpg"


def unique_in_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def derive_color_codes(card: dict) -> list[str]:
    oracle_text = (card.get("oracle_text") or "").upper()

    mana_symbols = re.findall(r"\{([WUBRG])\}", oracle_text)
    if mana_symbols:
        return unique_in_order(mana_symbols)

    fallback_letters = re.findall(r"\b([WUBRG]{1,5})\b", oracle_text)
    if fallback_letters:
        letters = [letter for chunk in fallback_letters for letter in chunk]
        ordered = [color for color in COLOR_ORDER if color in letters]
        return unique_in_order(ordered)

    return []


def collector_sort_key(value: str) -> tuple[int, str]:
    match = re.match(r"(\d+)(.*)", value)
    if not match:
        return (10**9, value)
    return (int(match.group(1)), match.group(2))


def transform_card(card: dict, owned_ids: set[str]) -> dict:
    color_codes = derive_color_codes(card)
    is_multicolor = len(color_codes) > 1
    color_label = " / ".join(COLOR_NAMES[code] for code in color_codes) if color_codes else "Colorless"
    is_owned = card["id"] in owned_ids

    return {
        "id": card["id"],
        "collectorNumber": card["collector_number"],
        "name": card["name"],
        "colorCodes": color_codes,
        "colorLabel": color_label,
        "isMulticolor": is_multicolor,
        "isOwned": is_owned,
        "excludedFromRandomizer": not is_owned,
        "imageUrl": image_url_for(card["id"]),
        "scryfallUri": card["scryfall_uri"],
    }


def build_payload(set_code: str, cards: list[dict], owned_entries: list[OwnedEntry] | None) -> dict:
    sorted_cards = sorted(cards, key=lambda card: collector_sort_key(card["collector_number"]))
    set_name = sorted_cards[0]["set_name"] if sorted_cards else set_code.upper()
    owned_ids = owned_card_ids(sorted_cards, owned_entries)
    packs = [transform_card(card, owned_ids) for card in sorted_cards]
    owned_pack_count = sum(1 for pack in packs if pack["isOwned"])

    return {
        "setCode": set_code,
        "setName": set_name,
        "sourceUrl": f"https://scryfall.com/search?q=e%3A{set_code}&include_extras=true",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "packCount": len(sorted_cards),
        "ownedPackCount": owned_pack_count,
        "hasOwnershipFile": owned_entries is not None,
        "packs": packs,
    }


def javascript_payload(payload: dict) -> str:
    set_code = payload["setCode"]
    data = json.dumps(payload, indent=2)
    return f"window.JUMPSTART_SETS = window.JUMPSTART_SETS || {{}};\nwindow.JUMPSTART_SETS[{json.dumps(set_code)}] = {data};\n"


def write_payload_files(project_root: Path, set_code: str, output_path: Path | None = None) -> dict:
    destination = output_path or project_root / "docs" / "data" / f"{set_code}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)

    cards = fetch_cards(set_code)
    owned_entries = load_owned_entries(project_root, set_code)
    validate_owned_entries(cards, owned_entries, set_code)
    payload = build_payload(set_code, cards, owned_entries)

    destination.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    js_output_path = destination.with_suffix(".js")
    js_output_path.write_text(javascript_payload(payload), encoding="utf-8")

    if owned_entries is None:
        ownership_message = f"all {payload['packCount']} packs enabled"
    else:
        ownership_message = f"{payload['ownedPackCount']} of {payload['packCount']} packs enabled"
    print(f"Wrote {ownership_message} to {destination}")
    print(f"Wrote JavaScript payload to {js_output_path}")

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Jumpstart front-card names, colors, and image URLs from Scryfall."
    )
    parser.add_argument("set_code", help="Scryfall set code, such as fmsc")
    parser.add_argument(
        "--output",
        help="Output JSON path. Defaults to docs/data/<set_code>.json",
    )
    args = parser.parse_args()

    set_code = args.set_code.lower()
    project_root = Path(__file__).resolve().parents[1]
    output_path = Path(args.output) if args.output else None
    write_payload_files(project_root, set_code, output_path)


if __name__ == "__main__":
    main()
