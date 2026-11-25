# field_clustering.py

from dbmysql import get_conn
import re

# ---------------- CLUSTERING RULES ----------------

CLUSTERING_RULES = {
    "first_name": [
        r"\bfirst name\b",
        r"\bfirstname\b",
        r"\bfname\b",
        r"\bgiven.?name\b",
        r"\bforename\b",
    ],
    "last_name": [
        r"\blast name\b",
        r"\blastname\b",
        r"\blname\b",
        r"\bsurname\b",
        r"\bfamily.?name\b",
    ],
    "full_name": [
        r"\bname\b",
        r"\byour name\b",
        r"\benter name\b",
        r"\bcontact name\b",
        r"\bvisitor name\b",
        r"full.?name",
        r"fullname",
    ],
    "email": [
        r"email",
        r"e-mail",
        r"\byour email\b",
        r"\benter email\b",
        r"\bmail id\b",
    ],
    "phone": [
        r"\bphone\b",
        r"\btelephone\b",
        r"\btel\b",
        r"\bmobile\b",
        r"\bcontact number\b",
        r"\bphone number\b",
        r"\byour phone\b",
        r"\benter phone\b",
        r"\bwhatsapp\b",
    ],
    "company": [
        r"\bcompany\b",
        r"\borganization\b",
        r"\borganisation\b",
        r"\bbusiness\b",
        r"\bfirm\b",
    ],
    "subject": [
        r"\bsubject\b",
        r"\byour subject\b",
        r"\benter subject\b",
        r"\btopic\b",
        r"\btitle\b",
    ],
    "message": [
        r"\bmessage\b",
        r"\byour message\b",
        r"\benter message\b",
        r"\bquery\b",
        r"\bquestion\b",
        r"\brequirement\b",
        r"\bcomments?\b",
        r"\bfeedback\b",
        r"\bdetails\b",
        r"\bdescription\b",
        r"\brequest\b",
    ],
    "address": [
        r"\baddress\b",
        r"\bstreet\b",
        r"street.?address",
        r"\blocation\b",
    ],
    "city": [
        r"\bcity\b",
        r"\btown\b",
        r"\blocality\b",
    ],
    "state": [
        r"\bstate\b",
        r"\bprovince\b",
        r"\bregion\b",
        r"\bcounty\b",
    ],
    "zip_code": [
        r"\bzip\b",
        r"postal.?code",
        r"\bpostcode\b",
        r"\bpincode\b",
        r"\bpin code\b",
    ],
    "country": [
        r"\bcountry\b",
        r"\bnation\b",
    ],
    "website": [
        r"website",
        r"web.?site",
        r"\burl\b",
        r"homepage",
    ],
}


def normalize_field_name(raw_name: str, placeholder: str | None = None) -> str:
    """
    Normalize a field into a standard semantic label (cluster_label).
    Looks at both field_name and placeholder, biased towards
    contact-form concepts (name, email, phone, subject, message).
    """
    if not raw_name and not placeholder:
        return "unknown"

    combined = ((raw_name or "") + " " + (placeholder or "")).lower()

    # Strip common prefixes/suffixes / junk
    combined = re.sub(
        r"(your_|your-|_your|contact_|contact-|form_|form-|field_|field-)",
        "",
        combined,
    )
    combined = re.sub(r"(_field|_input|_text|-field|-input|-text)$", "", combined)
    combined = re.sub(r"[_-]+", " ", combined)
    combined = re.sub(r"\s+", " ", combined).strip()

    # Try each clustering rule
    for cluster_name, patterns in CLUSTERING_RULES.items():
        for pattern in patterns:
            if re.search(pattern, combined):
                return cluster_name

    # Anything not matched is treated as unknown; filler will ignore it
    return "unknown"


def get_unique_raw_fields():
    """Get all unique raw field names from raw_fields table."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    cur.execute(
        """
        SELECT DISTINCT field_name
        FROM raw_fields
        WHERE field_name IS NOT NULL
        ORDER BY field_name
        """
    )
    rows = cur.fetchall()
    conn.close()
    return [r["field_name"] for r in rows]


def build_field_mapping_table():
    """
    Create or update field_mapping table that shows raw → normalized mapping.
    This is mainly for dashboard visualization.
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    # Create mapping table if not exists
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS field_mapping (
            id INT UNSIGNED NOT NULL AUTO_INCREMENT,
            raw_name VARCHAR(255) NOT NULL UNIQUE,
            normalized_name VARCHAR(255) NOT NULL,
            PRIMARY KEY (id),
            INDEX idx_normalized (normalized_name)
        )
        """
    )
    conn.commit()

    # Get all unique raw fields
    unique_fields = get_unique_raw_fields()
    print(f"Found {len(unique_fields)} unique raw field names")

    # Clear and rebuild mapping
    cur.execute("DELETE FROM field_mapping")
    conn.commit()

    for raw_name in unique_fields:
        normalized = normalize_field_name(raw_name, None)
        cur.execute(
            """
            INSERT INTO field_mapping (raw_name, normalized_name)
            VALUES (%s, %s)
            """,
            (raw_name, normalized),
        )

    conn.commit()
    conn.close()
    print(f"Created field_mapping with {len(unique_fields)} entries")


def update_raw_fields_cluster_labels():
    """
    Force-update cluster_label and normalized_name for ALL raw_fields rows,
    based on field_name + placeholder and the clustering rules.
    """
    conn = get_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT id, field_name, placeholder
        FROM raw_fields
        """
    )
    rows = cur.fetchall()
    print(f"Recomputing cluster_label for {len(rows)} raw_fields rows")

    counts: dict[str, int] = {}

    for r in rows:
        rid = r["id"]
        raw_name = r["field_name"]
        placeholder = r.get("placeholder")
        cluster = normalize_field_name(raw_name, placeholder)

        counts[cluster] = counts.get(cluster, 0) + 1

        cur.execute(
            """
            UPDATE raw_fields
            SET cluster_label = %s,
                normalized_name = %s
            WHERE id = %s
            """,
            (cluster, cluster, rid),
        )

    conn.commit()
    conn.close()
    print("Finished updating raw_fields.cluster_label and raw_fields.normalized_name.")
    print("Cluster distribution:", counts)


def main():
    print("Building field clustering mapping and updating raw_fields...")
    build_field_mapping_table()
    update_raw_fields_cluster_labels()
    print("Done.")


if __name__ == "__main__":
    main()
