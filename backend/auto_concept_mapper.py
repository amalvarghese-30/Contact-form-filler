# auto_concept_mapper.py
# Automatically maps raw fields -> normalized labels -> canonical concepts
# Uses your existing field_clustering.normalize_field_name()

import re
from dbmysql import get_conn
from field_clustering import normalize_field_name, CLUSTERING_RULES


# Canonical field concepts - what dashboard will ask user to fill
CANONICAL_CONCEPTS = {
    "full_name": "Full Name",
    "first_name": "First Name",
    "last_name": "Last Name",
    "email": "Email",
    "phone": "Phone",
    "company": "Company",
    "subject": "Subject",
    "message": "Message",
    "address": "Address",
    "city": "City",
    "state": "State/Province",
    "zip_code": "ZIP/Postal Code",
    "country": "Country",
    "website": "Website URL",
    "date_of_birth": "Date of Birth",
}


def setup_concept_map_table():
    """
    Create the mapping table if it doesn't exist.
    One row per normalized field label.
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS field_concept_map (
            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
            normalized_label VARCHAR(255) NOT NULL UNIQUE,
            canonical_concept VARCHAR(100),
            is_manual BOOLEAN DEFAULT FALSE,
            last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_concept (canonical_concept),
            INDEX idx_manual (is_manual)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )

    conn.commit()
    conn.close()


def match_to_canonical(normalized_label: str) -> str | None:
    """
    Match a normalized label to one of the canonical concepts
    by checking which CLUSTERING_RULES bucket it belongs to.
    Returns canonical concept string or None.
    """
    normalized_lower = normalized_label.lower()

    # First try exact match with known keys
    if normalized_lower in CANONICAL_CONCEPTS:
        return normalized_lower

    # Then use CLUSTERING_RULES patterns
    for concept, patterns in CLUSTERING_RULES.items():
        for pattern in patterns:
            if re.search(pattern, normalized_lower, re.IGNORECASE):
                return concept

    # No match -> unknown
    return None


def auto_map_concepts():
    """
    Automatically populate field_concept_map by:
    1. Getting all unique raw field names from raw_fields
    2. Normalizing them with normalize_field_name()
    3. Mapping to canonical concept (if any)
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # Get all unique raw field names
    cur.execute(
        """
        SELECT DISTINCT field_name, COUNT(*) AS frequency
        FROM raw_fields
        WHERE field_name IS NOT NULL
        GROUP BY field_name
        ORDER BY frequency DESC
        """
    )
    raw_fields = cur.fetchall()
    print(f"Found {len(raw_fields)} unique raw field names")

    for row in raw_fields:
        raw_name = row["field_name"]
        normalized = normalize_field_name(raw_name)
        canonical = match_to_canonical(normalized)

        try:
            cur.execute(
                """
                INSERT INTO field_concept_map (normalized_label, canonical_concept)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE
                    canonical_concept = VALUES(canonical_concept)
                """,
                (normalized, canonical),
            )
        except Exception as e:
            print(f"Error mapping {normalized}: {e}")

    conn.commit()
    conn.close()
    print("✓ Auto-mapping complete")


def get_active_concepts():
    """
    Return list of canonical concepts that actually appear in data.
    Used by dashboard to know which inputs to render.
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT DISTINCT canonical_concept
        FROM field_concept_map
        WHERE canonical_concept IS NOT NULL
        ORDER BY canonical_concept
        """
    )
    rows = cur.fetchall()
    conn.close()

    return [r["canonical_concept"] for r in rows]


def get_concept_details():
    """
    For each concept:
    - how many normalized labels map to it
    - simple prevalence flag (High/Medium/Low)
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT
            canonical_concept,
            COUNT(*) AS normalized_count
        FROM field_concept_map
        WHERE canonical_concept IS NOT NULL
        GROUP BY canonical_concept
        ORDER BY normalized_count DESC
        """
    )
    rows = cur.fetchall()
    conn.close()

    details = []
    for r in rows:
        concept = r["canonical_concept"]
        count = r["normalized_count"]
        human = CANONICAL_CONCEPTS.get(
            concept, concept.replace("_", " ").title()
        )

        if count > 10:
            prev = "High"
        elif count > 3:
            prev = "Medium"
        else:
            prev = "Low"

        details.append(
            {
                "concept": concept,
                "human_name": human,
                "normalized_label_count": count,
                "field_prevalence": prev,
            }
        )

    return details


def get_unmapped_fields():
    """
    Get normalized labels that have no canonical concept yet.
    These are candidates for inspection or new concepts.
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT normalized_label
        FROM field_concept_map
        WHERE canonical_concept IS NULL
        ORDER BY normalized_label
        """
    )
    rows = cur.fetchall()
    conn.close()

    return rows


def manually_map_concept(normalized_label: str, concept: str):
    """
    Optional manual override: map a specific normalized label to a concept.
    """
    if concept not in CANONICAL_CONCEPTS:
        return {"error": f"Unknown concept: {concept}"}

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE field_concept_map
        SET canonical_concept = %s, is_manual = TRUE
        WHERE normalized_label = %s
        """,
        (concept, normalized_label),
    )

    conn.commit()
    conn.close()
    return {"success": True, "message": f"Mapped {normalized_label} -> {concept}"}


def refresh_concepts_from_new_websites():
    """
    Run this after scraping more websites.
    It will detect new raw field names and map them.
    """
    print("Scanning for new field types...")
    auto_map_concepts()
    print("✓ Refresh complete")


def main():
    print("Setting up automatic concept mapping...")
    setup_concept_map_table()
    auto_map_concepts()

    print("\n📊 Active Concepts:")
    for c in get_concept_details():
        print(f"  • {c['human_name']}: {c['normalized_label_count']} variations")

    unmapped = get_unmapped_fields()
    print("\n⚠️ Unmapped normalized labels:")
    if unmapped:
        for r in unmapped[:20]:
            print("  •", r["normalized_label"])
    else:
        print("  None. All mapped.")

    print("\nDone.")


if __name__ == "__main__":
    main()
