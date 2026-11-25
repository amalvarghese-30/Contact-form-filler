import re
from collections import defaultdict

# Mapping of field patterns to standard categories
FIELD_MAPPINGS = {
    "name": {
        "patterns": [
            r"^(first_?name|fname|first|name)$",
            r"^(given_?name)$",
        ],
        "category": "first_name",
    },
    "surname": {
        "patterns": [
            r"^(last_?name|lname|surname|family_?name)$",
            r"^(second_?name)$",
        ],
        "category": "last_name",
    },
    "email": {
        "patterns": [
            r"^(email|email_?address|mail|e_?mail|contact_email)$",
        ],
        "category": "email",
    },
    "phone": {
        "patterns": [
            r"^(phone|phone_?number|mobile|mobile_?number|tel|telephone)$",
        ],
        "category": "phone",
    },
    "company": {
        "patterns": [
            r"^(company|organization|org|business|firm)$",
        ],
        "category": "company",
    },
    "message": {
        "patterns": [
            r"^(message|comment|comments|text|description|subject)$",
        ],
        "category": "message",
    },
    "address": {
        "patterns": [
            r"^(address|street|city|state|country|postal_?code|zip)$",
        ],
        "category": "address",
    },
}

def normalize_field_name(field_name: str) -> tuple:
    """
    Normalize a field name and return (category, original_pattern).
    Returns ("unknown", pattern) if no match.
    """
    field_name_clean = (
        field_name.lower()
        .strip()
        .replace(" ", "_")
        .replace("-", "_")
    )

    for key, config in FIELD_MAPPINGS.items():
        for pattern in config["patterns"]:
            if re.match(pattern, field_name_clean):
                return (config["category"], field_name_clean)

    return ("unknown", field_name_clean)

def extract_and_normalize_fields(form_fields: list) -> dict:
    """
    Takes raw form fields and groups them by category.
    Returns: {
        "first_name": [
            {"pattern": "fname", "type": "text", "required": True},
            {"pattern": "first_name", "type": "text", "required": False},
        ],
        ...
    }
    """
    grouped = defaultdict(list)

    for field in form_fields:
        category, pattern = normalize_field_name(field.get("name", ""))
        grouped[category].append({
            "pattern": pattern,
            "type": field.get("type", "text"),
            "required": field.get("is_required", False),
            "placeholder": field.get("placeholder", ""),
        })

    return dict(grouped)

def update_field_statistics(analytics_conn, normalized_fields: dict):
    """
    Update the global field_statistics table with patterns found.
    """
    cur = analytics_conn.cursor()

    for category, fields in normalized_fields.items():
        for field_info in fields:
            pattern = field_info["pattern"]
            try:
                cur.execute(
                    """
                    INSERT INTO field_statistics (field_category, pattern, count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(field_category, pattern) DO UPDATE SET count = count + 1
                    """,
                    (category, pattern),
                )
            except Exception as e:
                print(f"Error updating stats for {category}:{pattern}: {e}")

    analytics_conn.commit()
