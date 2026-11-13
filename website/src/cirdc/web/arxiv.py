"""Read-only adapter for the independently maintained arXiv catalog."""

import base64
import hashlib
import json
import os
import re
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pymysql
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.routing import Route

IDENTIFIER = re.compile(r"(\d{4}\.\d{4,5}|[a-z][a-z.-]+/\d{7})(?:v([1-9]\d*))?\Z")


def resolve(value):
    from urllib.parse import unquote, urlsplit

    value = value.strip().removeprefix("arXiv:")
    if "://" in value:
        url = urlsplit(value)
        if url.hostname not in ("arxiv.org", "export.arxiv.org"):
            raise ValueError("invalid_identifier")
        value = re.sub(r"^/(?:abs|pdf|src|html)/", "", unquote(url.path)).removesuffix(".pdf")
    match = IDENTIFIER.fullmatch(value)
    if not match:
        raise ValueError("invalid_identifier")
    return match[1], int(match[2]) if match[2] else None


class Catalog:
    def __init__(self, profile):
        self.config = json.loads(Path(profile).read_text())
        if self.config["mysql"]["database"] == "cirdc":
            raise ValueError("arxiv_database_required")

    @contextmanager
    def connection(self):
        allowed = ("host", "port", "user", "password", "unix_socket", "database")
        with (
            closing(
                pymysql.connect(
                    **{k: v for k, v in self.config["mysql"].items() if k in allowed},
                    charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=10,
                    read_timeout=30,
                )
            ) as db,
            db.cursor() as cur,
        ):
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute("SELECT application,instance_id,schema_version FROM arxiv_identity WHERE singleton=1")
            identity = cur.fetchone()
            if (
                not identity
                or identity["application"] != "cirdc-arxiv"
                or identity["instance_id"] != self.config["database_id"]
                or identity["schema_version"] != 1
            ):
                raise RuntimeError("arxiv_identity_mismatch")
            yield cur

    def paper(self, paper_id=None, arxiv_id=None):
        with self.connection() as cur:
            clause, key = ("id", paper_id) if paper_id is not None else ("arxiv_id", arxiv_id)
            cur.execute(
                "SELECT id,arxiv_id,title,authors_raw,abstract,document,deleted,oai_datestamp FROM papers WHERE "
                + clause
                + "=%s",
                (key,),
            )
            row = cur.fetchone()
            if not row:
                return None
            row["paper_id"] = str(row.pop("id"))
            row["metadata"] = {
                key: value
                for key, value in json.loads(row.pop("document")).items()
                if not key.endswith(("_ref", "_raw_ref"))
            }
            if row["oai_datestamp"]:
                row["oai_datestamp"] = str(row["oai_datestamp"])
            cur.execute(
                "SELECT version,version_date FROM versions WHERE paper_id=%s ORDER BY version",
                (row["paper_id"],),
            )
            row["versions"] = cur.fetchall()
            cur.execute("SELECT value FROM sync_state WHERE name='watermark'")
            watermark = cur.fetchone()
            row["metadata_coverage"] = {
                "scope": "metadata",
                "verified_through": json.loads(watermark["value"]).get("until") if watermark else None,
            }
            row["source"] = "arxiv"
            return row

    def index_connection(self):
        db = sqlite3.connect(
            Path(self.config["index_path"]).resolve().as_uri() + "?mode=ro", uri=True, timeout=5
        )
        try:
            if db.execute("SELECT database_id FROM identity").fetchall() != [(self.config["database_id"],)]:
                raise RuntimeError("arxiv_index_identity_mismatch")
            deadline = time.monotonic() + 8
            db.set_progress_handler(lambda: int(time.monotonic() > deadline), 20000)
            return db
        except BaseException:
            db.close()
            raise

    def overview(self):
        with closing(self.index_connection()) as db:
            count = db.execute("SELECT count(*) FROM metadata_docsize").fetchone()[0]
        return {
            "scope": "metadata",
            "indexed": count,
            "year_range": {"min": 1991, "max": datetime.now(timezone.utc).year},
        }

    def search(
        self,
        query,
        limit=20,
        cursor=None,
        *,
        field="all",
        sort="relevance",
        view="",
        k="20",
        terms="expand",
        category="",
        year_from="",
        year_to="",
        totals="",
    ):
        from .query import describe, fts_expression, parse

        if (
            not 1 <= limit <= 100
            or field not in ("all", "title", "authors", "abstract", "categories")
            or sort not in ("relevance", "year")
            or view not in ("", "top")
            or terms not in ("", "expand", "exact")
            or totals not in ("", "only", "defer")
        ):
            raise ValueError("invalid_search_options")
        if (
            len(query) > 200
            or len(category) > 64
            or category
            and not re.fullmatch("[A-Za-z0-9.-]+", category)
        ):
            raise ValueError("invalid_query")
        low = int(year_from) if year_from else None
        high = int(year_to) if year_to else None
        if any(v is not None and not 1991 <= v <= 2200 for v in (low, high)) or low and high and low > high:
            raise ValueError("invalid_year_range")
        top = int(k or 20)
        if top not in (10, 20, 50, 100):
            raise ValueError("invalid_top_k")
        if view == "top":
            limit = top
            sort = "relevance"
        signature = hashlib.sha256(
            json.dumps([query, field, sort, view, top, terms, category, low, high]).encode()
        ).hexdigest()
        offset = 0
        if cursor:
            try:
                saved = json.loads(base64.urlsafe_b64decode(cursor))
                if (
                    saved["q"] != signature
                    or type(saved["offset"]) is not int
                    or not 0 <= saved["offset"] <= 10000000
                ):
                    raise ValueError()
                offset = saved["offset"]
            except (ValueError, KeyError, TypeError):
                raise ValueError("invalid_cursor") from None
        exact_id = None
        requested_version = None
        if field == "all" and query.strip():
            try:
                exact_id, requested_version = resolve(query)
            except ValueError:
                pass
        groups = (
            parse(query, terms="exact" if terms == "exact" else "expand")
            if query.strip() and not exact_id
            else []
        )
        match = fts_expression(groups, field=None if field == "all" else field) if groups else ""
        if query.strip() and not exact_id and not groups:
            raise ValueError("invalid_query")
        if category:
            category_match = 'categories:("' + category.replace(".", " ").replace("-", " ") + '")'
            match = "(" + match + ") AND " + category_match if match else category_match
        where = []
        values = []
        if match:
            where.append("metadata MATCH ?")
            values.append(match)
        if exact_id:
            where.append("arxiv_id=?")
            values.append(exact_id)
        if category:
            where.append("instr(' '||lower(categories)||' ',' '||lower(?)||' ')>0")
            values.append(category)

        def year_sql(column):
            return (
                "CASE WHEN instr("
                + column
                + ",'/')>0 THEN (CASE WHEN CAST(substr("
                + column
                + ",instr("
                + column
                + ",'/')+1,2) AS INTEGER)>=91 THEN 1900 ELSE 2000 END)+CAST(substr("
                + column
                + ",instr("
                + column
                + ",'/')+1,2) AS INTEGER) WHEN length("
                + column
                + ")>=9 THEN 2000+CAST(substr("
                + column
                + ",1,2) AS INTEGER) ELSE NULL END"
            )

        year = year_sql("arxiv_id")
        if low:
            where.append(year + ">=?")
            values.append(low)
        if high:
            where.append(year + "<=?")
            values.append(high)
        clause = " WHERE " + " AND ".join(where) if where else ""
        explanation = {"terms": "exact" if terms == "exact" else "expand", "groups": describe(groups)}
        if exact_id:
            explanation["number"] = exact_id + ("v" + str(requested_version) if requested_version else "")
        with closing(self.index_connection()) as db:
            if exact_id and db.execute("SELECT 1 FROM sqlite_master WHERE name='documents'").fetchone():
                clause = clause.replace("arxiv_id=?", "rowid=(SELECT id FROM documents WHERE arxiv_id=?)")
            if totals != "defer":
                if not clause:
                    total = db.execute("SELECT COUNT(*) FROM metadata_docsize").fetchone()[0]
                elif (
                    not match
                    and not exact_id
                    and not category
                    and db.execute("SELECT 1 FROM sqlite_master WHERE name='documents'").fetchone()
                ):
                    filters = []
                    args = []
                    if low:
                        filters.append(year_sql("d.arxiv_id") + ">=?")
                        args.append(low)
                    if high:
                        filters.append(year_sql("d.arxiv_id") + "<=?")
                        args.append(high)
                    total = db.execute(
                        "SELECT COUNT(*) FROM documents d JOIN metadata_docsize s ON s.id=d.id WHERE "
                        + " AND ".join(filters),
                        args,
                    ).fetchone()[0]
                else:
                    total = db.execute("SELECT COUNT(*) FROM metadata" + clause, values).fetchone()[0]
            else:
                total = None
            rows = []
            if totals != "only":
                ordering = (
                    year + " DESC,arxiv_id DESC,rowid DESC"
                    if sort == "year"
                    else "rank,rowid"
                    if match
                    else "rowid DESC"
                )
                has_documents = db.execute("SELECT 1 FROM sqlite_master WHERE name='documents'").fetchone()
                if not match and not exact_id and not category and has_documents:
                    filters = []
                    args = []
                    if low:
                        filters.append(year_sql("d.arxiv_id") + ">=?")
                        args.append(low)
                    if high:
                        filters.append(year_sql("d.arxiv_id") + "<=?")
                        args.append(high)
                    filt = " WHERE " + " AND ".join(filters) if filters else ""
                    if sort == "year":
                        modern_low = max(2007, low or 2007)
                        modern_high = min(2099, high or 2099)
                        modern = []
                        if modern_low <= modern_high:
                            modern = db.execute(
                                "SELECT d.id,d.arxiv_id,"
                                + year_sql("d.arxiv_id")
                                + " FROM documents d JOIN metadata_docsize s ON s.id=d.id WHERE d.arxiv_id>=? AND d.arxiv_id<? ORDER BY d.arxiv_id DESC LIMIT ? OFFSET ?",
                                (
                                    f"{modern_low - 2000:02d}01",
                                    f"{modern_high - 2000:02d}13",
                                    limit + 1,
                                    offset,
                                ),
                            ).fetchall()
                        chosen = list(modern)
                        if len(chosen) < limit + 1:
                            modern_count = 0
                            if modern_low <= modern_high:
                                modern_count = db.execute(
                                    "SELECT COUNT(*) FROM documents d JOIN metadata_docsize s ON s.id=d.id WHERE d.arxiv_id>=? AND d.arxiv_id<?",
                                    (f"{modern_low - 2000:02d}01", f"{modern_high - 2000:02d}13"),
                                ).fetchone()[0]
                            old_where = ["instr(d.arxiv_id,'/')>0", *filters]
                            chosen.extend(
                                db.execute(
                                    "SELECT d.id,d.arxiv_id,"
                                    + year_sql("d.arxiv_id")
                                    + " FROM documents d JOIN metadata_docsize s ON s.id=d.id WHERE "
                                    + " AND ".join(old_where)
                                    + " ORDER BY "
                                    + year_sql("d.arxiv_id")
                                    + " DESC,d.arxiv_id DESC LIMIT ? OFFSET ?",
                                    [*args, limit + 1 - len(chosen), max(0, offset - modern_count)],
                                ).fetchall()
                            )
                    else:
                        chosen = db.execute(
                            "SELECT d.id,d.arxiv_id,"
                            + year_sql("d.arxiv_id")
                            + " FROM documents d JOIN metadata_docsize s ON s.id=d.id"
                            + filt
                            + " ORDER BY d.id DESC LIMIT ? OFFSET ?",
                            [*args, limit + 1, offset],
                        ).fetchall()
                    if chosen:
                        data = db.execute(
                            "SELECT rowid,arxiv_id,title,authors,abstract,categories FROM metadata WHERE rowid IN ("
                            + ",".join("?" for _ in chosen)
                            + ")",
                            [c[0] for c in chosen],
                        ).fetchall()
                        by_id = {row[0]: row for row in data}
                        rows = [(*by_id[c[0]], c[2]) for c in chosen if c[0] in by_id]

                else:
                    rows = db.execute(
                        "SELECT rowid,arxiv_id,title,authors,abstract,categories,"
                        + year
                        + " FROM metadata"
                        + clause
                        + " ORDER BY "
                        + ordering
                        + " LIMIT ? OFFSET ?",
                        [*values, limit + 1, offset],
                    ).fetchall()
        items = []
        for position, row in enumerate(rows[:limit], offset + 1):
            item = dict(
                zip(("paper_id", "arxiv_id", "title", "authors_raw", "abstract", "categories", "year"), row)
            )
            item["categories"] = item["categories"].split()
            item["year_source"] = "arxiv_identifier" if item["year"] is not None else None
            item["requested_version"] = requested_version
            if view == "top":
                item["position"] = position
            items.append(item)
        return {
            "scope": "metadata",
            "items": items,
            "query": explanation,
            "total": total,
            "total_exact": True,
            "partial": False,
            "next_cursor": base64.urlsafe_b64encode(
                json.dumps({"q": signature, "offset": offset + limit}).encode()
            ).decode()
            if len(rows) > limit and view != "top"
            else None,
        }


def routes(catalog=None):
    profile = os.environ.get("CIRDC_ARXIV_READER_CONFIG")
    if catalog is None and not profile:
        return []
    catalog = catalog or Catalog(profile)

    async def endpoint(request):
        try:
            params = request.query_params
            paper_id = request.path_params.get("paper_id")
            if request.url.path.endswith("/overview"):
                return JSONResponse(await run_in_threadpool(catalog.overview))
            if request.url.path.endswith("/resolve"):
                identifier, version = resolve(params.get("id", ""))
                paper = await run_in_threadpool(catalog.paper, arxiv_id=identifier)
                value = {"paper": paper, "paper_version": version}
            elif paper_id:
                paper = await run_in_threadpool(catalog.paper, paper_id=paper_id)
                value = (
                    {"versions": paper["versions"]}
                    if paper and request.url.path.endswith("/versions")
                    else {"paper": paper}
                )
            else:
                options = {
                    key: params[key]
                    for key in (
                        "field",
                        "sort",
                        "view",
                        "k",
                        "terms",
                        "category",
                        "year_from",
                        "year_to",
                        "totals",
                    )
                    if key in params
                }
                value = await run_in_threadpool(
                    catalog.search,
                    params.get("q", ""),
                    int(params.get("limit", 20)),
                    params.get("cursor"),
                    **options,
                )
                return JSONResponse(value)
            return JSONResponse(value, status_code=200 if paper else 404)
        except ValueError:
            return JSONResponse({"error": "invalid_arxiv_query"}, status_code=422)
        except (OSError, RuntimeError, sqlite3.Error, pymysql.MySQLError):
            return JSONResponse({"error": "arxiv_catalog_unavailable"}, status_code=503)

    return [
        Route("/api/arxiv/papers", endpoint),
        Route("/api/arxiv/overview", endpoint),
        Route("/api/arxiv/resolve", endpoint),
        Route("/api/arxiv/papers/{paper_id:int}", endpoint),
        Route("/api/arxiv/papers/{paper_id:int}/versions", endpoint),
    ]
