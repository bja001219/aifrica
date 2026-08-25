import sqlite3

import pytest
from fastapi.testclient import TestClient

from main import DATABASE_PATH, app, connect_database, initialize_database


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_csv_is_loaded_into_sqlite(client: TestClient) -> None:
    assert DATABASE_PATH.name == "books.db"
    assert DATABASE_PATH.is_file()

    with sqlite3.connect(DATABASE_PATH) as connection:
        count, min_id, max_id = connection.execute(
            "SELECT COUNT(*), MIN(id), MAX(id) FROM books"
        ).fetchone()

    assert (count, min_id, max_id) == (30_000, 1, 30_000)


def test_frontend_is_served(client: TestClient) -> None:
    page = client.get("/")
    script = client.get("/static/app.js")
    stylesheet = client.get("/static/styles.css")

    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert 'id="search-form"' in page.text
    assert 'rel="icon" href="data:,"' in page.text
    assert script.status_code == 200
    assert "/api/books" in script.text
    assert "AbortController" in script.text
    assert stylesheet.status_code == 200


def test_database_initialization_is_idempotent(client: TestClient) -> None:
    initialize_database()
    initialize_database()

    with sqlite3.connect(DATABASE_PATH) as connection:
        count = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]

    assert count == 30_000


def test_database_connection_is_closed_after_use(client: TestClient) -> None:
    with connect_database() as connection:
        connection.execute("SELECT 1").fetchone()

    with pytest.raises(sqlite3.ProgrammingError):
        connection.execute("SELECT 1").fetchone()


def test_searches_korean_book_title(client: TestClient) -> None:
    response = client.get("/api/books", params={"query": "단단한 사전 입문"})

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"total", "total_pages", "page", "items"}
    assert body["total"] >= 1
    assert any(book["title"] == "단단한 사전 입문 (전면개정판)" for book in body["items"])


def test_paginates_results(client: TestClient) -> None:
    first = client.get("/api/books", params={"page": 1, "size": 10}).json()
    second = client.get("/api/books", params={"page": 2, "size": 10}).json()

    assert first["total"] == 30_000
    assert first["total_pages"] == 3_000
    assert len(first["items"]) == len(second["items"]) == 10
    assert first["items"][0]["id"] == 1
    assert second["items"][0]["id"] == 11


def test_returns_empty_search_result(client: TestClient) -> None:
    response = client.get("/api/books", params={"query": "존재하지않는도서명XYZ"})

    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "total": 0,
        "total_pages": 0,
    }


def test_page_after_last_page_is_empty(client: TestClient) -> None:
    response = client.get("/api/books", params={"page": 30_001, "size": 1})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_very_large_page_is_empty_instead_of_failing(client: TestClient) -> None:
    response = client.get("/api/books", params={"page": 10**30, "size": 20})

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_uses_parameter_binding_for_search(client: TestClient) -> None:
    response = client.get(
        "/api/books", params={"query": "%') OR 1=1; DROP TABLE books; --"}
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert client.get("/health").json()["books"] == 30_000


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": "invalid"},
        {"size": 0},
        {"size": 101},
        {"size": "invalid"},
    ],
)
def test_rejects_invalid_pagination(client: TestClient, params: dict) -> None:
    response = client.get("/api/books", params=params)

    assert response.status_code == 422
