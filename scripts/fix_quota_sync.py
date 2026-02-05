"""
Fix quota inconsistency - sync used_quota with actual conversation data
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from admin.db_utils_v2 import get_db_session
from gateway.app.db.models import Student, Conversation
from sqlalchemy import func

def sync_quota():
    """Sync student used_quota with actual conversation tokens"""
    with get_db_session() as session:
        # Get all students
        students = session.query(Student).all()
        
        print("=== Syncing Quota ===\n")
        
        for student in students:
            # Calculate actual tokens from conversations
            result = session.query(
                func.sum(Conversation.tokens_used)
            ).filter(
                Conversation.student_id == student.id
            ).first()
            
            actual_tokens = result[0] or 0
            old_quota = student.used_quota
            
            if old_quota != actual_tokens:
                print(f"{student.id} ({student.name}):")
                print(f"  Old used_quota: {old_quota}")
                print(f"  Actual tokens:  {actual_tokens}")
                
                # Update used_quota
                student.used_quota = actual_tokens
                print(f"  -> Updated to: {actual_tokens}\n")
            else:
                print(f"{student.id} ({student.name}): OK ({actual_tokens})\n")
        
        session.commit()
        print("✅ Sync complete!")

if __name__ == "__main__":
    sync_quota()
