"""Student database operations."""
from gateway.app.db.models import Student
from gateway.app.db.session import get_session


def lookup_student_by_hash(api_key_hash: str) -> Student | None:
    """Find a student by their API key hash."""
    with get_session() as session:
        student = session.query(Student).filter(
            Student.api_key_hash == api_key_hash
        ).first()
        if student:
            # Detach from session to use outside
            session.expunge(student)
        return student


def update_student_quota(student_id: str, tokens_used: int) -> None:
    """Update student's used_quota by adding tokens_used."""
    with get_session() as session:
        student = session.query(Student).filter(Student.id == student_id).first()
        if student:
            student.used_quota += tokens_used
            session.commit()
