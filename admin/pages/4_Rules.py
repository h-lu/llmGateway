import streamlit as st
import pandas as pd
import sys
import re
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.header("⚙️ 规则配置")

try:
    from admin.db_utils import (
        get_all_rules, get_db_session, update_rule, delete_rule, toggle_rule_enabled
    )
    from gateway.app.db.models import Rule
    from gateway.app.services.rules import BLOCK_PATTERNS, GUIDE_PATTERNS
    from gateway.app.services.rule_service import reload_rules
    
    # ==================== 规则缓存控制 ====================
    col1, col2 = st.columns([3, 1])
    with col1:
        st.subheader("📋 内置规则")
    with col2:
        if st.button("🔄 刷新规则缓存", type="secondary"):
            try:
                reload_rules()
                st.success("✅ 规则缓存已刷新！")
                st.rerun()
            except Exception as e:
                st.error(f"刷新失败: {e}")
    
    with st.expander("🚫 阻断规则（硬编码）", expanded=True):
        for i, pattern in enumerate(BLOCK_PATTERNS, 1):
            st.code(pattern, language="regex")
        st.caption("这些规则在第1-2周生效，匹配时阻止直接请求代码")
    
    with st.expander("💡 引导规则（硬编码）", expanded=False):
        for pattern, message in GUIDE_PATTERNS:
            col1, col2 = st.columns([1, 2])
            with col1:
                st.code(pattern, language="regex")
            with col2:
                st.write(message)
    
    st.divider()
    
    # ==================== 规则测试器 ====================
    st.subheader("🧪 规则测试")
    with st.expander("测试规则匹配", expanded=False):
        test_prompt = st.text_area("输入测试文本", placeholder="帮我写一个Python爬虫程序")
        test_week = st.number_input("模拟周次", min_value=1, max_value=20, value=1)
        
        if st.button("运行测试", type="primary"):
            if test_prompt:
                from gateway.app.services.rule_service import get_rule_service
                service = get_rule_service()
                result = service.evaluate_prompt(test_prompt, test_week)
                
                if result.action == "blocked":
                    st.error(f"🚫 **阻断** - 规则ID: {result.rule_id}")
                    st.info(result.message)
                elif result.action == "guided":
                    st.warning(f"💡 **引导** - 规则ID: {result.rule_id}")
                    st.info(result.message)
                else:
                    st.success("✅ **通过** - 无规则匹配")
            else:
                st.warning("请输入测试文本")
    
    st.divider()
    
    # ==================== 数据库规则管理 ====================
    st.subheader("📦 数据库规则")
    
    # Add new rule
    with st.expander("➕ 添加新规则", expanded=False):
        with st.form("add_rule_form"):
            col1, col2 = st.columns(2)
            with col1:
                pattern = st.text_input("正则表达式 *", placeholder=r"写一个.+程序")
                rule_type = st.selectbox("规则类型 *", ["block", "guide"])
            with col2:
                active_weeks = st.text_input("生效周次", value="1-16", placeholder="1-2 或 3-6")
                st.caption("格式: \"1-2\" 表示第1-2周, \"5\" 表示仅第5周")
            
            message = st.text_area("返回消息 *", placeholder="触发规则时返回给用户的消息")
            
            # Validate regex
            def validate_regex(pattern_str):
                try:
                    re.compile(pattern_str)
                    return True
                except re.error:
                    return False
            
            submitted = st.form_submit_button("添加规则", type="primary")
            
            if submitted:
                if not pattern:
                    st.error("正则表达式不能为空")
                elif not validate_regex(pattern):
                    st.error("正则表达式格式无效")
                elif not message:
                    st.error("返回消息不能为空")
                else:
                    session = get_db_session()
                    try:
                        new_rule = Rule(
                            pattern=pattern,
                            rule_type=rule_type,
                            message=message,
                            active_weeks=active_weeks,
                            enabled=True
                        )
                        session.add(new_rule)
                        session.commit()
                        st.success("✅ 规则添加成功！5分钟内自动生效，或点击刷新按钮立即生效。")
                        st.rerun()
                    except Exception as e:
                        session.rollback()
                        st.error(f"添加失败: {e}")
                    finally:
                        session.close()
    
    # Display and manage database rules
    rules = get_all_rules()
    
    if rules:
        st.write(f"共 **{len(rules)}** 条数据库规则")
        
        # Create tabs for different views
        tab_list, tab_edit = st.tabs(["📋 规则列表", "✏️ 编辑规则"])
        
        with tab_list:
            # Prepare data for display
            data = []
            for r in rules:
                status_icon = "🟢" if r.enabled else "🔴"
                type_icon = "🚫" if r.rule_type == "block" else "💡"
                data.append({
                    "ID": r.id,
                    "状态": status_icon,
                    "类型": f"{type_icon} {r.rule_type}",
                    "正则": r.pattern,
                    "消息": r.message[:40] + "..." if len(r.message) > 40 else r.message,
                    "生效周": r.active_weeks,
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Quick actions
            st.divider()
            st.write("快速操作：")
            
            cols = st.columns(4)
            for i, rule in enumerate(rules[:8]):  # Show up to 8 quick action buttons
                with cols[i % 4]:
                    if rule.enabled:
                        if st.button(f"🔴 禁用 #{rule.id}", key=f"disable_{rule.id}"):
                            try:
                                toggle_rule_enabled(rule.id)
                                st.success(f"已禁用规则 #{rule.id}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"操作失败: {e}")
                    else:
                        if st.button(f"🟢 启用 #{rule.id}", key=f"enable_{rule.id}"):
                            try:
                                toggle_rule_enabled(rule.id)
                                st.success(f"已启用规则 #{rule.id}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"操作失败: {e}")
        
        with tab_edit:
            # Rule editing interface
            rule_options = {f"#{r.id} [{r.rule_type}] {r.pattern[:30]}...": r for r in rules}
            selected_rule_key = st.selectbox(
                "选择要编辑的规则",
                options=list(rule_options.keys()),
                index=0
            )
            
            if selected_rule_key:
                selected_rule = rule_options[selected_rule_key]
                
                with st.form("edit_rule_form"):
                    st.write(f"编辑规则 #{selected_rule.id}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        edit_pattern = st.text_input(
                            "正则表达式",
                            value=selected_rule.pattern
                        )
                        edit_type = st.selectbox(
                            "规则类型",
                            ["block", "guide"],
                            index=0 if selected_rule.rule_type == "block" else 1
                        )
                    with col2:
                        edit_weeks = st.text_input(
                            "生效周次",
                            value=selected_rule.active_weeks
                        )
                        edit_enabled = st.checkbox(
                            "启用规则",
                            value=selected_rule.enabled
                        )
                    
                    edit_message = st.text_area(
                        "返回消息",
                        value=selected_rule.message
                    )
                    
                    col_save, col_delete = st.columns(2)
                    with col_save:
                        save_submitted = st.form_submit_button("💾 保存修改", type="primary")
                    with col_delete:
                        delete_submitted = st.form_submit_button("🗑️ 删除规则", type="secondary")
                    
                    if save_submitted:
                        try:
                            update_rule(
                                selected_rule.id,
                                pattern=edit_pattern,
                                rule_type=edit_type,
                                message=edit_message,
                                active_weeks=edit_weeks,
                                enabled=edit_enabled
                            )
                            st.success("✅ 规则更新成功！")
                            st.rerun()
                        except Exception as e:
                            st.error(f"更新失败: {e}")
                    
                    if delete_submitted:
                        # Confirm deletion
                        st.session_state[f"confirm_delete_{selected_rule.id}"] = True
                        st.warning(f"确定要删除规则 #{selected_rule.id} 吗？")
                        if st.button("确认删除", key=f"confirm_del_{selected_rule.id}"):
                            try:
                                delete_rule(selected_rule.id)
                                st.success("✅ 规则已删除！")
                                st.rerun()
                            except Exception as e:
                                st.error(f"删除失败: {e}")
    else:
        st.info("数据库中暂无自定义规则")
        st.caption("目前使用硬编码的内置规则，您可以添加自定义规则")

except ImportError as e:
    st.warning(f"模块加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
except Exception as e:
    st.error(f"加载规则失败: {e}")
    import traceback
    st.code(traceback.format_exc())
