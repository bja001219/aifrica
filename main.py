import csv
import math
import os
import sqlite3
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def project_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise RuntimeError("DATABASE_PATH must be relative to the project directory")

    resolved = (BASE_DIR / path).resolve()
    if resolved != BASE_DIR and BASE_DIR not in resolved.parents:
        raise RuntimeError("DATABASE_PATH must stay inside the project directory")
    return resolved


CSV_PATH = BASE_DIR / "books.csv"
DATABASE_PATH = project_relative_path(os.getenv("DATABASE_PATH", "books.db"))
STATIC_DIR = BASE_DIR / "static"
EXPECTED_COLUMNS = (
    "id",
    "title",
    "author",
    "publisher",
    "category",
    "published_date",
    "isbn",
    "price",
    "stock",
)
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class Book(BaseModel):
    id: int
    title: str
    author: str
    publisher: str
    category: str
    published_date: date
    isbn: str
    price: int
    stock: int


class BookPage(BaseModel):
    items: list[Book]
    page: int
    total: int
    total_pages: int


def parse_csv() -> list[tuple[int, str, str, str, str, str, str, int, int]]:
    if not CSV_PATH.is_file():
        raise RuntimeError(f"CSV file not found: {CSV_PATH}")

    books: list[tuple[int, str, str, str, str, str, str, int, int]] = []
    with CSV_PATH.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise RuntimeError(
                f"Unexpected CSV columns: {reader.fieldnames}; "
                f"expected: {list(EXPECTED_COLUMNS)}"
            )

        for line_number, row in enumerate(reader, start=2):
            try:
                if None in row or any(
                    row[column] is None or not row[column].strip()
                    for column in EXPECTED_COLUMNS
                ):
                    raise ValueError("missing or extra column value")

                book_id = int(row["id"])
                price = int(row["price"])
                stock = int(row["stock"])
                published_date = date.fromisoformat(row["published_date"])

                if book_id <= 0:
                    raise ValueError("id must be positive")
                if price < 0 or stock < 0:
                    raise ValueError("price and stock must be non-negative")
                if published_date.isoformat() != row["published_date"]:
                    raise ValueError("published_date must use YYYY-MM-DD")
                if len(row["isbn"]) != 13 or not row["isbn"].isdigit():
                    raise ValueError("isbn must contain 13 digits")

                books.append(
                    (
                        book_id,
                        row["title"],
                        row["author"],
                        row["publisher"],
                        row["category"],
                        row["published_date"],
                        row["isbn"],
                        price,
                        stock,
                    )
                )
            except (KeyError, TypeError, ValueError) as error:
                raise RuntimeError(f"Invalid CSV data at line {line_number}: {error}") from error

    return books


@contextmanager
def connect_database() -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database() -> None:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect_database() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                publisher TEXT NOT NULL,
                category TEXT NOT NULL,
                published_date TEXT NOT NULL,
                isbn TEXT NOT NULL,
                price INTEGER NOT NULL CHECK (price >= 0),
                stock INTEGER NOT NULL CHECK (stock >= 0)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)"
        )
        row_count = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if row_count == 0:
            books = parse_csv()
            connection.executemany(
                """
                INSERT OR IGNORE INTO books (
                    id, title, author, publisher, category,
                    published_date, isbn, price, stock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                books,
            )


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="Book Search API", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, int | str]:
    with connect_database() as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    return {"status": "ok", "books": row_count}


@app.get("/api/books", response_model=BookPage)
def search_books(
    query: Annotated[str, Query(max_length=200)] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> BookPage:
    search_term = query.strip()
    where_clause = ""
    parameters: list[str | int] = []

    if search_term:
        where_clause = "WHERE title LIKE ? ESCAPE '\\'"
        parameters.append(f"%{escape_like(search_term)}%")

    with connect_database() as connection:
        total = connection.execute(
            f"SELECT COUNT(*) FROM books {where_clause}", parameters
        ).fetchone()[0]
        offset = (page - 1) * size
        if offset >= total:
            rows = []
        else:
            rows = connection.execute(
                f"""
                SELECT id, title, author, publisher, category,
                       published_date, isbn, price, stock
                FROM books
                {where_clause}
                ORDER BY id
                LIMIT ? OFFSET ?
                """,
                [*parameters, size, offset],
            ).fetchall()

    return BookPage(
        items=[Book.model_validate(dict(row)) for row in rows],
        page=page,
        total=total,
        total_pages=math.ceil(total / size),
    )
