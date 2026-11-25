import re

# simple regex-based normalization
FIELD_NORMALIZATION = {
    r"^(first_?name|fname|first|given_?name)$": "first_name",
    r"^(last_?name|lname|surname|family_?name)$": "last_name",
    r"^(email|mail|e_?mail|contact_?email)$": "email",
    r"^(phone|mobile|tel|phone_?number|mobile_?number)$": "phone",
    r"^(company|organization|org|business|firm)$": "company",
    r"^(message|comment|text|subject|description)$": "message",
}

def normalize_field_name(raw: str) -> str:
    """
    Map raw DOM name/id to a category.
    Examples:
        fname, first_name, name  -> first_name
        lname, surname          -> last_name
    """
    if not raw:
        return "other"
    name = raw.lower().strip().replace(" ", "_").replace("-", "_")
    for pattern, category in FIELD_NORMALIZATION.items():
        if re.match(pattern, name):
            return category
    return "other"
