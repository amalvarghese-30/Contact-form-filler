"""Field concepts, mappings, and random value pool management routes."""

import csv
import io
from typing import Any, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.database.connection import db_session
from app.schemas.settings import FieldMappingUpdateRequest, RandomValueCreateRequest
from auto_concept_mapper import CANONICAL_CONCEPTS, get_concept_details, manually_map_concept

router = APIRouter(prefix="/api", tags=["fields"])


@router.get("/field-frequency")
def get_field_frequency():
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT field_name AS field, COUNT(*) AS frequency
            FROM raw_fields
            WHERE field_name IS NOT NULL AND TRIM(field_name) <> ''
            GROUP BY field_name
            ORDER BY frequency DESC
            LIMIT 200
            """
        )
        return {"items": cur.fetchall() or []}


@router.get("/field-mapping")
def get_field_mapping():
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT COALESCE(cluster_key, 'unknown') AS clusterkey, COUNT(*) AS fieldcount
            FROM raw_fields
            GROUP BY COALESCE(cluster_key, 'unknown')
            ORDER BY fieldcount DESC
            """
        )
        return {"items": cur.fetchall() or []}


@router.get("/fill-form-template")
def get_fill_form_template():
    """Return canonical concepts grouped by prevalence (fixed field_prevalence key)."""
    concepts = get_concept_details() or []

    def prev(v: Any) -> str:
        return str(v or "").strip().lower()

    high = [c for c in concepts if prev(c.get("field_prevalence")) == "high"]
    medium = [c for c in concepts if prev(c.get("field_prevalence")) == "medium"]
    low = [c for c in concepts if prev(c.get("field_prevalence")) == "low"]

    if not high and not medium and not low and concepts:
        high = concepts

    return {
        "commonFields": high,
        "optionalFields": medium,
        "rareFields": low,
        "canonicalConcepts": CANONICAL_CONCEPTS,
    }


@router.get("/concepts-debug")
def concepts_debug(limit: int = 20):
    concepts = get_concept_details() or []
    return {
        "count": len(concepts),
        "sample": concepts[: max(0, int(limit))],
        "fieldprevalence_values": sorted(list({str(c.get("field_prevalence")) for c in concepts})),
    }


@router.get("/field-mappings/details")
def get_field_mapping_details(
    search: Optional[str] = None,
    concept: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    """Detailed view of raw/normalized field mappings and canonical concepts."""
    where_clauses: List[str] = []
    params: List[Any] = []
    if search and search.strip():
        where_clauses.append("fcm.normalized_label LIKE %s")
        params.append(f"%{search.strip()}%")
    if concept and concept != "all":
        if concept == "unmapped":
            where_clauses.append("fcm.canonical_concept IS NULL")
        else:
            where_clauses.append("fcm.canonical_concept = %s")
            params.append(concept)

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with db_session(dictionary=True) as (_, cur):
        cur.execute(f"SELECT COUNT(*) AS total FROM field_concept_map fcm {where_sql}", tuple(params))
        total = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            f"""
            SELECT fcm.id, fcm.normalized_label, fcm.canonical_concept, fcm.is_manual, fcm.last_updated
            FROM field_concept_map fcm
            {where_sql}
            ORDER BY fcm.is_manual DESC, fcm.normalized_label ASC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limit, skip]),
        )
        rows = cur.fetchall() or []

    for r in rows:
        if r.get("last_updated"):
            r["last_updated"] = str(r["last_updated"])
        r["is_manual"] = bool(r.get("is_manual"))

    return {"total": total, "items": rows, "canonicalConcepts": CANONICAL_CONCEPTS}


@router.put("/field-mappings")
def update_field_mapping(req: FieldMappingUpdateRequest):
    if req.canonical_concept not in CANONICAL_CONCEPTS:
        raise HTTPException(status_code=400, detail=f"Unknown canonical concept: {req.canonical_concept}")
    res = manually_map_concept(req.normalized_label.strip(), req.canonical_concept)
    if res.get("error"):
        raise HTTPException(status_code=400, detail=res["error"])
    return {"ok": True, "message": res.get("message")}


@router.get("/random-values")
def list_random_values(
    concept: Optional[str] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
):
    where_sql = "WHERE field_concept = %s" if (concept and concept != "all") else ""
    params: List[Any] = [concept] if where_sql else []

    with db_session(dictionary=True) as (_, cur):
        cur.execute(f"SELECT COUNT(*) AS total FROM random_value_pool {where_sql}", tuple(params))
        total = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            f"""
            SELECT id, field_concept, value, created_at
            FROM random_value_pool
            {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limit, skip]),
        )
        rows = cur.fetchall() or []

        cur.execute("SELECT field_concept, COUNT(*) AS count FROM random_value_pool GROUP BY field_concept ORDER BY count DESC")
        counts = cur.fetchall() or []

    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])

    return {"total": total, "items": rows, "counts_by_concept": counts}


@router.post("/random-values")
def add_random_value(req: RandomValueCreateRequest):
    with db_session() as (_, cur):
        cur.execute(
            "INSERT INTO random_value_pool (field_concept, value) VALUES (%s, %s)",
            (req.field_concept.strip(), req.value.strip()),
        )
        vid = int(cur.lastrowid)
    return {"ok": True, "id": vid}


@router.delete("/random-values/{value_id}")
def delete_random_value(value_id: int):
    with db_session() as (_, cur):
        cur.execute("DELETE FROM random_value_pool WHERE id=%s", (value_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Value not found")
    return {"ok": True}


@router.post("/random-values/import-csv")
async def import_random_values_csv(fieldconcept: str = Form(...), csvfile: UploadFile = File(...)):
    raw = (await csvfile.read()).decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(raw))
    values: List[str] = []
    for row in reader:
        if not row:
            continue
        v = (row[0] or "").strip()
        if v:
            values.append(v)

    with db_session() as (_, cur):
        cur.execute("DELETE FROM random_value_pool WHERE field_concept = %s", (fieldconcept,))
        if values:
            cur.executemany(
                "INSERT INTO random_value_pool (field_concept, value) VALUES (%s, %s)",
                [(fieldconcept, v) for v in values],
            )

    return {"ok": True, "fieldconcept": fieldconcept, "imported": len(values), "filename": csvfile.filename}


@router.get("/random-values/export-csv")
def export_random_values_csv(concept: Optional[str] = None):
    where_sql = "WHERE field_concept = %s" if (concept and concept != "all") else ""
    params = (concept,) if where_sql else ()

    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            f"SELECT field_concept, value FROM random_value_pool {where_sql} ORDER BY field_concept, id",
            params,
        )
        rows = cur.fetchall() or []

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field_concept", "value"])
    for r in rows:
        writer.writerow([r["field_concept"], r["value"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=random_values_export.csv"},
    )


@router.get("/random-values/{fieldconcept}/sample")
def get_random_values_sample(fieldconcept: str, limit: int = 5):
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            "SELECT value FROM random_value_pool WHERE field_concept=%s ORDER BY RAND() LIMIT %s",
            (fieldconcept, int(limit)),
        )
        return {"fieldconcept": fieldconcept, "values": [r["value"] for r in (cur.fetchall() or [])]}


@router.get("/random-values/{fieldconcept}/count")
def get_pool_count(fieldconcept: str):
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT COUNT(*) AS count FROM random_value_pool WHERE field_concept=%s", (fieldconcept,))
        row = cur.fetchone()
        return {"fieldconcept": fieldconcept, "count": int(row["count"] if row else 0)}
