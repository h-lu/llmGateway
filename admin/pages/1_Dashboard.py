import streamlit as st
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.header("📊 仪表盘")

try:
    from admin.db_utils import get_dashboard_stats
    
    stats = get_dashboard_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("👥 学生总数", stats["students"])
    with col2:
        st.metric("💬 对话总数", stats["conversations"])
    with col3:
        st.metric("⚙️ 规则数量", stats["rules"])
    
    col4, col5 = st.columns(2)
    with col4:
        st.metric("🚫 阻断次数", stats["blocked"])
    with col5:
        st.metric("🔢 总Token使用", f"{stats['total_tokens']:,}")
    
    st.divider()
    st.subheader("📌 快速操作")
    
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("👥 管理学生", use_container_width=True):
            st.switch_page("pages/2_Students.py")
    with col_b:
        if st.button("💬 查看对话", use_container_width=True):
            st.switch_page("pages/3_Conversations.py")
    with col_c:
        if st.button("⚙️ 配置规则", use_container_width=True):
            st.switch_page("pages/4_Rules.py")
            
except ImportError as e:
    st.warning(f"数据库模块加载失败: {e}")
    st.info("请确保在项目根目录运行 streamlit")
except Exception as e:
    st.error(f"获取统计信息失败: {e}")
    st.info("数据库可能还没有数据，这是正常的初始状态")
