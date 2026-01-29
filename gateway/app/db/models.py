from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from gateway.app.db.base import Base


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    api_key_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    current_week_quota: Mapped[int] = mapped_column(Integer, default=0)
    used_quota: Mapped[int] = mapped_column(Integer, default=0)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    prompt_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    tokens_used: Mapped[int] = mapped_column(Integer)
    rule_triggered: Mapped[str | None] = mapped_column(String, nullable=True)
    action_taken: Mapped[str] = mapped_column(String)
    week_number: Mapped[int] = mapped_column(Integer)


class Rule(Base):
    __tablename__ = "rules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pattern: Mapped[str] = mapped_column(String)
    rule_type: Mapped[str] = mapped_column(String)  # block | guide
    message: Mapped[str] = mapped_column(Text)
    active_weeks: Mapped[str] = mapped_column(String)  # "1-2" or "3-6"
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class QuotaLog(Base):
    __tablename__ = "quota_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    week_number: Mapped[int] = mapped_column(Integer)
    tokens_granted: Mapped[int] = mapped_column(Integer)
    tokens_used: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[datetime] = mapped_column(DateTime)


class WeeklySystemPrompt(Base):
    """Weekly system prompt configuration.
    
    Allows configuring custom system prompts for specific week ranges
    to guide student learning progressively throughout the course.
    """
    
    __tablename__ = "weekly_system_prompts"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    week_start: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    week_end: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    
    def __repr__(self) -> str:
        return f"<WeeklySystemPrompt(id={self.id}, weeks={self.week_start}-{self.week_end})>"
    
    def is_current_week(self, week_number: int) -> bool:
        """Check if given week number falls within this prompt's range."""
        return self.week_start <= week_number <= self.week_end
