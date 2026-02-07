"""
TeachProxy Admin Panel - Database Utilities v2
现代化的数据库工具类，支持同步操作
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, func, desc, and_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

# 导入项目配置和模型
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from gateway.app.core.config import settings  # noqa: E402
from gateway.app.db.models import (  # noqa: E402
    Student,
    Conversation,
    Rule,
    WeeklySystemPrompt,
    QuotaLog,
)
from gateway.app.core.utils import get_current_week_number  # noqa: E402


# 创建同步数据库引擎
# 注意：将 asyncpg 替换为 psycopg2 用于同步操作
def get_sync_database_url() -> str:
    """获取同步数据库连接 URL"""
    url = settings.database_url
    # 替换异步驱动为同步驱动
    url = url.replace("+aiosqlite", "+pysqlite")
    url = url.replace("+asyncpg", "")
    return url


engine = create_engine(
    get_sync_database_url(),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Session:
    """获取数据库会话的上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except SQLAlchemyError as e:
        session.rollback()
        raise e
    finally:
        session.close()


# ==================== 仪表板统计 ====================


def get_dashboard_stats() -> Dict[str, Any]:
    """获取仪表板统计数据"""
    with get_db_session() as session:
        # 基础统计
        student_count = session.query(func.count(Student.id)).scalar() or 0
        conversation_count = session.query(func.count(Conversation.id)).scalar() or 0
        rule_count = session.query(func.count(Rule.id)).scalar() or 0

        # 今日统计
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        conversations_today = (
            session.query(func.count(Conversation.id))
            .filter(Conversation.timestamp >= today_start)
            .scalar()
            or 0
        )

        tokens_today = (
            session.query(func.sum(Conversation.tokens_used))
            .filter(Conversation.timestamp >= today_start)
            .scalar()
            or 0
        )

        # 阻断统计
        blocked_count = (
            session.query(func.count(Conversation.id))
            .filter(Conversation.action_taken == "blocked")
            .scalar()
            or 0
        )

        # 总 Token 使用
        total_tokens = session.query(func.sum(Conversation.tokens_used)).scalar() or 0

        # 配额使用率计算
        total_quota = session.query(func.sum(Student.current_week_quota)).scalar() or 0
        total_used = session.query(func.sum(Student.used_quota)).scalar() or 0
        quota_usage_rate = (total_used / total_quota * 100) if total_quota > 0 else 0

        # 本周配额日志统计
        current_week = get_current_week_number()
        week_quota_logs = (
            session.query(func.sum(QuotaLog.tokens_used))
            .filter(QuotaLog.week_number == current_week)
            .scalar()
            or 0
        )

        return {
            "students": student_count,
            "conversations": conversation_count,
            "rules": rule_count,
            "blocked": blocked_count,
            "total_tokens": int(total_tokens),
            "conversations_today": int(conversations_today),
            "tokens_today": int(tokens_today),
            "quota_usage_rate": quota_usage_rate,
            "week_tokens": int(week_quota_logs),
            "current_week": current_week,
        }


def get_recent_activity(days: int = 7) -> List[Dict[str, Any]]:
    """获取最近的活动数据（用于图表）"""
    with get_db_session() as session:
        start_date = datetime.now() - timedelta(days=days)

        # 按日期统计对话数和 Token 使用
        results = (
            session.query(
                func.date(Conversation.timestamp).label("date"),
                func.count(Conversation.id).label("count"),
                func.sum(Conversation.tokens_used).label("tokens"),
            )
            .filter(Conversation.timestamp >= start_date)
            .group_by(func.date(Conversation.timestamp))
            .order_by(func.date(Conversation.timestamp))
            .all()
        )

        return [
            {
                "date": str(r.date),
                "conversations": r.count,
                "tokens": int(r.tokens or 0),
            }
            for r in results
        ]


# ==================== 学生管理 ====================


def get_all_students() -> List[Dict[str, Any]]:
    """获取所有学生列表，返回字典列表避免 Session 问题"""
    with get_db_session() as session:
        students = session.query(Student).order_by(Student.created_at.desc()).all()
        # 在 Session 内转换为字典
        return [
            {
                "id": s.id,
                "name": s.name,
                "email": s.email,
                "api_key_hash": s.api_key_hash,
                "created_at": s.created_at,
                "current_week_quota": s.current_week_quota,
                "used_quota": s.used_quota,
                "provider_api_key_encrypted": s.provider_api_key_encrypted,
                "provider_type": s.provider_type,
            }
            for s in students
        ]


def get_student_by_id(student_id: str) -> Optional[Dict[str, Any]]:
    """根据 ID 获取学生（返回 dict，避免 ORM 序列化问题）"""
    with get_db_session() as session:
        s = session.query(Student).filter(Student.id == student_id).first()
        if not s:
            return None
        return {
            "id": s.id,
            "name": s.name,
            "email": s.email,
            "api_key_hash": s.api_key_hash,
            "created_at": s.created_at,
            "current_week_quota": s.current_week_quota,
            "used_quota": s.used_quota,
            "provider_api_key_encrypted": s.provider_api_key_encrypted,
            "provider_type": s.provider_type,
        }


def create_student(
    name: str, email: str, quota: int = 10000
) -> tuple[Dict[str, Any], str]:
    """
    创建新学生

    Returns:
        (student, api_key) 元组
    """
    import uuid
    from gateway.app.core.security import hash_api_key, generate_api_key

    # 生成 API Key
    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    student = Student(
        id=str(uuid.uuid4()),
        name=name,
        email=email,
        api_key_hash=api_key_hash,
        created_at=datetime.now(),
        current_week_quota=quota,
        used_quota=0,
    )

    with get_db_session() as session:
        session.add(student)
        session.flush()
        session.refresh(student)
        student_dict = {
            "id": student.id,
            "name": student.name,
            "email": student.email,
            "api_key_hash": student.api_key_hash,
            "created_at": student.created_at,
            "current_week_quota": student.current_week_quota,
            "used_quota": student.used_quota,
            "provider_api_key_encrypted": student.provider_api_key_encrypted,
            "provider_type": student.provider_type,
        }

    return student_dict, api_key


def update_student_quota(student_id: str, new_quota: int) -> bool:
    """更新学生配额"""
    with get_db_session() as session:
        student = session.query(Student).filter(Student.id == student_id).first()
        if not student:
            return False
        student.current_week_quota = new_quota
        return True


def reset_student_quota(student_id: str) -> bool:
    """重置学生已使用配额（用于新周期）"""
    with get_db_session() as session:
        student = session.query(Student).filter(Student.id == student_id).first()
        if not student:
            return False
        student.used_quota = 0
        return True


def regenerate_student_api_key(student_id: str) -> Optional[str]:
    """
    重新生成学生 API Key

    Returns:
        新的 API Key 或 None（如果学生不存在）
    """
    from gateway.app.core.security import hash_api_key, generate_api_key

    new_key = generate_api_key()
    new_hash = hash_api_key(new_key)

    with get_db_session() as session:
        student = session.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None
        student.api_key_hash = new_hash
        return new_key


def delete_student(student_id: str) -> bool:
    """删除学生"""
    with get_db_session() as session:
        student = session.query(Student).filter(Student.id == student_id).first()
        if not student:
            return False
        session.delete(student)
        return True


# ==================== 对话记录 ====================


def get_conversations(
    limit: int = 100,
    offset: int = 0,
    student_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """获取对话记录，支持筛选，返回字典列表"""
    with get_db_session() as session:
        query = session.query(Conversation)

        # 应用筛选条件
        if student_id:
            query = query.filter(Conversation.student_id == student_id)
        if action:
            query = query.filter(Conversation.action_taken == action)
        if start_date:
            query = query.filter(Conversation.timestamp >= start_date)
        if end_date:
            query = query.filter(Conversation.timestamp <= end_date)

        conversations = (
            query.order_by(desc(Conversation.timestamp))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": c.id,
                "student_id": c.student_id,
                "timestamp": c.timestamp,
                "prompt_text": c.prompt_text,
                "response_text": c.response_text,
                "tokens_used": c.tokens_used,
                "rule_triggered": c.rule_triggered,
                "action_taken": c.action_taken,
                "week_number": c.week_number,
                "model": getattr(c, "model", None),
            }
            for c in conversations
        ]


def get_conversation_count(
    student_id: Optional[str] = None, action: Optional[str] = None
) -> int:
    """获取对话记录总数"""
    with get_db_session() as session:
        query = session.query(func.count(Conversation.id))

        if student_id:
            query = query.filter(Conversation.student_id == student_id)
        if action:
            query = query.filter(Conversation.action_taken == action)

        return query.scalar() or 0


def get_conversation_by_id(conversation_id: int) -> Optional[Conversation]:
    """根据 ID 获取单条对话"""
    with get_db_session() as session:
        return (
            session.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )


def get_conversations_by_student(
    student_id: str, limit: int = 100, offset: int = 0
) -> List[Dict[str, Any]]:
    """获取指定学生的所有对话记录"""
    with get_db_session() as session:
        conversations = (
            session.query(Conversation)
            .filter(Conversation.student_id == student_id)
            .order_by(desc(Conversation.timestamp))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": c.id,
                "student_id": c.student_id,
                "timestamp": c.timestamp,
                "prompt_text": c.prompt_text,
                "response_text": c.response_text,
                "tokens_used": c.tokens_used,
                "rule_triggered": c.rule_triggered,
                "action_taken": c.action_taken,
                "week_number": c.week_number,
                "model": getattr(c, "model", None),
            }
            for c in conversations
        ]


def search_conversations(
    query: str,
    limit: int = 50,
    offset: int = 0,
    student_id: Optional[str] = None,
    action: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """搜索对话内容（prompt 或 response）"""
    with get_db_session() as session:
        # 构建基础查询
        db_query = session.query(Conversation).filter(
            Conversation.prompt_text.ilike(f"%{query}%")
            | Conversation.response_text.ilike(f"%{query}%")
        )

        # 应用额外筛选
        if student_id:
            db_query = db_query.filter(Conversation.student_id == student_id)
        if action:
            db_query = db_query.filter(Conversation.action_taken == action)

        conversations = (
            db_query.order_by(desc(Conversation.timestamp))
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": c.id,
                "student_id": c.student_id,
                "timestamp": c.timestamp,
                "prompt_text": c.prompt_text,
                "response_text": c.response_text,
                "tokens_used": c.tokens_used,
                "rule_triggered": c.rule_triggered,
                "action_taken": c.action_taken,
                "week_number": c.week_number,
                "model": getattr(c, "model", None),
            }
            for c in conversations
        ]


# ==================== 规则管理 ====================


def get_all_rules() -> List[Dict[str, Any]]:
    """获取所有规则，返回字典列表"""
    with get_db_session() as session:
        rules = session.query(Rule).order_by(Rule.id.desc()).all()
        return [
            {
                "id": r.id,
                "pattern": r.pattern,
                "rule_type": r.rule_type,
                "message": r.message,
                "active_weeks": r.active_weeks,
                "enabled": r.enabled,
            }
            for r in rules
        ]


def get_rule_by_id(rule_id: int) -> Optional[Rule]:
    """根据 ID 获取规则"""
    with get_db_session() as session:
        return session.query(Rule).filter(Rule.id == rule_id).first()


def create_rule(
    pattern: str,
    rule_type: str,
    message: str,
    active_weeks: str = "1-16",
    enabled: bool = True,
) -> Dict[str, Any]:
    """创建新规则，返回字典"""
    rule = Rule(
        pattern=pattern,
        rule_type=rule_type,
        message=message,
        active_weeks=active_weeks,
        enabled=enabled,
    )

    with get_db_session() as session:
        session.add(rule)
        session.flush()
        session.refresh(rule)
        # 返回字典以避免 session 关闭后的访问问题
        return {
            "id": rule.id,
            "pattern": rule.pattern,
            "rule_type": rule.rule_type,
            "message": rule.message,
            "active_weeks": rule.active_weeks,
            "enabled": rule.enabled,
        }


def update_rule(
    rule_id: int,
    pattern: Optional[str] = None,
    rule_type: Optional[str] = None,
    message: Optional[str] = None,
    active_weeks: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> bool:
    """更新规则"""
    with get_db_session() as session:
        rule = session.query(Rule).filter(Rule.id == rule_id).first()
        if not rule:
            return False

        if pattern is not None:
            rule.pattern = pattern
        if rule_type is not None:
            rule.rule_type = rule_type
        if message is not None:
            rule.message = message
        if active_weeks is not None:
            rule.active_weeks = active_weeks
        if enabled is not None:
            rule.enabled = enabled

        return True


def delete_rule(rule_id: int) -> bool:
    """删除规则"""
    with get_db_session() as session:
        rule = session.query(Rule).filter(Rule.id == rule_id).first()
        if not rule:
            return False
        session.delete(rule)
        return True


def toggle_rule_enabled(rule_id: int) -> Optional[bool]:
    """切换规则启用状态"""
    with get_db_session() as session:
        rule = session.query(Rule).filter(Rule.id == rule_id).first()
        if not rule:
            return None
        rule.enabled = not rule.enabled
        return rule.enabled


# ==================== 每周提示词管理 ====================


def get_all_weekly_prompts() -> List[Dict[str, Any]]:
    """获取所有每周提示词，返回字典列表"""
    with get_db_session() as session:
        prompts = (
            session.query(WeeklySystemPrompt)
            .order_by(WeeklySystemPrompt.week_start)
            .all()
        )
        return [
            {
                "id": p.id,
                "week_start": p.week_start,
                "week_end": p.week_end,
                "system_prompt": p.system_prompt,
                "description": p.description,
                "is_active": p.is_active,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in prompts
        ]


def get_prompt_by_week(week_number: int) -> Optional[Dict[str, Any]]:
    """根据周次获取提示词（查找包含该周次范围的配置），返回字典"""
    with get_db_session() as session:
        prompt = (
            session.query(WeeklySystemPrompt)
            .filter(
                and_(
                    WeeklySystemPrompt.week_start <= week_number,
                    WeeklySystemPrompt.week_end >= week_number,
                )
            )
            .first()
        )
        if prompt:
            return {
                "id": prompt.id,
                "week_start": prompt.week_start,
                "week_end": prompt.week_end,
                "system_prompt": prompt.system_prompt,
                "description": prompt.description,
                "is_active": prompt.is_active,
                "created_at": prompt.created_at,
                "updated_at": prompt.updated_at,
            }
        return None


def get_current_week_prompt() -> Optional[Dict[str, Any]]:
    """获取当前周的提示词，返回字典"""
    current_week = get_current_week_number()
    return get_prompt_by_week(current_week)


def create_or_update_weekly_prompt(
    week_start: int,
    week_end: int,
    system_prompt: str,
    description: Optional[str] = None,
    is_active: bool = True,
) -> Dict[str, Any]:
    """创建或更新每周提示词，返回字典"""
    with get_db_session() as session:
        # 查找是否存在包含该范围的配置
        prompt = (
            session.query(WeeklySystemPrompt)
            .filter(
                and_(
                    WeeklySystemPrompt.week_start == week_start,
                    WeeklySystemPrompt.week_end == week_end,
                )
            )
            .first()
        )

        now = datetime.now()
        if prompt:
            # 更新
            prompt.system_prompt = system_prompt
            prompt.description = description
            prompt.is_active = is_active
            prompt.updated_at = now
        else:
            # 创建
            prompt = WeeklySystemPrompt(
                week_start=week_start,
                week_end=week_end,
                system_prompt=system_prompt,
                description=description,
                is_active=is_active,
            )
            session.add(prompt)

        session.flush()
        session.refresh(prompt)
        # 返回字典以避免 session 关闭后的访问问题
        return {
            "id": prompt.id,
            "week_start": prompt.week_start,
            "week_end": prompt.week_end,
            "system_prompt": prompt.system_prompt,
            "description": prompt.description,
            "is_active": prompt.is_active,
            "created_at": prompt.created_at,
            "updated_at": prompt.updated_at,
        }


def delete_weekly_prompt(prompt_id: int) -> bool:
    """删除每周提示词"""
    with get_db_session() as session:
        prompt = (
            session.query(WeeklySystemPrompt)
            .filter(WeeklySystemPrompt.id == prompt_id)
            .first()
        )
        if not prompt:
            return False
        session.delete(prompt)
        session.flush()
        return True


# ==================== 配额日志 ====================


def get_quota_logs(
    student_id: Optional[str] = None,
    week_number: Optional[int] = None,
    limit: int = 100,
) -> List[QuotaLog]:
    """获取配额日志"""
    with get_db_session() as session:
        query = session.query(QuotaLog)

        if student_id:
            query = query.filter(QuotaLog.student_id == student_id)
        if week_number:
            query = query.filter(QuotaLog.week_number == week_number)

        return query.order_by(desc(QuotaLog.created_at)).limit(limit).all()


def get_student_quota_stats(student_id: str) -> Dict[str, Any]:
    """获取学生配额统计"""
    with get_db_session() as session:
        student = session.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        current_week = get_current_week_number()

        # 本周使用
        week_usage = (
            session.query(func.sum(QuotaLog.tokens_used))
            .filter(
                and_(
                    QuotaLog.student_id == student_id,
                    QuotaLog.week_number == current_week,
                )
            )
            .scalar()
            or 0
        )

        # 历史总计
        total_usage = (
            session.query(func.sum(QuotaLog.tokens_used))
            .filter(QuotaLog.student_id == student_id)
            .scalar()
            or 0
        )

        return {
            "student_id": student_id,
            "name": student.name,
            "current_week": current_week,
            "week_quota": student.current_week_quota,
            "week_used": student.used_quota,
            "week_remaining": max(0, student.current_week_quota - student.used_quota),
            "week_usage_from_logs": int(week_usage),
            "total_usage_from_logs": int(total_usage),
        }
