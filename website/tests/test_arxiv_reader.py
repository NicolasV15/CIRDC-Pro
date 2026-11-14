import json
import sqlite3

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from cirdc.web.arxiv import Catalog, resolve, routes


def test_identifiers_and_versions():
    assert resolve("https://export.arxiv.org/src/hep-th/9901001v2") == ("hep-th/9901001", 2)
    assert resolve("arXiv:2402.08954v1") == ("2402.08954", 1)
    with pytest.raises(ValueError):
        resolve("https://example.org/abs/2402.08954")
    with pytest.raises(ValueError):
        resolve("../2402.08954")


def test_search_is_readonly_and_pagination_bound_to_query(tmp_path):
    index = tmp_path / "index.sqlite"
    with sqlite3.connect(index) as db:
        db.execute("CREATE TABLE identity(database_id TEXT)")
        db.execute("INSERT INTO identity VALUES ('fixture')")
        db.execute(
            "CREATE VIRTUAL TABLE metadata USING fts5(arxiv_id UNINDEXED,title,authors,abstract,categories)"
        )
        db.executemany(
            "INSERT INTO metadata VALUES (?,?,?,?,?)",
            [(str(i), "analog study", "A", "text", "cs.AI") for i in range(4)],
        )
    profile = tmp_path / "config.json"
    profile.write_text(
        json.dumps(
            {"mysql": {"database": "fixture_arxiv"}, "database_id": "fixture", "index_path": str(index)}
        )
    )
    catalog = Catalog(profile)
    first = catalog.search("analog", 2)
    assert len(first["items"]) == 2
    second = catalog.search("analog", 2, first["next_cursor"])
    assert len(second["items"]) == 2
    assert {x["paper_id"] for x in first["items"]}.isdisjoint(x["paper_id"] for x in second["items"])
    with pytest.raises(ValueError):
        catalog.search("different", 2, first["next_cursor"])
    with pytest.raises(ValueError):
        catalog.search("analog", 101)
    assert not (tmp_path / "index.sqlite-wal").exists()


def test_routes_never_acquire():
    class Fake:
        def paper(self, **kw):
            return {"paper_id": "1", "versions": [{"version": 1}]}

        def search(self, *args):
            return {"items": []}

    with TestClient(Starlette(routes=routes(Fake()))) as client:
        assert client.get("/api/arxiv/papers?q=analog").status_code == 200
        assert client.get("/api/arxiv/papers/1").json()["paper"]["paper_id"] == "1"
        assert client.get("/api/arxiv/papers/1/versions").json()["versions"] == [{"version": 1}]
        assert client.post("/api/arxiv/papers/1").status_code == 405


@pytest.fixture
def search_catalog(tmp_path):
    index = tmp_path / "index.sqlite"
    papers = [
        ("hep-th/9901001", "Early physics", "Alice", "Vacuum theory", "hep-th"),
        ("0704.0001", "Operational amplifier design", "Alice", "A precision analog circuit", "hep-ph"),
        ("2402.08954", "Learning system", "Bob", "Operational amplifier study", "cs.AI"),
        ("2501.00001", "New amplifier", "Carol", "A new opamp design", "eess.SP"),
    ]
    with sqlite3.connect(index) as db:
        db.execute("CREATE TABLE identity(database_id TEXT)")
        db.execute("INSERT INTO identity VALUES ('search-fixture')")
        db.execute("CREATE TABLE documents(id INTEGER PRIMARY KEY,arxiv_id TEXT UNIQUE,content_hash TEXT)")
        db.execute(
            "CREATE VIRTUAL TABLE metadata USING fts5(arxiv_id UNINDEXED,title,authors,abstract,categories)"
        )
        for i, row in enumerate(papers, 1):
            db.execute(
                "INSERT INTO metadata(rowid,arxiv_id,title,authors,abstract,categories) VALUES (?,?,?,?,?,?)",
                (i, *row),
            )
            db.execute("INSERT INTO documents VALUES (?,?,?)", (i, row[0], "fixture"))
    profile = tmp_path / "reader.json"
    profile.write_text(
        json.dumps(
            {
                "mysql": {"database": "search_fixture"},
                "database_id": "search-fixture",
                "index_path": str(index),
            }
        )
    )
    return Catalog(profile)


def test_arxiv_search_fields_aliases_years_and_category(search_catalog):
    c = search_catalog
    assert c.overview()["indexed"] == 4
    assert len(c.search("", 2)["items"]) == 2
    assert c.search("Alice", field="authors")["total"] == 2
    assert c.search("Alice", field="title")["total"] == 0
    assert c.search("opamp")["total"] == 3
    assert c.search("opamp", terms="exact")["total"] == 1
    assert c.search("", category="CS.ai")["items"][0]["arxiv_id"] == "2402.08954"
    assert c.search("", year_from="1999", year_to="2007")["total"] == 2
    assert [p["year"] for p in c.search("", sort="year")["items"]] == [2025, 2024, 2007, 1999]
    assert c.search('"vacuum theory"')["total"] == 1
    assert c.search("0704.0001v2")["items"][0]["requested_version"] == 2
    assert c.search("0704.0001v2")["query"]["number"] == "0704.0001v2"
    assert c.search("opamp", totals="defer")["total"] is None
    assert c.search("opamp", totals="only")["items"] == []


def test_archive_filter_matches_its_subject_classes_only(tmp_path):
    index = tmp_path / "index.sqlite"
    papers = [
        ("2501.00001", "eess paper", "A", "x", "eess.SP cs.AR"),
        ("2501.00002", "cross-list", "A", "x", "cs.LG eess.SY"),
        ("2501.00003", "math physics", "A", "x", "math-ph"),
        ("2501.00004", "mathematics", "A", "x", "math.OC"),
        ("2501.00005", "condensed", "A", "x", "cond-mat.mes-hall"),
        ("2501.00006", "legacy", "A", "x", "cond-mat"),
    ]
    with sqlite3.connect(index) as db:
        db.execute("CREATE TABLE identity(database_id TEXT)")
        db.execute("INSERT INTO identity VALUES ('archive-fixture')")
        db.execute(
            "CREATE VIRTUAL TABLE metadata USING fts5(arxiv_id UNINDEXED,title,authors,abstract,categories)"
        )
        db.executemany("INSERT INTO metadata VALUES (?,?,?,?,?)", papers)
    profile = tmp_path / "reader.json"
    profile.write_text(
        json.dumps({"mysql": {"database": "archive"}, "database_id": "archive-fixture", "index_path": str(index)})
    )
    c = Catalog(profile)

    def ids(**options):
        return sorted(item["arxiv_id"] for item in c.search("", **options)["items"])

    assert ids(category="eess") == ["2501.00001", "2501.00002"]
    assert c.search("", category="eess", totals="only")["total"] == 2
    assert ids(category="math") == ["2501.00004"]
    assert ids(category="cond-mat") == ["2501.00005", "2501.00006"]
    assert ids(category="eess.SY") == ["2501.00002"]
    assert ids(category="eess.SP,cs.AR") == ["2501.00001"]  # cross-lists appear once
    # FTS tokenization equates dots and hyphens: exact category checks must remain.
    with sqlite3.connect(index) as db:
        db.execute("INSERT INTO metadata VALUES (?,?,?,?,?)", ("2501.00007", "punctuation", "A", "x", "eess-SP"))
    assert c.search("", category="eess.SP", totals="only")["total"] == 1
    assert c.search("", category="eess.SP,cs.AR", year_from="2025", year_to="2025", totals="only")["total"] == 1
    assert c.search("paper", category="eess.SP,cs.AR", totals="only")["total"] == 1
    with sqlite3.connect(index) as db:
        db.execute("DELETE FROM metadata WHERE arxiv_id='2501.00007'")

    assert ids(category=" eess.SP, EESS.sy ") == ["2501.00001", "2501.00002"]
    assert ids(category="math,math-ph") == ["2501.00003", "2501.00004"]
    assert c.search("", category="eess.SP,cs.AR,eess.SY", totals="only")["total"] == 2
    assert sorted(item["arxiv_id"] for item in c.search("paper", category="eess.SP,math")["items"]) == ["2501.00001"]
    assert ids(category="eess.SP,cs.AR", year_from="2026") == []
    first = c.search("", category="eess.SP,eess.SY", limit=1)
    second = c.search("", category="EESS.SY,eess.SP,eess.SP", limit=1, cursor=first["next_cursor"])
    assert first["items"][0]["arxiv_id"] != second["items"][0]["arxiv_id"]
    with pytest.raises(ValueError, match="invalid_cursor"):
        c.search("", category="eess.SP,math", limit=1, cursor=first["next_cursor"])
    for category in ["eess.SP,", ",eess.SP", "eess.SP OR cs.AR", "eess.SP,cs.AR) OR x", ",".join(f"cs.X{i}" for i in range(33))]:
        with pytest.raises(ValueError):
            c.search("", category=category)

    assert ids(category="cs") == ["2501.00001", "2501.00002"]
    assert sorted(item["arxiv_id"] for item in c.search("paper", category="eess")["items"]) == ["2501.00001"]


def test_unicode_queries_match_tex_encoded_metadata(tmp_path):
    index = tmp_path / "index.sqlite"
    papers = [
        ("0704.0001", "Diphoton production", "C. Bal\\'azs, E. L. Berger", "x", "hep-ph"),
        ("2611.14067", "Hall crystals in moir\\'e graphene", "A", "x", "cond-mat.str-el"),
        ("2611.14447", "Reflectance", "J. Mart\\'{\\i}n-Albo, M. Ib\\'a\\~nez", "x", "physics.ins-det"),
        ("2611.11648", "Search and rescue", "Jok\\=ubas Dim\\v{s}a", "x", "cs.RO"),
        ("2611.00001", "Unrelated", "Martin Balazs", "x", "cs.AI"),
    ]
    with sqlite3.connect(index) as db:
        db.execute("CREATE TABLE identity(database_id TEXT)")
        db.execute("INSERT INTO identity VALUES ('accent-fixture')")
        db.execute(
            "CREATE VIRTUAL TABLE metadata USING fts5(arxiv_id UNINDEXED,title,authors,abstract,categories)"
        )
        db.executemany("INSERT INTO metadata VALUES (?,?,?,?,?)", papers)
    profile = tmp_path / "reader.json"
    profile.write_text(
        json.dumps({"mysql": {"database": "accent"}, "database_id": "accent-fixture", "index_path": str(index)})
    )
    c = Catalog(profile)

    def ids(query, **options):
        return sorted(item["arxiv_id"] for item in c.search(query, **options)["items"])

    # A Unicode name matches both Unicode and TeX spellings; the unaccented spelling matches only itself.
    assert ids("Balázs", field="authors") == ["0704.0001", "2611.00001"]
    assert ids('"C. Balázs"', field="authors") == ["0704.0001"]
    assert ids("Martín", field="authors") == ["2611.00001", "2611.14447"]
    assert ids("Ibáñez", field="authors") == ["2611.14447"]
    assert ids("Dimša Jokūbas", field="authors") == ["2611.11648"]
    assert ids("moiré", field="title") == ["2611.14067"]
    assert ids("Balazs", field="authors") == ["2611.00001"]
    assert c.search("Balázs", field="authors", totals="only")["total"] == 2


def test_cursors_bind_filters_and_top_has_no_next_cursor(search_catalog):
    c = search_catalog
    first = c.search("opamp", 1)
    assert first["next_cursor"]
    with pytest.raises(ValueError):
        c.search("opamp", 1, first["next_cursor"], field="title")
    with pytest.raises(ValueError):
        c.search("", field="body")
    with pytest.raises(ValueError):
        c.search("", year_from="2025", year_to="2020")
    assert c.search("opamp", view="top", k="10")["next_cursor"] is None


def test_category_only_browses_newest_indexed_rows_without_text_ranking(tmp_path):
    index = tmp_path / "browse.sqlite"
    with sqlite3.connect(index) as db:
        db.execute("CREATE TABLE identity(database_id TEXT)")
        db.execute("INSERT INTO identity VALUES ('category-browse')")
        db.execute("CREATE VIRTUAL TABLE metadata USING fts5(arxiv_id UNINDEXED,title,authors,abstract,categories)")
        db.executemany("INSERT INTO metadata VALUES (?,?,?,?,?)", [
            ("2501.00001", "Earlier", "A", "x", "eess.SP"),
            ("2501.00002", "Later", "B", "x", "eess.SP cs.AR cs.LG"),
        ])
    profile = tmp_path / "reader.json"
    profile.write_text(json.dumps({"mysql": {"database": "archive"}, "database_id": "category-browse", "index_path": str(index)}))
    catalog = Catalog(profile)
    first = catalog.search("", category="eess", limit=1)
    assert first["items"][0]["arxiv_id"] == "2501.00002"
    second = catalog.search("", category="eess", limit=1, cursor=first["next_cursor"])
    assert second["items"][0]["arxiv_id"] == "2501.00001"
    assert second["total"] == 2
