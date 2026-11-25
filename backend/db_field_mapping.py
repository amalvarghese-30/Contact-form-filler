# db_field_mapping.py
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from dbmysql import getconn  # existing helper
except Exception:
    getconn = None


@dataclass
class DBField:
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
    cluster_key: str
    cluster_score: float


class RawFieldsStore:
    """
    Loads per-website clustered field metadata from form_insights.raw_fields. [image:1]
    """

    def __init__(self, table: str = "raw_fields") -> None:
        if getconn is None:
            raise RuntimeError("dbmysql.getconn not available")
        self.table = table

    def load_for_website(self, website_id: int, min_score: float = 0.55) -> List[DBField]:
        conn = getconn()
        cur = conn.cursor(dictionary=True)

        cur.execute(
            f"""
            SELECT id, website_id, tag_name, field_id, field_name, field_type,
                   placeholder, class_name, form_id, form_class,
                   COALESCE(cluster_key,'unknown') AS cluster_key,
                   COALESCE(cluster_score,0) AS cluster_score
            FROM {self.table}
            WHERE website_id=%s
            ORDER BY COALESCE(cluster_score,0) DESC, id ASC
            """,
            (int(website_id),),
        )
        rows = cur.fetchall() or []
        cur.close()
        conn.close()

        out: List[DBField] = []
        for r in rows:
            score = float(r.get("cluster_score") or 0.0)
            ck = str(r.get("cluster_key") or "unknown").strip()
            if ck == "unknown":
                continue
            if score < float(min_score):
                continue
            out.append(
                DBField(
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
                    cluster_key=ck,
                    cluster_score=score,
                )
            )
        return out
