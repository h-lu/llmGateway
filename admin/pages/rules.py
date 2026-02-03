"""
TeachProxy Admin - 规则配置页面
"""
import streamlit as st
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="规则配置 - TeachProxy Admin",
    page_icon="⚙️",
    layout="wide"
)

st.title("⚙️ 规则配置")

# 检查认证
if "admin_authenticated" not in st.session_state or not st.session_state.admin_authenticated:
    st.warning("⚠️ 请先登录")
    st.stop()

try:
    from admin.db_utils_v2 import (
        get_all_rules, create_rule, update_rule, delete_rule, toggle_rule_enabled
    )
    from gateway.app.services.rules import BLOCK_PATTERNS, GUIDE_PATTERNS
    
    # ========== 规则缓存控制 ==========
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### 📋 规则概览")
    with col2:
        if st.button("🔄 刷新规则缓存", type="secondary", use_container_width=True):
            try:
                from gateway.app.services.rule_service import reload_rules
                reload_rules()
                st.success("✅ 规则缓存已刷新！")
                st.rerun()
            except Exception as e:
                st.error(f"刷新失败: {e}")
    
    # ========== 内置规则（只读展示） ==========
    with st.expander("📚 查看内置规则（系统预设）", expanded=False):
        tab1, tab2 = st.tabs(["🚫 阻断规则", "💡 引导规则"])
        
        with tab1:
            st.markdown("以下规则在前几周生效，阻止学生直接获取代码答案：")
            for i, pattern in enumerate(BLOCK_PATTERNS, 1):
                st.code(pattern, language="regex")
                st.caption(f"规则 #{i}")
        
        with tab2:
            st.markdown("以下规则在前几周生效，引导学生自主思考：")
            for i, (pattern, message) in enumerate(GUIDE_PATTERNS, 1):
                col_p, col_m = st.columns([1, 2])
                with col_p:
                    st.code(pattern, language="regex")
                with col_m:
                    st.info(message)
                st.divider()
    
    st.divider()
    
    # ========== 规则测试器 ==========
    with st.expander("🧪 规则测试工具", expanded=False):
        st.markdown("测试规则匹配效果，无需保存即可验证")
        
        test_text = st.text_area(
            "输入测试文本",
            placeholder="例如：帮我写一个Python爬虫程序",
            height=80
        )
        test_week = st.number_input(
            "模拟当前周次",
            min_value=1,
            max_value=20,
            value=1,
            help="不同周次可能有不同的规则生效"
        )
        
        if st.button("▶️ 运行测试", type="primary"):
            if test_text:
                try:
                    from gateway.app.services.rule_service import get_rule_service
                    
                    service = get_rule_service()
                    result = service.evaluate_prompt(test_text, test_week)
                    
                    st.markdown("### 测试结果")
                    
                    if result.action == "blocked":
                        st.error(f"🚫 **阻断** - 规则ID: {result.rule_id}")
                        st.markdown(f"<div class='warning-box'>{result.message}</div>", unsafe_allow_html=True)
                    elif result.action == "guided":
                        st.warning(f"💡 **引导** - 规则ID: {result.rule_id}")
                        st.markdown(f"<div class='info-box'>{result.message}</div>", unsafe_allow_html=True)
                    else:
                        st.success("✅ **通过** - 没有规则匹配此内容")
                        st.markdown("内容将直接发送给 AI 处理")
                    
                    # 显示匹配详情
                    with st.expander("查看匹配详情"):
                        st.json({
                            "action": result.action,
                            "rule_id": result.rule_id,
                            "message": result.message,
                            "week": test_week
                        })
                        
                except Exception as e:
                    st.error(f"测试失败: {e}")
                    import traceback
                    st.code(traceback.format_exc())
            else:
                st.warning("请输入测试文本")
    
    st.divider()
    
    # ========== 添加新规则 ==========
    with st.expander("➕ 添加自定义规则", expanded=False):
        st.markdown("<div class='info-box'>创建自定义规则补充内置规则</div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            new_pattern = st.text_input(
                "正则表达式 *",
                placeholder=r"帮我写.+程序",
                help="使用 Python 正则表达式语法"
            )
            new_type = st.selectbox(
                "规则类型 *",
                ["block", "guide"],
                format_func=lambda x: "🚫 阻断" if x == "block" else "💡 引导"
            )
        with col2:
            new_weeks = st.text_input(
                "生效周次",
                value="1-16",
                placeholder="1-4, 8-12",
                help="格式: '1-4' 表示第1-4周, '1,3,5' 表示特定周次"
            )
            st.caption("默认 1-16 表示全学期生效")
        
        new_message = st.text_area(
            "返回消息 *",
            placeholder="触发规则时返回给学生的提示消息...",
            height=100
        )
        
        # 正则验证
        def validate_regex(pattern_str):
            try:
                re.compile(pattern_str)
                return True
            except re.error:
                return False
        
        # 实时验证
        if new_pattern:
            if validate_regex(new_pattern):
                st.success("✅ 正则表达式格式正确")
            else:
                st.error("❌ 正则表达式格式无效")
        
        if st.button("✅ 创建规则", type="primary"):
            if not new_pattern:
                st.error("请输入正则表达式")
            elif not validate_regex(new_pattern):
                st.error("正则表达式格式无效")
            elif not new_message:
                st.error("请输入返回消息")
            else:
                try:
                    rule = create_rule(
                        pattern=new_pattern,
                        rule_type=new_type,
                        message=new_message,
                        active_weeks=new_weeks,
                        enabled=True
                    )
                    st.success(f"✅ 规则 #{rule.id} 创建成功！")
                    st.info("规则将在5分钟内自动生效，或点击刷新按钮立即生效")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败: {e}")
    
    st.divider()
    
    # ========== 数据库规则管理 ==========
    st.markdown("### 🗂️ 自定义规则列表")
    
    rules = get_all_rules()
    
    if not rules:
        st.info("📭 暂无自定义规则。当前仅使用系统内置规则。")
    else:
        st.caption(f"共 {len(rules)} 条自定义规则")
        
        # 规则表格
        import pandas as pd
        
        rule_data = []
        for r in rules:
            status_icon = "🟢" if r.enabled else "🔴"
            type_icon = "🚫" if r.rule_type == "block" else "💡"
            
            rule_data.append({
                "ID": r.id,
                "状态": f"{status_icon} {'启用' if r.enabled else '禁用'}",
                "类型": f"{type_icon} {'阻断' if r.rule_type == 'block' else '引导'}",
                "正则表达式": r.pattern,
                "消息": r.message[:50] + "..." if len(r.message) > 50 else r.message,
                "生效周次": r.active_weeks or "全部"
            })
        
        df = pd.DataFrame(rule_data)
        
        # 样式
        def color_status(val):
            if "🟢" in val:
                return 'background-color: #d1fae5'
            elif "🔴" in val:
                return 'background-color: #fee2e2'
            return ''
        
        styled_df = df.style.applymap(color_status, subset=['状态'])
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.divider()
        
        # ========== 规则编辑 ==========
        st.markdown("### ✏️ 编辑规则")
        
        # 选择要编辑的规则
        rule_options = {f"#{r.id} [{r.rule_type}] {r.pattern[:40]}...": r for r in rules}
        selected = st.selectbox(
            "选择规则",
            options=list(rule_options.keys())
        )
        
        if selected:
            rule = rule_options[selected]
            
            tab_edit, tab_preview = st.tabs(["编辑", "预览效果"])
            
            with tab_edit:
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    edit_pattern = st.text_input(
                        "正则表达式",
                        value=rule.pattern
                    )
                    edit_type = st.selectbox(
                        "规则类型",
                        ["block", "guide"],
                        index=0 if rule.rule_type == "block" else 1,
                        format_func=lambda x: "🚫 阻断" if x == "block" else "💡 引导"
                    )
                with col_e2:
                    edit_weeks = st.text_input(
                        "生效周次",
                        value=rule.active_weeks or "1-16"
                    )
                    edit_enabled = st.checkbox(
                        "启用规则",
                        value=rule.enabled
                    )
                
                edit_message = st.text_area(
                    "返回消息",
                    value=rule.message,
                    height=100
                )
                
                col_save, col_del = st.columns([1, 1])
                
                with col_save:
                    if st.button("💾 保存修改", type="primary", use_container_width=True):
                        try:
                            update_rule(
                                rule.id,
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
                
                with col_del:
                    with st.expander("🗑️ 删除规则"):
                        st.warning("⚠️ 此操作不可恢复！")
                        confirm = st.text_input(f"输入 'DELETE #{rule.id}' 确认")
                        if st.button("确认删除", type="primary"):
                            if confirm == f"DELETE #{rule.id}":
                                if delete_rule(rule.id):
                                    st.success("✅ 规则已删除")
                                    st.rerun()
                                else:
                                    st.error("删除失败")
                            else:
                                st.error("确认文本不匹配")
            
            with tab_preview:
                st.markdown("#### 规则预览")
                st.write(f"**类型:** {'阻断' if rule.rule_type == 'block' else '引导'}")
                st.write(f"**状态:** {'启用' if rule.enabled else '禁用'}")
                st.write(f"**生效周次:** {rule.active_weeks or '全部'}")
                
                st.markdown("**匹配模式:**")
                st.code(rule.pattern, language="regex")
                
                st.markdown("**返回消息:**")
                if rule.rule_type == "block":
                    st.error(rule.message)
                else:
                    st.warning(rule.message)
        
        # 快速操作按钮
        st.divider()
        st.markdown("### ⚡ 快速开关")
        
        cols = st.columns(4)
        for i, rule in enumerate(rules[:8]):  # 最多显示8个
            with cols[i % 4]:
                if rule.enabled:
                    if st.button(
                        f"🔴 禁用 #{rule.id}",
                        key=f"quick_disable_{rule.id}",
                        use_container_width=True
                    ):
                        toggle_rule_enabled(rule.id)
                        st.rerun()
                else:
                    if st.button(
                        f"🟢 启用 #{rule.id}",
                        key=f"quick_enable_{rule.id}",
                        use_container_width=True
                    ):
                        toggle_rule_enabled(rule.id)
                        st.rerun()

except ImportError as e:
    st.error(f"模块加载失败: {e}")
    import traceback
    st.code(traceback.format_exc())
except Exception as e:
    st.error(f"加载规则失败: {e}")
    import traceback
    st.code(traceback.format_exc())
