"""
TeachProxy Admin - 系统设置页面
"""
import streamlit as st
import sys
from pathlib import Path
import os

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="系统设置 - TeachProxy Admin",
    page_icon="🔧",
    layout="wide"
)

st.title("🔧 系统设置")

# 检查认证
if "admin_authenticated" not in st.session_state or not st.session_state.admin_authenticated:
    st.warning("⚠️ 请先登录")
    st.stop()

# 加载配置
try:
    from gateway.app.core.config import settings
    
    # ========== 提供商配置 ==========
    st.markdown("### 🤖 AI 提供商配置")
    
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### DeepSeek")
            st.text_input(
                "API Key",
                value="*" * 20 if settings.deepseek_api_key else "",
                disabled=True,
                type="password"
            )
            st.text_input(
                "Base URL",
                value=settings.deepseek_base_url,
                disabled=True
            )
            st.text_input(
                "超时时间",
                value=f"{settings.deepseek_direct_timeout}s",
                disabled=True
            )
            
            # 测试连接
            if st.button("🔄 测试 DeepSeek 连接"):
                try:
                    import requests
                    headers = {"Authorization": f"Bearer {settings.deepseek_api_key}"}
                    response = requests.get(
                        f"{settings.deepseek_base_url}/models",
                        headers=headers,
                        timeout=10
                    )
                    if response.status_code == 200:
                        st.success("✅ DeepSeek 连接正常")
                        models = response.json().get("data", [])
                        st.caption(f"可用模型: {len(models)} 个")
                    else:
                        st.error(f"❌ 连接失败: HTTP {response.status_code}")
                except Exception as e:
                    st.error(f"❌ 连接失败: {e}")
        
        with col2:
            st.markdown("#### OpenAI (备用)")
            openai_key_set = bool(settings.openai_api_key)
            st.text_input(
                "API Key",
                value="*" * 20 if openai_key_set else "未配置",
                disabled=True,
                type="password"
            )
            st.text_input(
                "Base URL",
                value=settings.openai_base_url,
                disabled=True
            )
            
            if openai_key_set:
                if st.button("🔄 测试 OpenAI 连接"):
                    try:
                        import requests
                        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
                        if settings.openai_organization:
                            headers["OpenAI-Organization"] = settings.openai_organization
                        response = requests.get(
                            f"{settings.openai_base_url}/models",
                            headers=headers,
                            timeout=10
                        )
                        if response.status_code == 200:
                            st.success("✅ OpenAI 连接正常")
                        else:
                            st.error(f"❌ 连接失败: HTTP {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ 连接失败: {e}")
            else:
                st.info("ℹ️ OpenAI 未配置")
    
    st.divider()
    
    # ========== 限流和配额配置 ==========
    st.markdown("### ⏱️ 限流和配额配置")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="每分钟请求限制",
            value=f"{settings.rate_limit_requests_per_minute} req/min"
        )
        st.metric(
            label="突发流量限制",
            value=f"{settings.rate_limit_burst_size}"
        )
    
    with col2:
        st.metric(
            label="流式请求并发限制",
            value=f"{settings.request_router_streaming_limit}"
        )
        st.metric(
            label="普通请求并发限制",
            value=f"{settings.request_router_normal_limit}"
        )
    
    with col3:
        st.metric(
            label="请求超时时间",
            value=f"{settings.request_router_timeout}s"
        )
        st.metric(
            label="HTTP 超时",
            value=f"{settings.httpx_timeout}s"
        )
    
    st.caption("⚠️ 修改这些配置需要重启服务")
    
    st.divider()
    
    # ========== 数据库和缓存 ==========
    st.markdown("### 💾 数据库和缓存")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 数据库")
        db_url = settings.database_url
        # 隐藏密码
        if "@" in db_url:
            db_display = db_url.split("@")[0].split(":")[0] + "://***@" + db_url.split("@")[1]
        else:
            db_display = db_url
        
        st.text_input(
            "数据库 URL",
            value=db_display,
            disabled=True
        )
        st.text_input(
            "连接池大小",
            value=str(settings.db_pool_size),
            disabled=True
        )
        
        # 数据库连接测试
        if st.button("🔄 测试数据库连接"):
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(settings.database_url.replace("+aiosqlite", "+pysqlite").replace("+asyncpg", ""))
                with engine.connect() as conn:
                    result = conn.execute(text("SELECT 1"))
                    st.success("✅ 数据库连接正常")
            except Exception as e:
                st.error(f"❌ 数据库连接失败: {e}")
    
    with col2:
        st.markdown("#### 缓存")
        st.toggle(
            "内存缓存",
            value=settings.cache_enabled,
            disabled=True
        )
        st.toggle(
            "Redis 缓存",
            value=settings.redis_enabled,
            disabled=True
        )
        if settings.redis_enabled:
            st.text_input(
                "Redis URL",
                value=settings.redis_url,
                disabled=True
            )
    
    st.divider()
    
    # ========== 日志配置 ==========
    st.markdown("### 📝 日志配置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.selectbox(
            "日志级别",
            options=["DEBUG", "INFO", "WARNING", "ERROR"],
            index=["DEBUG", "INFO", "WARNING", "ERROR"].index(settings.log_level),
            disabled=True
        )
    
    with col2:
        st.selectbox(
            "日志格式",
            options=["text", "structured", "json"],
            index=["text", "structured", "json"].index(settings.log_format),
            disabled=True
        )
    
    st.divider()
    
    # ========== 系统状态监控 ==========
    st.markdown("### 📊 系统状态监控")
    
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            
            st.success("🟢 网关运行中")
            
            with st.expander("查看详细状态", expanded=True):
                st.json(health)
        else:
            st.error(f"🔴 网关异常: HTTP {response.status_code}")
    except Exception as e:
        st.error(f"🔴 无法连接网关: {e}")
    
    st.divider()
    
    # ========== 重启服务 ==========
    st.markdown("### 🔄 服务管理")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 重启网关服务")
        st.warning("⚠️ 重启服务会中断正在进行的请求")
        
        if st.button("🔄 重启服务", type="primary", use_container_width=True):
            st.info("执行重启命令...")
            # 这里可以添加重启逻辑
            st.code("""
pkill -f "uvicorn gateway.app.main"
uv run uvicorn gateway.app.main:app --host 0.0.0.0 --port 8000
            """, language="bash")
    
    with col2:
        st.markdown("#### 清理缓存")
        st.info("清理内存和 Redis 缓存")
        
        if st.button("🧹 清理缓存", type="secondary", use_container_width=True):
            try:
                from gateway.app.core.cache import get_cache
                cache = get_cache()
                if hasattr(cache, 'clear'):
                    cache.clear()
                    st.success("✅ 缓存已清理")
                else:
                    st.info("缓存接口不支持清理操作")
            except Exception as e:
                st.error(f"清理失败: {e}")
    
    st.divider()
    
    # ========== 配置说明 ==========
    with st.expander("📖 配置文件位置", expanded=False):
        st.markdown(f"""
        **当前配置文件:** `{project_root}/.env`
        
        **生产环境配置:** `{project_root}/.env.production`
        
        **配置项说明:**
        - `DEEPSEEK_API_KEY` - DeepSeek API 密钥
        - `TEACHER_DEEPSEEK_API_KEY` - 教师池 DeepSeek 密钥
        - `DATABASE_URL` - 数据库连接字符串
        - `REDIS_ENABLED` - 是否启用 Redis 缓存
        - `RATE_LIMIT_REQUESTS_PER_MINUTE` - 每分钟请求限制
        - `REQUEST_ROUTER_STREAMING_LIMIT` - 流式请求并发限制
        - `LOG_LEVEL` - 日志级别 (DEBUG/INFO/WARNING/ERROR)
        - `LOG_FORMAT` - 日志格式 (text/structured/json)
        """)

except ImportError as e:
    st.error(f"模块加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
except Exception as e:
    st.error(f"加载设置失败: {e}")
    import traceback
    st.code(traceback.format_exc())
