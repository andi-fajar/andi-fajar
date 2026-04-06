"""
flatten_kyc_csv.py
==================
Flattens a CSV file that contains a nested JSON string in the `raw_response`
column into a fully tabular CSV.

Each JSON field is extracted and mapped to a dedicated output column.
Missing or null fields are written as empty strings.

Usage
-----
    python3 flatten_kyc_csv.py -i input.csv -o output.csv
"""

import argparse
import csv
import json
import sys


# ---------------------------------------------------------------------------
# Output column definitions (ordered)
# ---------------------------------------------------------------------------
OUTPUT_COLUMNS = [
    # Original columns (raw_response is intentionally excluded)
    "user_id",
    "last_application_status",
    "id_card_url",

    # Top-level metadata
    "transaction_id",
    "partner_trx_id",
    "group_id",

    # Card info
    "card_country",
    "card_type",
    "card_iso_alpha3",
    "card_iso_alpha2",

    # Warnings & Errors (multiple entries joined with "|")
    "warning_codes",
    "warning_messages",
    "error_codes",
    "error_messages",

    # Image quality
    "img_blurriness_score",
    "img_low_light_score",
    "img_over_exposure_score",
    "img_card_width",
    "img_card_height",

    # OCR result — value + confidence score for each field
    "ocr_id_number",
    "ocr_id_number_score",
    "ocr_name",
    "ocr_name_score",
    "ocr_dob",
    "ocr_dob_score",
    "ocr_place_of_birth",
    "ocr_place_of_birth_score",
    "ocr_gender",
    "ocr_gender_score",
    "ocr_blood_type",
    "ocr_blood_type_score",
    "ocr_religion",
    "ocr_religion_score",
    "ocr_marital_status",
    "ocr_marital_status_score",
    "ocr_occupation",
    "ocr_occupation_score",
    "ocr_nationality",
    "ocr_nationality_score",
    "ocr_address",
    "ocr_address_score",
    "ocr_province",
    "ocr_province_score",
    "ocr_city",
    "ocr_city_score",
    "ocr_sub_district",
    "ocr_sub_district_score",
    "ocr_village",
    "ocr_village_score",
    "ocr_neighborhood_group",
    "ocr_neighborhood_group_score",
    "ocr_valid_until",
    "ocr_valid_until_score",

    # ID Verification — Spoofing
    "spoof_code",
    "spoof_message",
    "spoof_recap_score",
    "spoof_black_white_score",
    "spoof_color_print_score",
    "spoof_screenshot_score",

    # ID Verification — Forgery
    "forgery_code",
    "forgery_message",
    "forgery_score",

    # ID Verification — Landmark
    "landmark_code",
    "landmark_message",
    "landmark_portrait_background_color",
    "landmark_heuristic_check_status",
]


def _get(obj, *keys, default=""):
    """Safely navigate nested dicts/lists; return *default* on any miss."""
    cur = obj
    for key in keys:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, list) and isinstance(key, int):
            cur = cur[key] if key < len(cur) else None
        else:
            return default
    return cur if cur is not None else default


def _join_list(items, field):
    """Extract *field* from each dict in *items* and join them with '|'."""
    if not items:
        return ""
    return "|".join(str(item.get(field, "")) for item in items if field in item)


def flatten_row(raw_row):
    """
    Parse the `raw_response` JSON from *raw_row* and return a flat dict
    matching OUTPUT_COLUMNS.

    Parameters
    ----------
    raw_row : dict
        A single row read by csv.DictReader.

    Returns
    -------
    dict
        Flat dict with keys from OUTPUT_COLUMNS.
    bool
        True if JSON was parsed successfully, False otherwise.
    """
    # Start with empty values for every output column
    out = {col: "" for col in OUTPUT_COLUMNS}

    # --- Original non-JSON columns ---
    out["user_id"] = raw_row.get("user_id", "")
    out["last_application_status"] = raw_row.get("last_application_status", "")
    out["id_card_url"] = raw_row.get("id_card_url", "")

    # --- Parse raw_response JSON ---
    raw_json = raw_row.get("raw_response", "")
    if not raw_json or raw_json.strip() == "":
        # Nothing to parse; return row with empty JSON-derived columns
        return out, False

    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, ValueError) as exc:
        print(
            f"WARNING: Failed to parse raw_response JSON for user_id="
            f"'{raw_row.get('user_id', '?')}': {exc}",
            file=sys.stderr,
        )
        return out, False

    # --- Top-level metadata ---
    out["transaction_id"] = _get(data, "transactionId")
    out["partner_trx_id"] = _get(data, "partnerTrxId")
    out["group_id"] = _get(data, "groupId")

    # --- Card info (optional block) ---
    card = data.get("card") or {}
    out["card_country"] = card.get("country", "")
    out["card_type"] = card.get("type", "")
    out["card_iso_alpha3"] = card.get("isoAlpha3CountryCode", "")
    out["card_iso_alpha2"] = card.get("isoAlpha2CountryCode", "")

    # --- Warnings & Errors ---
    warnings = data.get("warnings") or []
    out["warning_codes"] = _join_list(warnings, "code")
    out["warning_messages"] = _join_list(warnings, "message")

    errors = data.get("errors") or []
    out["error_codes"] = _join_list(errors, "code")
    out["error_messages"] = _join_list(errors, "message")

    # --- Image Quality (imageQualityResult.front) ---
    iq_front = _get(data, "imageQualityResult", "front") or {}
    out["img_blurriness_score"] = _get(iq_front, "blurriness", "score")
    out["img_low_light_score"] = _get(iq_front, "lowLight", "score")
    out["img_over_exposure_score"] = _get(iq_front, "overExposure", "score")
    out["img_card_width"] = _get(iq_front, "cardDimension", "card_width")
    out["img_card_height"] = _get(iq_front, "cardDimension", "card_height")

    # --- OCR Result (ocrResult.front.data) ---
    ocr_data = _get(data, "ocrResult", "front", "data") or {}

    def _ocr(field_key, out_key):
        """Helper to extract OCR value + score for a single field."""
        field = ocr_data.get(field_key) or {}
        out[out_key] = field.get("value", "")
        out[out_key + "_score"] = field.get("score", "")

    _ocr("idNumber", "ocr_id_number")
    _ocr("name", "ocr_name")
    _ocr("dob", "ocr_dob")
    _ocr("placeOfBirth", "ocr_place_of_birth")
    _ocr("gender", "ocr_gender")
    _ocr("bloodType", "ocr_blood_type")
    _ocr("religion", "ocr_religion")
    _ocr("maritalStatus", "ocr_marital_status")
    _ocr("occupation", "ocr_occupation")
    _ocr("nationality", "ocr_nationality")
    _ocr("address", "ocr_address")
    _ocr("province", "ocr_province")
    _ocr("city", "ocr_city")
    _ocr("subDistrict", "ocr_sub_district")
    _ocr("village", "ocr_village")
    _ocr("neighborhoodAssociationGroup", "ocr_neighborhood_group")
    _ocr("validUntil", "ocr_valid_until")

    # --- ID Verification (idVerificationResult.front) ---
    id_ver_front = _get(data, "idVerificationResult", "front") or {}

    # Spoofing
    spoof = id_ver_front.get("spoofingResult") or {}
    out["spoof_code"] = spoof.get("code", "")
    out["spoof_message"] = spoof.get("message", "")
    out["spoof_recap_score"] = _get(spoof, "recapScore", "score")
    out["spoof_black_white_score"] = _get(spoof, "blackWhite", "score")
    out["spoof_color_print_score"] = _get(spoof, "colorPrint", "score")
    out["spoof_screenshot_score"] = _get(spoof, "screenshot", "score")

    # Forgery
    forgery = id_ver_front.get("forgeryResult") or {}
    out["forgery_code"] = forgery.get("code", "")
    out["forgery_message"] = forgery.get("message", "")
    out["forgery_score"] = _get(forgery, "summary", "score")

    # Landmark
    landmark = id_ver_front.get("landmarkResult") or {}
    out["landmark_code"] = landmark.get("code", "")
    out["landmark_message"] = landmark.get("message", "")

    # Extract named tag from landmarkTags list
    landmark_tags = landmark.get("landmarkTags") or []
    portrait_bg = next(
        (tag.get("value", "") for tag in landmark_tags if tag.get("name") == "portrait_background_color"),
        "",
    )
    out["landmark_portrait_background_color"] = portrait_bg

    # Extract named verification from landmarkVerification list
    landmark_verif = landmark.get("landmarkVerification") or []
    heuristic_status = next(
        (verification.get("status", "") for verification in landmark_verif if verification.get("name") == "heuristic_check"),
        "",
    )
    out["landmark_heuristic_check_status"] = heuristic_status

    return out, True


def main():
    parser = argparse.ArgumentParser(
        description="Flatten a KYC CSV file that contains nested JSON in the raw_response column."
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to the input CSV file.",
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to the output (flattened) CSV file.",
    )
    args = parser.parse_args()

    total = 0
    success = 0
    errors = 0

    with open(args.input, newline="", encoding="utf-8") as infile, \
         open(args.output, "w", newline="", encoding="utf-8") as outfile:

        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()

        for row in reader:
            total += 1
            flat_row, ok = flatten_row(row)
            writer.writerow(flat_row)
            if ok:
                success += 1
            else:
                errors += 1

    # Summary
    print(f"\nDone.")
    print(f"  Total rows processed : {total}")
    print(f"  Successfully parsed  : {success}")
    print(f"  JSON parse errors    : {errors}")


if __name__ == "__main__":
    main()
