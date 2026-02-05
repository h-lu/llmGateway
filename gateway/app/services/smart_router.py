"""Smart router for LLM provider selection."""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from gateway.app.core.config import settings
from gateway.app.db.models import Student
from gateway.app.exceptions import QuotaExceededWithGuidanceError

logger = logging.getLogger(__name__)


class KeyType(Enum):
    """API Key 类型"""

    TEACHER_DEEPSEEK = "teacher_deepseek"
    TEACHER_OPENROUTER = "teacher_openrouter"
    STUDENT = "student"


@dataclass
class RoutingDecision:
    """路由决策结果"""

    key_type: KeyType
    provider_name: str
    api_key: str
    base_url: str
    model: str
    timeout: float
    fallback_models: list[str] | None = None
    cost_per_1m_tokens: tuple[float, float] = (0.0, 0.0)  # (input, output)


def get_current_week_number() -> int:
    """获取当前周数（基于学期开始日期）"""
    if not settings.semester_start_date:
        # Fallback: use ISO week number
        return datetime.now().isocalendar()[1]

    from datetime import date

    today = date.today()
    start = settings.semester_start_date

    if today < start:
        return 1

    days_diff = (today - start).days
    week = (days_diff // 7) + 1

    return min(week, settings.semester_weeks)


class SmartRouter:
    """智能路由器。

    路由优先级：
    1. 学生自己的 Key（如果配置了）
    2. 教师 DeepSeek（如果有配额）
    3. 配额用完 → 异常（引导配置 Key）

    Mock 模式：当 TEACHPROXY_MOCK_PROVIDER=true 时，绕过真实 API 调用
    """

    def __init__(self):
        self.config = settings
        self._is_mock_mode = os.getenv("TEACHPROXY_MOCK_PROVIDER", "").lower() == "true"

    async def route(
        self,
        student: Student,
        requested_model: str,
    ) -> RoutingDecision:
        """路由决策。"""
        logger.debug(f"Routing for student {student.id}, model {requested_model}")

        # Mock 模式：返回模拟的路由决策
        if self._is_mock_mode:
            logger.info(f"Mock mode: using mock routing decision for {student.id}")
            return RoutingDecision(
                key_type=KeyType.TEACHER_DEEPSEEK,
                provider_name="mock",
                api_key="mock-key",
                base_url="http://mock.provider",
                model=requested_model or "deepseek-chat",
                timeout=30.0,
                cost_per_1m_tokens=(0.0, 0.0),
            )

        # 1. 检查学生是否有自己的 Key
        if student.has_own_provider_key:
            logger.info(f"Using student's own key for {student.id}")
            return self._use_student_key(student, requested_model)

        # 2. 检查配额
        has_quota = await self._check_quota(student)
        if has_quota:
            logger.info(f"Using teacher key for {student.id}")
            return self._use_teacher_deepseek(requested_model)

        # 3. 配额用完
        logger.warning(f"Quota exceeded for student {student.id}")
        current_week = get_current_week_number()
        raise QuotaExceededWithGuidanceError(
            student_id=student.id,
            remaining=0,
            reset_week=current_week + 1,
            message="本周配额已用完。您可以选择：\n"
            "1. 在设置中配置自己的 DeepSeek API Key（推荐，费用低）\n"
            "2. 等待下周配额重置\n"
            "3. 联系教师申请额外配额",
        )

    def _use_student_key(
        self, student: Student, requested_model: str
    ) -> RoutingDecision:
        """使用学生自己的 Key"""
        api_key = student.get_provider_api_key()

        if not api_key:
            raise ValueError(
                f"Student {student.id} has_own_provider_key=True but key is None"
            )

        if student.provider_type == "deepseek":
            return RoutingDecision(
                key_type=KeyType.STUDENT,
                provider_name="deepseek",
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
                model=requested_model or "deepseek-chat",
                timeout=30.0,
                cost_per_1m_tokens=(0.55, 2.19),
            )
        elif student.provider_type == "openrouter":
            return RoutingDecision(
                key_type=KeyType.STUDENT,
                provider_name="openrouter",
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                model=f"deepseek/{requested_model or 'deepseek-chat'}",
                timeout=30.0,
                fallback_models=[
                    "openai/gpt-4o-mini",
                    "anthropic/claude-3-haiku",
                ],
                cost_per_1m_tokens=(0.58, 2.31),  # +5.5%
            )
        else:
            raise ValueError(f"Unknown provider type: {student.provider_type}")

    def _use_teacher_deepseek(self, requested_model: str) -> RoutingDecision:
        """使用教师 DeepSeek Key"""
        if not self.config.teacher_deepseek_api_key:
            raise ValueError("Teacher DeepSeek API key not configured")

        return RoutingDecision(
            key_type=KeyType.TEACHER_DEEPSEEK,
            provider_name="deepseek",
            api_key=self.config.teacher_deepseek_api_key,
            base_url=self.config.teacher_deepseek_base_url,
            model=requested_model or "deepseek-chat",
            timeout=self.config.deepseek_direct_timeout,  # 15s
            cost_per_1m_tokens=(0.55, 2.19),
        )

    def _use_teacher_openrouter(self, requested_model: str) -> RoutingDecision:
        """使用教师 OpenRouter Key（故障转移用）"""
        if not self.config.teacher_openrouter_api_key:
            raise ValueError("Teacher OpenRouter API key not configured")

        return RoutingDecision(
            key_type=KeyType.TEACHER_OPENROUTER,
            provider_name="openrouter",
            api_key=self.config.teacher_openrouter_api_key,
            base_url=self.config.teacher_openrouter_base_url,
            model=f"deepseek/{requested_model or 'deepseek-chat'}",
            timeout=self.config.openrouter_timeout,  # 30s
            fallback_models=self.config.openrouter_fallback_models,
            cost_per_1m_tokens=(0.58, 2.31),
        )

    async def _check_quota(self, student: Student) -> bool:
        """检查学生是否还有剩余配额"""
        # 延迟导入避免循环依赖 (遵循 FastAPI 最佳实践)
        from gateway.app.services.quota_cache import get_quota_cache_service

        try:
            quota_service = get_quota_cache_service()
            week_number = get_current_week_number()

            state = await quota_service.get_quota_state(student.id, week_number)
            if state:
                return state.remaining > 0
        except Exception as e:
            logger.warning(f"Failed to check quota from cache: {e}")

        # Fallback to direct calculation
        return student.current_week_quota > student.used_quota
