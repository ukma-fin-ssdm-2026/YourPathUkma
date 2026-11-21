"""
Тести на кількість SQL-запитів (відсутність N+1) та пагінацію для списків (issue #218).

Використання ШІ: файл створено за допомогою Antigravity (Claude Sonnet 4.6, Google DeepMind) для issue #218.
Перевірено: pytest tests/test_list_query_counts.py.
"""

from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from src.api.main import app
from src.db.base import utcnow
from src.db.enums import CertificateAvailability, DocumentMimeType, DocumentParseStatus, Trimester
from src.db.models.catalog import CertificateProgram, CertificateProgramCourse
from src.db.models.deanery import DeaneryPlanDocument, NormativeCourseEntry
from src.db.models.users import User
from src.db.session import get_engine, session_factory

client = TestClient(app)


@contextmanager
def capture_queries():
    queries = []
    engine = get_engine()

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        # Ігноруємо службові запити транзакцій / savepoints
        stmt = statement.strip().upper()
        if not (stmt.startswith("BEGIN") or stmt.startswith("COMMIT") or stmt.startswith("ROLLBACK")):
            queries.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield queries
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_certificate_programs_no_n_plus_one():
    with session_factory()() as db:
        # Створюємо 5 програм, кожна з 3 дисциплінами
        programs = []
        for i in range(5):
            prog = CertificateProgram(
                title=f"Test Program {i}",
                source_url=f"https://example.com/prog{i}",
                availability=CertificateAvailability.AVAILABLE,
                hidden=False,
                direction_ids=[1, 2],
            )
            db.add(prog)
            db.flush()
            programs.append(prog)
            for j in range(3):
                db.add(
                    CertificateProgramCourse(
                        program_id=prog.id,
                        raw_title=f"Course {i}-{j}",
                    )
                )
        db.commit()

    with capture_queries() as queries:
        resp = client.get("/api/v1/certificate-programs", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 5

    # Завдяки selectinload запитів має бути рівно 2 (один на програми, один на всі курси), а не 1 + N
    select_queries = [q for q in queries if q.strip().upper().startswith("SELECT")]
    assert len(select_queries) <= 2, f"Очікувалось <= 2 SELECT-запитів, але було {len(select_queries)}"


def test_certificate_programs_pagination():
    resp_all = client.get("/api/v1/certificate-programs", headers={"Authorization": "Bearer test"})
    assert resp_all.status_code == 200
    all_progs = resp_all.json()
    assert len(all_progs) >= 3

    resp_page = client.get("/api/v1/certificate-programs?limit=2&offset=1", headers={"Authorization": "Bearer test"})
    assert resp_page.status_code == 200
    page_progs = resp_page.json()
    assert len(page_progs) == 2
    assert page_progs[0]["id"] == all_progs[1]["id"]
    assert page_progs[1]["id"] == all_progs[2]["id"]


def test_deanery_documents_no_n_plus_one():
    with session_factory()() as db:
        user = db.scalar(select(User).where(User.id == 42))
        assert user is not None

        # Створюємо 4 документи, кожен з 3 нормативними дисциплінами
        for i in range(4):
            doc = DeaneryPlanDocument(
                student_id=user.id,
                academic_year=2024 + i,
                original_filename=f"plan_{i}.pdf",
                mime_type=DocumentMimeType.PDF,
                size_bytes=1024,
                sha256=f"hash_{i}_abc",
                content=b"%PDF-1.4 mock",
                parse_status=DocumentParseStatus.PARSED,
                uploaded_at=utcnow(),
            )
            db.add(doc)
            db.flush()
            for j in range(3):
                db.add(
                    NormativeCourseEntry(
                        document_id=doc.id,
                        raw_title=f"Normative {i}-{j}",
                        trimester=Trimester.AUTUMN,
                        credits=3.0,
                    )
                )
        db.commit()

    with capture_queries() as queries:
        resp = client.get("/api/v1/deanery-documents", headers={"Authorization": "Bearer test"})
        assert resp.status_code == 200
        docs = resp.json()["deanery_documents"]
        assert len(docs) >= 4

    # Завдяки selectinload запитів має бути не більше 2 (один на документи, один на всі нормативні курси)
    select_queries = [q for q in queries if q.strip().upper().startswith("SELECT")]
    assert len(select_queries) <= 2, f"Очікувалось <= 2 SELECT-запитів, але було {len(select_queries)}"


def test_deanery_documents_pagination():
    resp_all = client.get("/api/v1/deanery-documents", headers={"Authorization": "Bearer test"})
    assert resp_all.status_code == 200
    all_docs = resp_all.json()["deanery_documents"]
    assert len(all_docs) >= 3

    resp_page = client.get("/api/v1/deanery-documents?limit=2&offset=1", headers={"Authorization": "Bearer test"})
    assert resp_page.status_code == 200
    page_docs = resp_page.json()["deanery_documents"]
    assert len(page_docs) == 2
    assert page_docs[0]["id"] == all_docs[1]["id"]
    assert page_docs[1]["id"] == all_docs[2]["id"]
