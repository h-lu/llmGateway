"""
TeachProxy 教师管理面板 v2.0
现代化的 Streamlit 管理界面
"""
import streamlit as st
import sys
from pathlib import Path

# 设置页面配置（必须是第一个 Streamlit 命令）
st.set_page_config(
    page_title="TeachProxy 管理面板",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# 自定义 CSS 样式
st.markdown("""
<style>
    /* 全局样式 */
    .main {
        padding: 0rem 1rem;
    }
    
    /* 卡片样式 */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .metric-card-secondary {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    .metric-card-success {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        padding: 1.5rem;
        border-radius: 1rem;
        color: white;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    
    /* 侧边栏样式 */
    .css-1d391kg {
        padding-top: 1rem;
    }
    
    /* 标题样式 */
    h1 {
        color: #1f2937;
        font-weight: 700;
    }
    
    h2 {
        color: #374151;
        font-weight: 600;
    }
    
    h3 {
        color: #4b5563;
        font-weight: 600;
    }
    
    /* 按钮样式 */
    .stButton > button {
        border-radius: 0.5rem;
        font-weight: 500;
    }
    
    /* 表格样式 */
    .dataframe {
        font-size: 0.9rem;
    }
    
    /* 状态标签 */
    .status-active {
        background-color: #10b981;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    .status-inactive {
        background-color: #ef4444;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    
    /* 信息框 */
    .info-box {
        background-color: #eff6ff;
        border-left: 4px solid #3b82f6;
        padding: 1rem;
        border-radius: 0 0.5rem 0.5rem 0;
    }
    
    .warning-box {
        background-color: #fffbeb;
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        border-radius: 0 0.5rem 0.5rem 0;
    }
    
    .success-box {
        background-color: #ecfdf5;
        border-left: 4px solid #10b981;
        padding: 1rem;
        border-radius: 0 0.5rem 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# 检查管理员认证
def check_auth():
    """检查管理员是否已登录"""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        show_login()
        return False
    return True

def show_login():
    """显示登录界面"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 3rem 0;">
            <h1>🎓 TeachProxy</h1>
            <h3>教师管理面板</h3>
        </div>
        """, unsafe_allow_html=True)
        
        with st.container():
            st.markdown("<div class='info-box'>请输入管理员令牌继续</div>", unsafe_allow_html=True)
            
            admin_token = st.text_input(
                "管理员令牌",
                type="password",
                placeholder="输入您的管理员令牌",
                help="令牌在环境变量 ADMIN_TOKEN 中设置"
            )
            
            if st.button("🔐 登录", use_container_width=True, type="primary"):
                import os
                expected_token = os.getenv("ADMIN_TOKEN", "")
                
                if not expected_token:
                    st.error("⚠️ 系统未配置 ADMIN_TOKEN，请在 .env 文件中设置")
                elif admin_token == expected_token:
                    st.session_state.admin_authenticated = True
                    st.success("✅ 登录成功！")
                    st.rerun()
                else:
                    st.error("❌ 无效的令牌")

def show_sidebar():
    """显示侧边栏导航"""
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h2>🎓 TeachProxy</h2>
            <p style="color: #6b7280; font-size: 0.875rem;">AI 教学代理网关</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # 导航菜单
        st.markdown("### 📋 功能菜单")
        
        pages = {
            "📊 仪表板": "pages/dashboard",
            "👥 学生管理": "pages/students",
            "💬 对话记录": "pages/conversations", 
            "⚙️ 规则配置": "pages/rules",
            "📝 每周提示词": "pages/weekly_prompts",
            "🔧 系统设置": "pages/settings",
        }
        
        for label, page in pages.items():
            if st.button(label, use_container_width=True, key=f"nav_{page}"):
                st.switch_page(f"{page}.py")
        
        st.divider()
        
        # 系统状态
        st.markdown("### 📡 系统状态")
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                if health.get("status") == "ok":
                    st.success("🟢 网关运行正常")
                else:
                    st.warning("🟡 网关运行降级")
            else:
                st.error("🔴 网关未响应")
        except Exception:
            st.error("🔴 网关未启动")
        
        st.divider()
        
        # 登出按钮
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()
        
        # 版本信息
        st.markdown("""
        <div style="text-align: center; padding-top: 2rem; color: #9ca3af; font-size: 0.75rem;">
            TeachProxy v2.0<br>
            Made with ❤️ for Education
        </div>
        """, unsafe_allow_html=True)

def main():
    """主函数"""
    # 检查认证
    if not check_auth():
        return
    
    # 显示侧边栏
    show_sidebar()
    
    # 显示欢迎页面
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem;">
        <h1>👋 欢迎使用 TeachProxy 管理面板</h1>
        <p style="font-size: 1.25rem; color: #6b7280; margin-top: 1rem;">
            请选择左侧菜单开始管理您的 AI 教学网关
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # 快捷入口卡片
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style="background: #eff6ff; padding: 2rem; border-radius: 1rem; text-align: center;">
            <h2>👥</h2>
            <h4>学生管理</h4>
            <p style="color: #6b7280;">添加、编辑学生账号<br>管理 API 密钥和配额</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("进入学生管理", key="goto_students"):
            st.switch_page("pages/students.py")
    
    with col2:
        st.markdown("""
        <div style="background: #f0fdf4; padding: 2rem; border-radius: 1rem; text-align: center;">
            <h2>💬</h2>
            <h4>对话记录</h4>
            <p style="color: #6b7280;">查看学生对话历史<br>监控内容过滤情况</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("查看对话记录", key="goto_conversations"):
            st.switch_page("pages/conversations.py")
    
    with col3:
        st.markdown("""
        <div style="background: #fef3c7; padding: 2rem; border-radius: 1rem; text-align: center;">
            <h2>⚙️</h2>
            <h4>规则配置</h4>
            <p style="color: #6b7280;">配置内容过滤规则<br>设置学习引导策略</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("配置规则", key="goto_rules"):
            st.switch_page("pages/rules.py")
    
    # 快速统计
    st.divider()
    st.subheader("📈 快速概览")
    
    try:
        from admin.db_utils_v2 import get_dashboard_stats
        stats = get_dashboard_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="👥 学生总数",
                value=stats["students"],
                delta=None
            )
        
        with col2:
            st.metric(
                label="💬 今日对话",
                value=stats["conversations_today"],
                delta=None
            )
        
        with col3:
            st.metric(
                label="🔢 Token 使用",
                value=f"{stats['tokens_today']:,}",
                delta=None
            )
        
        with col4:
            quota_usage = stats.get("quota_usage_rate", 0)
            st.metric(
                label="📊 配额使用率",
                value=f"{quota_usage:.1f}%",
                delta=None
            )
            
    except Exception as e:
        st.info("📊 统计数据加载中..." if "No module named" in str(e) else f"加载统计失败: {e}")

if __name__ == "__main__":
    main()
