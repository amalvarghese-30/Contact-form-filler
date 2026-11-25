import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple, Any

try:
    from dbmysql import getconn
except Exception:
    getconn = None


def _norm(s: Optional[str]) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[\s\-_]+", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class RawFieldRow:
    id: int
    website_id: int
    tag_name: str
    field_id: str
    field_name: str
    field_type: str
    placeholder: str
    class_name: str
    form_id: str
    form_class: str


CLUSTERS: Dict[str, Dict[str, List[str]]] = {
    "email": {"keywords": ["email", "e-mail", "mail", "your email"]},
    "phone": {"keywords": ["phone", "mobile", "tel", "telephone", "contact number", "whatsapp"]},
    "message": {"keywords": ["message", "comment", "enquiry", "inquiry", "details", "description", "your message"]},
    "subject": {"keywords": ["subject", "topic", "title", "reason"]},
    "first_name": {"keywords": ["first name", "firstname", "fname", "given name", "your first name"]},
    "last_name": {"keywords": ["last name", "lastname", "lname", "surname", "family name"]},
    "full_name": {"keywords": ["full name", "fullname", "your name", "name", "contact name"]},
    "company": {"keywords": ["company", "organization", "organisation", "business", "firm"]},
    "address": {"keywords": ["address", "street", "address line", "addr"]},
    "city": {"keywords": ["city", "town"]},
    "state": {"keywords": ["state", "province", "region"]},
    "country": {"keywords": ["country", "nation"]},
    "zip_code": {"keywords": ["zip", "zipcode", "postal", "postal code", "pincode", "pin code"]},
    "website": {"keywords": ["website", "web site", "url", "site"]},
}

EMAIL_TYPE_HINTS = {"email"}
PHONE_TYPE_HINTS = {"tel", "phone"}
URL_TYPE_HINTS = {"url"}
TEXTAREA_TAGS = {"textarea"}


def build_blob(r: RawFieldRow) -> str:
    parts = [
        r.tag_name,
        r.field_type,
        r.field_name,
        r.field_id,
        r.placeholder,
        r.class_name,
        r.form_id,
        r.form_class,
    ]
    return _norm(" ".join([p for p in parts if p]))


def score_cluster(cluster_key: str, blob: str, r: RawFieldRow) -> float:
    base = 0.0
    kw = CLUSTERS[cluster_key]["keywords"]

    for k in kw:
        k2 = _norm(k)
        if not k2:
            continue
        if k2 in blob:
            base = max(base, 0.80)
        base = max(base, _ratio(blob, k2) * 0.65)

    ftype = _norm(r.field_type)
    tag = _norm(r.tag_name)

    if cluster_key == "email" and ftype in EMAIL_TYPE_HINTS:
        base = max(base, 0.98)
    if cluster_key == "phone" and ftype in PHONE_TYPE_HINTS:
        base = max(base, 0.95)
    if cluster_key == "website" and ftype in URL_TYPE_HINTS:
        base = max(base, 0.92)
    if cluster_key == "message" and tag in TEXTAREA_TAGS:
        base = max(base, 0.92)

    if cluster_key == "full_name":
        if "username" in blob or "login" in blob:
            base *= 0.4

    return float(min(base, 1.0))


def choose_cluster(blob: str, r: RawFieldRow) -> Tuple[str, float]:
    best_key = "unknown"
    best_score = 0.0

    for ck in CLUSTERS.keys():
        s = score_cluster(ck, blob, r)
        if s > best_score:
            best_score = s
            best_key = ck

    if best_score < 0.55:
        return "unknown", best_score

    if best_key == "full_name":
        fn = score_cluster("first_name", blob, r)
        ln = score_cluster("last_name", blob, r)
        if max(fn, ln) >= best_score - 0.05 and max(fn, ln) >= 0.70:
            best_key = "first_name" if fn >= ln else "last_name"
            best_score = max(fn, ln)

    return best_key, best_score


def fetch_raw_fields(limit: Optional[int] = None, website_ids: Optional[List[int]] = None) -> List[RawFieldRow]:
    if getconn is None:
        raise RuntimeError("dbmysql.getconn not available")

    conn = getconn()
    cur = conn.cursor(dictionary=True)

    sql = """
      SELECT id, website_id, tag_name, field_id, field_name, field_type,
             placeholder, class_name, form_id, form_class
      FROM raw_fields
    """

    params: List[Any] = []
    where = []
    if website_ids:
        fmt = ",".join(["%s"] * len(website_ids))
        where.append(f"website_id IN ({fmt})")
        params.extend([int(x) for x in website_ids])

    if where:
        sql += " WHERE " + " AND ".join(where)

    if isinstance(limit, int) and limit > 0:
        sql += " LIMIT %s"
        params.append(int(limit))

    cur.execute(sql, tuple(params))
    rows = cur.fetchall() or []
    cur.close()
    conn.close()

    out: List[RawFieldRow] = []
    for r in rows:
        out.append(
            RawFieldRow(
                id=int(r.get("id") or 0),
                website_id=int(r.get("website_id") or 0),
                tag_name=str(r.get("tag_name") or ""),
                field_id=str(r.get("field_id") or ""),
                field_name=str(r.get("field_name") or ""),
                field_type=str(r.get("field_type") or ""),
                placeholder=str(r.get("placeholder") or ""),
                class_name=str(r.get("class_name") or ""),
                form_id=str(r.get("form_id") or ""),
                form_class=str(r.get("form_class") or ""),
            )
        )
    return out


def update_cluster_results(updates: List[Tuple[str, float, int]]) -> None:
    if getconn is None:
        raise RuntimeError("dbmysql.getconn not available")

    conn = getconn()
    cur = conn.cursor()
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    cur.executemany(
        """
        UPDATE raw_fields
        SET cluster_key=%s, cluster_score=%s, cluster_version='v2', clustered_at=%s
        WHERE id=%s
        """,
        [(ck, float(sc), ts, int(rid)) for (ck, sc, rid) in updates],
    )
    conn.commit()
    cur.close()
    conn.close()


def cluster_websites(
    website_ids: List[int],
    limit: Optional[int] = None,
    on_progress=None,  # on_progress(done:int, total:int, current_website_id:int)
) -> None:
    if not website_ids:
        return

    rows = fetch_raw_fields(limit=limit, website_ids=website_ids)
    if not rows:
        if callable(on_progress):
            try:
                on_progress(0, len(website_ids), None)
            except Exception:
                pass
        return

    # Group by website_id so we can report progress per website
    by_site: Dict[int, List[RawFieldRow]] = {}
    for r in rows:
        by_site.setdefault(int(r.website_id), []).append(r)

    total_sites = len(website_ids)
    done_sites = 0

    updates: List[Tuple[str, float, int]] = []

    # Iterate in the same order as input website_ids (better UX)
    for wid in [int(x) for x in website_ids]:
        site_rows = by_site.get(wid, [])
        for r in site_rows:
            blob = build_blob(r)
            ck, sc = choose_cluster(blob, r)
            updates.append((ck, sc, r.id))

        done_sites += 1
        if callable(on_progress):
            try:
                on_progress(done_sites, total_sites, wid)
            except Exception:
                pass

    if updates:
        update_cluster_results(updates)



def main() -> None:
    limit_env = os.getenv("CLUSTER_LIMIT", "").strip()
    limit = int(limit_env) if limit_env.isdigit() else None
    rows = fetch_raw_fields(limit=limit)
    updates: List[Tuple[str, float, int]] = []
    for r in rows:
        blob = build_blob(r)
        ck, sc = choose_cluster(blob, r)
        updates.append((ck, sc, r.id))
    if updates:
        update_cluster_results(updates)
    print(f"Clustered {len(updates)} raw_fields rows (v2).")


if __name__ == "__main__":
    main()
