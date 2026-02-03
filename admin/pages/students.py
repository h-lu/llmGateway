"""
TeachProxy Admin - 学生管理页面
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="学生管理 - TeachProxy Admin",
    page_icon="👥",
    layout="wide"
)

st.title("👥 学生管理")

# 检查认证
if "admin_authenticated" not in st.session_state or not st.session_state.admin_authenticated:
    st.warning("⚠️ 请先登录")
    st.stop()

try:
    from admin.db_utils_v2 import (
        get_all_students, create_student, update_student_quota,
        reset_student_quota, regenerate_student_api_key, delete_student,
        get_student_quota_stats
    )
    
    # ========== 添加新学生 ==========
    with st.expander("➕ 添加新学生", expanded=False):
        st.markdown("<div class='info-box'>创建新学生账号并生成 API Key</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("姓名 *", placeholder="张三")
            new_email = st.text_input("邮箱 *", placeholder="zhangsan@example.com")
        with col2:
            new_quota = st.number_input(
                "周配额 (Tokens) *",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000
            )
            st.caption("建议: 初学者 10,000，进阶 50,000，高级 100,000")
        
        if st.button("✅ 创建学生", type="primary"):
            if not new_name or not new_email:
                st.error("❌ 请填写姓名和邮箱")
            else:
                try:
                    student, api_key = create_student(
                        name=new_name,
                        email=new_email,
                        quota=new_quota
                    )
                    
                    st.success(f"✅ 学生 {new_name} 创建成功！")
                    
                    # 显示 API Key（只显示一次）
                    st.markdown("### 🔑 API Key（请立即复制保存）")
                    st.code(api_key, language="text")
                    st.warning("⚠️ 此 API Key 只显示一次，请务必复制保存！")
                    
                    # 显示使用示例
                    st.markdown("### 💡 使用示例")
                    st.code(f"""curl -X POST http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer {api_key}" \\
  -d '{{"model": "deepseek-chat", "messages": [{{"role": "user", "content": "你好"}}]}}'""", language="bash")
                    
                except Exception as e:
                    st.error(f"❌ 创建失败: {e}")
    
    st.divider()
    
    # ========== 学生列表 ==========
    st.markdown("### 📋 学生列表")
    
    # 加载学生数据
    students = get_all_students()
    
    if not students:
        st.info("📭 暂无学生数据，请先添加学生")
    else:
        # 搜索和筛选
        col_search, col_filter = st.columns([2, 1])
        with col_search:
            search = st.text_input("🔍 搜索学生（姓名或邮箱）", placeholder="输入关键词...")
        with col_filter:
            quota_filter = st.selectbox(
                "筛选",
                ["全部", "有剩余配额", "配额已用完", "未使用"]
            )
        
        # 筛选学生
        filtered_students = students
        if search:
            filtered_students = [
                s for s in students
                if search.lower() in s.name.lower() or search.lower() in s.email.lower()
            ]
        
        if quota_filter == "有剩余配额":
            filtered_students = [s for s in filtered_students if s.current_week_quota > s.used_quota]
        elif quota_filter == "配额已用完":
            filtered_students = [s for s in filtered_students if s.current_week_quota <= s.used_quota]
        elif quota_filter == "未使用":
            filtered_students = [s for s in filtered_students if s.used_quota == 0]
        
        st.caption(f"显示 {len(filtered_students)} / {len(students)} 名学生")
        
        # 使用表格展示
        student_data = []
        for s in filtered_students:
            remaining = max(0, s.current_week_quota - s.used_quota)
            usage_pct = (s.used_quota / s.current_week_quota * 100) if s.current_week_quota > 0 else 0
            
            # 状态标签
            if usage_pct >= 100:
                status = "🔴 已用完"
            elif usage_pct >= 80:
                status = "🟡 紧张"
            elif s.used_quota == 0:
                status = "⚪ 未使用"
            else:
                status = "🟢 正常"
            
            student_data.append({
                "ID": s.id,
                "姓名": s.name,
                "邮箱": s.email,
                "周配额": f"{s.current_week_quota:,}",
                "已使用": f"{s.used_quota:,}",
                "剩余": f"{remaining:,}",
                "使用率": f"{usage_pct:.1f}%",
                "状态": status,
                "创建时间": s.created_at.strftime("%Y-%m-%d") if s.created_at else "-"
            })
        
        # 显示表格
        import pandas as pd
        df = pd.DataFrame(student_data)
        
        # 应用样式
        def highlight_status(val):
            if "🔴" in val:
                return 'background-color: #fee2e2; color: #dc2626'
            elif "🟡" in val:
                return 'background-color: #fef3c7; color: #d97706'
            elif "🟢" in val:
                return 'background-color: #d1fae5; color: #059669'
            return ''
        
        styled_df = df.style.applymap(highlight_status, subset=['状态'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # ========== 学生详情操作 ==========
        st.markdown("### ✏️ 学生详情管理")
        
        selected_student_id = st.selectbox(
            "选择学生",
            options=[s.id for s in students],
            format_func=lambda x: next(f"{s.name} ({s.email})" for s in students if s.id == x)
        )
        
        if selected_student_id:
            student = next((s for s in students if s.id == selected_student_id), None)
            
            if student:
                tab1, tab2, tab3 = st.tabs(["📊 配额管理", "🔑 API Key", "⚠️ 危险操作"])
                
                with tab1:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 当前配额")
                        remaining = max(0, student.current_week_quota - student.used_quota)
                        
                        # 进度条
                        usage_pct = min(100, (student.used_quota / student.current_week_quota * 100)) if student.current_week_quota > 0 else 0
                        st.progress(usage_pct / 100)
                        st.write(f"已使用: **{student.used_quota:,}** / {student.current_week_quota:,}")
                        st.write(f"剩余: **{remaining:,}**")
                        
                        # 配额使用趋势
                        try:
                            stats = get_student_quota_stats(student.id)
                            if stats:
                                st.markdown("#### 本周使用统计")
                                st.write(f"日志记录使用: {stats.get('week_usage_from_logs', 0):,} tokens")
                        except:
                            pass
                    
                    with col2:
                        st.markdown("#### 修改配额")
                        new_quota = st.number_input(
                            "新的周配额",
                            min_value=1000,
                            max_value=1000000,
                            value=student.current_week_quota,
                            step=1000,
                            key=f"quota_{student.id}"
                        )
                        
                        if st.button("💾 保存配额", key=f"save_quota_{student.id}"):
                            if update_student_quota(student.id, new_quota):
                                st.success("✅ 配额更新成功！")
                                st.rerun()
                            else:
                                st.error("❌ 更新失败")
                        
                        st.divider()
                        
                        st.markdown("#### 重置使用")
                        if st.button("🔄 重置已使用配额", key=f"reset_{student.id}"):
                            if reset_student_quota(student.id):
                                st.success("✅ 已重置已使用配额为 0")
                                st.rerun()
                            else:
                                st.error("❌ 重置失败")
                        st.caption("将已使用配额重置为 0，学生可继续使用")
                
                with tab2:
                    st.markdown("#### API Key 管理")
                    st.info("API Key 已加密存储，无法查看明文。如需更换，请重新生成。")
                    
                    st.warning("⚠️ 重新生成 API Key 后，旧的 Key 将立即失效！")
                    
                    if st.button("🔄 重新生成 API Key", type="secondary", key=f"regen_{student.id}"):
                        # 确认对话框
                        if st.checkbox("我确认要重新生成 API Key", key=f"confirm_regen_{student.id}"):
                            new_key = regenerate_student_api_key(student.id)
                            if new_key:
                                st.success("✅ API Key 重新生成成功！")
                                st.markdown("### 🔑 新的 API Key")
                                st.code(new_key, language="text")
                                st.warning("⚠️ 请立即复制保存，此 Key 只显示一次！")
                            else:
                                st.error("❌ 重新生成失败")
                
                with tab3:
                    st.error("⚠️ 以下操作不可恢复，请谨慎操作！")
                    
                    st.markdown("#### 删除学生")
                    st.write(f"将永久删除学生 **{student.name}** 及其所有数据")
                    
                    confirm_delete = st.text_input(
                        f"输入 'DELETE' 确认删除 {student.name}",
                        key=f"confirm_delete_{student.id}"
                    )
                    
                    if st.button("🗑️ 删除学生", type="primary", key=f"delete_{student.id}"):
                        if confirm_delete == "DELETE":
                            if delete_student(student.id):
                                st.success(f"✅ 学生 {student.name} 已删除")
                                st.rerun()
                            else:
                                st.error("❌ 删除失败")
                        else:
                            st.error("❌ 请输入 'DELETE' 确认删除")

except ImportError as e:
    st.error(f"模块加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
except Exception as e:
    st.error(f"加载学生数据失败: {e}")
    import traceback
    st.code(traceback.format_exc())
