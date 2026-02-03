"""
TeachProxy Admin - 对话记录页面
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="对话记录 - TeachProxy Admin",
    page_icon="💬",
    layout="wide"
)

st.title("💬 对话记录")

# 检查认证
if "admin_authenticated" not in st.session_state or not st.session_state.admin_authenticated:
    st.warning("⚠️ 请先登录")
    st.stop()

try:
    from admin.db_utils_v2 import get_conversations, get_conversation_count, get_all_students
    
    # ========== 筛选器 ==========
    st.markdown("### 🔍 筛选条件")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # 加载学生列表用于筛选
        students = get_all_students()
        student_options = {"全部": None}
        for s in students:
            student_options[f"{s.name} ({s.email})"] = s.id
        
        selected_student = st.selectbox("👤 学生", options=list(student_options.keys()))
        student_id = student_options[selected_student]
    
    with col2:
        action_filter = st.selectbox(
            "🏷️ 操作类型",
            ["全部", "blocked", "guided", "passed"]
        )
        action = None if action_filter == "全部" else action_filter
    
    with col3:
        date_range = st.selectbox(
            "📅 时间范围",
            ["全部", "今天", "最近7天", "最近30天", "自定义"]
        )
    
    with col4:
        items_per_page = st.selectbox("📄 每页显示", [10, 20, 50, 100], index=2)
    
    # 日期范围处理
    start_date = None
    end_date = None
    
    if date_range == "今天":
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = datetime.now()
    elif date_range == "最近7天":
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
    elif date_range == "最近30天":
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
    elif date_range == "自定义":
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("开始日期", value=datetime.now() - timedelta(days=7))
            start_date = datetime.combine(start_date, datetime.min.time())
        with col_end:
            end_date = st.date_input("结束日期", value=datetime.now())
            end_date = datetime.combine(end_date, datetime.max.time())
    
    st.divider()
    
    # ========== 统计数据 ==========
    total_count = get_conversation_count(student_id=student_id, action=action)
    
    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    
    with col_stat1:
        st.metric("📊 总计记录", total_count)
    with col_stat2:
        blocked_count = get_conversation_count(student_id=student_id, action="blocked")
        st.metric("🚫 阻断次数", blocked_count)
    with col_stat3:
        guided_count = get_conversation_count(student_id=student_id, action="guided")
        st.metric("💡 引导次数", guided_count)
    with col_stat4:
        passed_count = get_conversation_count(student_id=student_id, action="passed")
        st.metric("✅ 通过次数", passed_count)
    
    st.divider()
    
    # ========== 分页 ==========
    total_pages = (total_count + items_per_page - 1) // items_per_page
    if total_pages == 0:
        total_pages = 1
    
    col_page1, col_page2, col_page3 = st.columns([1, 2, 1])
    with col_page2:
        current_page = st.number_input(
            f"页码 (共 {total_pages} 页)",
            min_value=1,
            max_value=total_pages,
            value=1
        )
    
    offset = (current_page - 1) * items_per_page
    
    # ========== 加载对话数据 ==========
    conversations = get_conversations(
        limit=items_per_page,
        offset=offset,
        student_id=student_id,
        action=action,
        start_date=start_date,
        end_date=end_date
    )
    
    if not conversations:
        st.info("📭 没有找到符合条件的对话记录")
    else:
        st.caption(f"显示 {len(conversations)} 条记录 (第 {current_page}/{total_pages} 页)")
        
        # ========== 对话列表 ==========
        for conv in conversations:
            # 获取学生信息
            student_name = "未知"
            student_email = ""
            for s in students:
                if s.id == conv.student_id:
                    student_name = s.name
                    student_email = s.email
                    break
            
            # 根据操作类型设置颜色
            if conv.action_taken == "blocked":
                border_color = "#ef4444"
                bg_color = "#fef2f2"
                icon = "🚫"
            elif conv.action_taken == "guided":
                border_color = "#f59e0b"
                bg_color = "#fffbeb"
                icon = "💡"
            else:
                border_color = "#10b981"
                bg_color = "#f0fdf4"
                icon = "✅"
            
            with st.container():
                st.markdown(f"""
                <div style="
                    background-color: {bg_color};
                    border-left: 4px solid {border_color};
                    padding: 1rem;
                    margin: 0.5rem 0;
                    border-radius: 0 0.5rem 0.5rem 0;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-size: 1.25rem;">{icon}</span>
                            <strong>{student_name}</strong>
                            <span style="color: #6b7280; font-size: 0.875rem;">({student_email})</span>
                        </div>
                        <div style="color: #6b7280; font-size: 0.875rem;">
                            {conv.timestamp.strftime("%Y-%m-%d %H:%M:%S") if conv.timestamp else "-"}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 展开查看详情
                with st.expander("查看详情"):
                    col_detail1, col_detail2 = st.columns([2, 1])
                    
                    with col_detail1:
                        st.markdown("**📝 提问内容**")
                        st.text_area(
                            "Prompt",
                            value=conv.prompt_text or "(无内容)",
                            height=100,
                            disabled=True,
                            key=f"prompt_{conv.id}"
                        )
                        
                        st.markdown("**💬 回复内容**")
                        st.text_area(
                            "Response",
                            value=conv.response_text or "(无内容)",
                            height=150,
                            disabled=True,
                            key=f"response_{conv.id}"
                        )
                    
                    with col_detail2:
                        st.markdown("**📊 元数据**")
                        st.write(f"操作: `{conv.action_taken}`")
                        st.write(f"规则: `{conv.rule_triggered or '无'}`")
                        st.write(f"Tokens: `{conv.tokens_used or 0}`")
                        st.write(f"周次: `{conv.week_number}`")
                        if conv.model:
                            st.write(f"模型: `{conv.model}`")
                        
                        # 复制功能
                        st.divider()
                        if st.button("📋 复制提问", key=f"copy_{conv.id}"):
                            st.write("已复制到剪贴板!")
                            # 使用 JS 复制
                            st.markdown(f"""
                            <script>
                                navigator.clipboard.writeText(`{conv.prompt_text or ''}`);
                            </script>
                            """, unsafe_allow_html=True)
                
                st.markdown("---")
        
        # ========== 分页控制 ==========
        col_prev, col_info, col_next = st.columns([1, 2, 1])
        
        with col_prev:
            if current_page > 1:
                if st.button("⬅️ 上一页", use_container_width=True):
                    st.session_state.current_page = current_page - 1
                    st.rerun()
        
        with col_info:
            st.markdown(f"<div style='text-align: center;'>第 {current_page} / {total_pages} 页</div>", unsafe_allow_html=True)
        
        with col_next:
            if current_page < total_pages:
                if st.button("下一页 ➡️", use_container_width=True):
                    st.session_state.current_page = current_page + 1
                    st.rerun()

except ImportError as e:
    st.error(f"模块加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
except Exception as e:
    st.error(f"加载对话记录失败: {e}")
    import traceback
    st.code(traceback.format_exc())
