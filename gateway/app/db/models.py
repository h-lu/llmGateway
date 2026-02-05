from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from gateway.app.db.base import Base


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (
        Index("idx_students_email", "email"),
        Index("idx_students_created", "created_at"),
        Index("idx_students_provider_key", "provider_api_key_encrypted"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String, unique=True)
    api_key_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_week_quota: Mapped[int] = mapped_column(Integer, default=0)
    used_quota: Mapped[int] = mapped_column(Integer, default=0)

    # Balance Architecture: Student's own provider key
    provider_api_key_encrypted: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="学生自己的 AI 提供商 API Key（加密存储）"
    )
    provider_type: Mapped[str] = mapped_column(
        String(50), default="deepseek", comment="提供商类型: deepseek/openrouter"
    )

    @property
    def has_own_provider_key(self) -> bool:
        """检查学生是否设置了自己的提供商 Key"""
        return self.provider_api_key_encrypted is not None

    def get_provider_api_key(self, cipher=None) -> str | None:
        """解密获取学生的 API Key"""
        if not self.provider_api_key_encrypted:
            return None
        from gateway.app.core.security import decrypt_api_key

        return decrypt_api_key(self.provider_api_key_encrypted, cipher)


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_student_week", "student_id", "week_number"),
        Index("idx_conversations_timestamp", "timestamp"),
        Index("idx_conversations_rule_triggered", "rule_triggered"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<WeeklySystemPrompt(id={self.id}, weeks={self.week_start}-{self.week_end})>"

    def is_current_week(self, week_number: int) -> bool:
        """Check if given week number falls within this prompt's range."""
        return self.week_start <= week_number <= self.week_end


class QuotaLog(Base):
    __tablename__ = "quota_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"))
    week_number: Mapped[int] = mapped_column(Integer)
    tokens_granted: Mapped[int] = mapped_column(Integer)
    tokens_used: Mapped[int] = mapped_column(Integer)
    reset_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
