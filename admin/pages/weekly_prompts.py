"""
TeachProxy Admin - 每周提示词管理页面
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="每周提示词 - TeachProxy Admin",
    page_icon="📝",
    layout="wide"
)

st.title("📝 每周提示词管理")

# 检查认证
if "admin_authenticated" not in st.session_state or not st.session_state.admin_authenticated:
    st.warning("⚠️ 请先登录")
    st.stop()

try:
    from admin.db_utils_v2 import (
        get_all_weekly_prompts, get_prompt_by_week, get_current_week_prompt,
        create_or_update_weekly_prompt, delete_weekly_prompt
    )
    from gateway.app.core.utils import get_current_week_number
    
    current_week = get_current_week_number()
    
    # ========== 学期概览 ==========
    st.markdown("### 📅 学期概览")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("当前周次", f"第 {current_week} 周")
    with col2:
        prompts = get_all_weekly_prompts()
        st.metric("已配置周次", f"{len(prompts)} / 16")
    with col3:
        current_prompt = get_current_week_prompt()
        if current_prompt:
            st.metric("本周提示词", "✅ 已配置")
        else:
            st.metric("本周提示词", "❌ 未配置")
    
    st.divider()
    
    # ========== 快速编辑当前周 ==========
    if current_prompt:
        with st.expander(f"✏️ 编辑本周（第 {current_week} 周）提示词", expanded=True):
            st.markdown(f"<div class='success-box'>本周已有配置，可点击下方编辑修改</div>", unsafe_allow_html=True)
            
            cur_title = st.text_input(
                "标题",
                value=current_prompt.title,
                key=f"title_current_{current_week}"
            )
            cur_content = st.text_area(
                "提示词内容（系统提示）",
                value=current_prompt.content,
                height=200,
                key=f"content_current_{current_week}",
                help="此内容将作为系统提示词注入到学生的每次对话中"
            )
            cur_desc = st.text_area(
                "描述（可选，用于管理说明）",
                value=current_prompt.description or "",
                height=80,
                key=f"desc_current_{current_week}"
            )
            cur_active = st.checkbox(
                "启用此提示词",
                value=current_prompt.is_active,
                key=f"active_current_{current_week}"
            )
            
            if st.button("💾 保存本周配置", type="primary", key=f"save_current_{current_week}"):
                try:
                    create_or_update_weekly_prompt(
                        week_number=current_week,
                        title=cur_title,
                        content=cur_content,
                        description=cur_desc if cur_desc else None,
                        is_active=cur_active
                    )
                    st.success("✅ 本周提示词已更新！")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失败: {e}")
    else:
        with st.expander(f"➕ 添加本周（第 {current_week} 周）提示词", expanded=True):
            st.markdown(f"<div class='warning-box'>本周尚未配置提示词</div>", unsafe_allow_html=True)
            
            new_title = st.text_input(
                "标题 *",
                placeholder=f"第 {current_week} 周学习目标",
                key=f"title_new_{current_week}"
            )
            new_content = st.text_area(
                "提示词内容（系统提示） *",
                placeholder="作为学习助手，本周我们重点关注...",
                height=200,
                key=f"content_new_{current_week}",
                help="此内容将作为系统提示词注入到学生的每次对话中"
            )
            new_desc = st.text_area(
                "描述（可选）",
                placeholder="本周学习重点说明...",
                height=80,
                key=f"desc_new_{current_week}"
            )
            
            if st.button("✅ 创建本周提示词", type="primary", key=f"create_current_{current_week}"):
                if not new_title or not new_content:
                    st.error("请填写标题和内容")
                else:
                    try:
                        create_or_update_weekly_prompt(
                            week_number=current_week,
                            title=new_title,
                            content=new_content,
                            description=new_desc if new_desc else None,
                            is_active=True
                        )
                        st.success("✅ 本周提示词已创建！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"创建失败: {e}")
    
    st.divider()
    
    # ========== 学期日历视图 ==========
    st.markdown("### 🗓️ 学期日历")
    
    # 显示所有已配置的提示词
    all_prompts = get_all_weekly_prompts()
    
    if all_prompts:
        import pandas as pd
        
        prompt_data = []
        for p in all_prompts:
            is_current = p.week_number == current_week
            status = "🟢 当前" if is_current else ("⚪ 已配置" if p.is_active else "⚫ 禁用")
            
            prompt_data.append({
                "周次": f"第 {p.week_number} 周",
                "标题": p.title,
                "状态": status,
                "更新时间": p.updated_at.strftime("%Y-%m-%d %H:%M") if p.updated_at else "-"
            })
        
        df = pd.DataFrame(prompt_data)
        
        def highlight_current(val):
            if "🟢" in val:
                return 'background-color: #d1fae5; font-weight: bold'
            return ''
        
        styled_df = df.style.applymap(highlight_current, subset=['状态'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
    else:
        st.info("📭 尚未配置任何周的提示词")
    
    st.divider()
    
    # ========== 批量编辑/管理 ==========
    st.markdown("### ✏️ 管理所有周次")
    
    # 选择周次
    week_options = [f"第 {i} 周" for i in range(1, 17)]
    selected_week_str = st.selectbox(
        "选择周次",
        options=week_options,
        index=current_week - 1 if 1 <= current_week <= 16 else 0
    )
    selected_week = int(selected_week_str.replace("第 ", "").replace(" 周", ""))
    
    # 加载该周的配置
    week_prompt = get_prompt_by_week(selected_week)
    
    if week_prompt:
        st.markdown(f"#### 编辑第 {selected_week} 周配置")
        
        edit_title = st.text_input(
            "标题",
            value=week_prompt.title,
            key=f"edit_title_{selected_week}"
        )
        edit_content = st.text_area(
            "提示词内容",
            value=week_prompt.content,
            height=200,
            key=f"edit_content_{selected_week}"
        )
        edit_desc = st.text_area(
            "描述",
            value=week_prompt.description or "",
            height=80,
            key=f"edit_desc_{selected_week}"
        )
        edit_active = st.checkbox(
            "启用",
            value=week_prompt.is_active,
            key=f"edit_active_{selected_week}"
        )
        
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("💾 保存修改", type="primary", use_container_width=True, key=f"save_week_{selected_week}"):
                try:
                    create_or_update_weekly_prompt(
                        week_number=selected_week,
                        title=edit_title,
                        content=edit_content,
                        description=edit_desc if edit_desc else None,
                        is_active=edit_active
                    )
                    st.success(f"✅ 第 {selected_week} 周配置已更新！")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失败: {e}")
        
        with col2:
            with st.expander("🗑️ 删除配置"):
                st.warning(f"⚠️ 将删除第 {selected_week} 周的提示词配置")
                confirm = st.text_input(f"输入 'DELETE {selected_week}' 确认")
                if st.button("确认删除", type="primary"):
                    if confirm == f"DELETE {selected_week}":
                        if delete_weekly_prompt(week_prompt.id):
                            st.success("✅ 配置已删除")
                            st.rerun()
                        else:
                            st.error("删除失败")
                    else:
                        st.error("确认文本不匹配")
        
        # 预览
        st.markdown("#### 👁️ 预览效果")
        st.markdown(f"**标题:** {edit_title}")
        st.markdown(f"**状态:** {'启用' if edit_active else '禁用'}")
        st.markdown("**系统提示词:**")
        st.code(edit_content, language="markdown")
        
    else:
        st.markdown(f"#### 添加第 {selected_week} 周配置")
        st.info(f"第 {selected_week} 周尚未配置提示词")
        
        new_week_title = st.text_input(
            "标题 *",
            placeholder=f"第 {selected_week} 周学习目标",
            key=f"new_title_{selected_week}"
        )
        new_week_content = st.text_area(
            "提示词内容 *",
            placeholder=f"第 {selected_week} 周，我们将学习...",
            height=200,
            key=f"new_content_{selected_week}"
        )
        new_week_desc = st.text_area(
            "描述",
            placeholder="本周学习重点...",
            height=80,
            key=f"new_desc_{selected_week}"
        )
        
        if st.button("✅ 创建配置", type="primary", use_container_width=True, key=f"create_week_{selected_week}"):
            if not new_week_title or not new_week_content:
                st.error("请填写标题和内容")
            else:
                try:
                    create_or_update_weekly_prompt(
                        week_number=selected_week,
                        title=new_week_title,
                        content=new_week_content,
                        description=new_week_desc if new_week_desc else None,
                        is_active=True
                    )
                    st.success(f"✅ 第 {selected_week} 周配置已创建！")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")
    
    st.divider()
    
    # ========== 使用说明 ==========
    with st.expander("📖 使用说明", expanded=False):
        st.markdown("""
        ### 每周提示词功能说明
        
        **什么是每周提示词？**
        
        每周提示词是作为系统提示词（System Prompt）注入到学生每次对话中的内容。它可以：
        
        1. **设定学习目标** - 明确本周的学习重点
        2. **调整 AI 风格** - 让 AI 以特定方式回应（如更鼓励自主思考）
        3. **渐进式引导** - 随着周次推进，逐步降低引导强度
        
        **使用示例：**
        
        ```
        第 1-2 周：
        "你是学生的学习助手。本周学生刚开始学习编程，
        请多给予鼓励，不要直接给出代码答案，
        而是引导学生自己思考和尝试。"
        
        第 5-6 周：
        "学生已经掌握了基础知识。请鼓励学生独立思考，
        只有在学生确实遇到困难时才给予提示。"
        
        第 10+ 周：
        "学生已具备独立解决问题的能力。
        请仅在学生请求帮助时提供指导。"
        ```
        
        **提示词优先级：**
        - 系统提示词 > 用户消息
        - 每周提示词会与学生消息一起发送给 AI
        - 可以与规则引擎配合使用
        """)

except ImportError as e:
    st.error(f"模块加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
except Exception as e:
    st.error(f"加载数据失败: {e}")
    import traceback
    st.code(traceback.format_exc())
