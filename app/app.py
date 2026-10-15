"""Library Book Service - a small layered REST API used as the test subject.
Layers: Model (Book) -> Repository (BookRepository, DAO over SQLite)
        -> Service (BookService) -> Controller (Flask routes)."""
import os, sqlite3, threading
from dataclasses import dataclass, asdict
from flask import Flask, jsonify, request, abort

DB_PATH = os.environ.get("DB_PATH", "library.db")
SEED_ROWS = int(os.environ.get("SEED_ROWS", "100"))


@dataclass
class Book:                                   # Model / entity
    id: int
    title: str
    author: str
    year: int
    available: bool


class Database:                               # Singleton: one connection factory
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, path=DB_PATH):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.path = path
        return cls._instance

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


class BookRepository:                         # Repository / DAO
    def __init__(self, db: Database):
        self.db = db

    def init_schema(self, seed_rows: int):
        with self.db.connect() as c:
            c.execute("DROP TABLE IF EXISTS books")
            c.execute("""CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, author TEXT NOT NULL,
                year INTEGER NOT NULL, available INTEGER NOT NULL DEFAULT 1)""")
            c.execute("CREATE INDEX idx_books_author ON books(author)")
            c.executemany("INSERT INTO books(title, author, year, available) VALUES (?,?,?,?)",
                          [(f"Book {i}", f"Author {i % 10}", 1990 + i % 35, i % 3 != 0)
                           for i in range(1, seed_rows + 1)])

    def _row(self, r):
        return Book(r["id"], r["title"], r["author"], r["year"], bool(r["available"]))

    def find_all(self, limit: int, offset: int):
        with self.db.connect() as c:
            rows = c.execute("SELECT * FROM books ORDER BY id LIMIT ? OFFSET ?", (limit, offset))
            return [self._row(r) for r in rows]

    def find_by_id(self, book_id: int):
        with self.db.connect() as c:
            r = c.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
            return self._row(r) if r else None

    def save(self, title, author, year):
        with self.db.connect() as c:
            cur = c.execute("INSERT INTO books(title, author, year, available) VALUES (?,?,?,1)",
                            (title, author, year))
            return Book(cur.lastrowid, title, author, year, True)


class BookService:                            # Service: business rules
    def __init__(self, repo: BookRepository):
        self.repo = repo

    def list_books(self, page: int, size: int):
        size = max(1, min(size, 50))
        return self.repo.find_all(size, (max(page, 1) - 1) * size)

    def get_book(self, book_id: int):
        return self.repo.find_by_id(book_id)

    def add_book(self, data: dict):
        if not data.get("title") or not data.get("author"):
            raise ValueError("title and author are required")
        return self.repo.save(data["title"], data["author"], int(data.get("year", 2000)))


def create_app() -> Flask:                    # Factory: builds and wires the app
    repo = BookRepository(Database())
    repo.init_schema(SEED_ROWS)
    service = BookService(repo)
    app = Flask(__name__)

    @app.get("/api/v1/health")
    def health():
        return jsonify(status="ok")

    @app.get("/api/v1/books")
    def list_books():
        page = int(request.args.get("page", 1)); size = int(request.args.get("size", 20))
        return jsonify([asdict(b) for b in service.list_books(page, size)])

    @app.get("/api/v1/books/<int:book_id>")
    def get_book(book_id):
        book = service.get_book(book_id)
        if book is None:
            abort(404)
        return jsonify(asdict(book))

    @app.post("/api/v1/books")
    def add_book():
        try:
            return jsonify(asdict(service.add_book(request.get_json(force=True)))), 201
        except ValueError as e:
            return jsonify(error=str(e)), 400

    return app


if __name__ == "__main__":
    from waitress import serve
    port = int(os.environ.get("PORT", "5000"))
    serve(create_app(), host="0.0.0.0", port=port, threads=8)
