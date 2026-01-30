import streamlit as st
import pandas as pd
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.header("💬 对话记录")

try:
    from admin.db_utils import get_all_conversations
    
    conversations = get_all_conversations(limit=100)
    
    if conversations:
        # Filter options
        col1, col2 = st.columns(2)
        with col1:
            action_filter = st.selectbox(
                "过滤操作类型",
                ["全部", "blocked", "guided", "passed"]
            )
        with col2:
            limit_num = st.slider("显示条数", 10, 100, 50)
        
        # Filter and display
        filtered = conversations
        if action_filter != "全部":
            filtered = [c for c in conversations if c.action_taken == action_filter]
        
        filtered = filtered[:limit_num]
        
        if filtered:
            data = [{
                "时间": c.timestamp.strftime("%Y-%m-%d %H:%M") if c.timestamp else "-",
                "学生ID": c.student_id[:8] + "..." if c.student_id else "-",
                "提问": c.prompt_text[:50] + "..." if len(c.prompt_text) > 50 else c.prompt_text,
                "操作": c.action_taken,
                "触发规则": c.rule_triggered or "-",
                "Tokens": c.tokens_used
            } for c in filtered]
            
            df = pd.DataFrame(data)
            
            # Color code by action
            def highlight_action(row):
                if row["操作"] == "blocked":
                    return ["background-color: #ffcccc"] * len(row)
                elif row["操作"] == "guided":
                    return ["background-color: #ffffcc"] * len(row)
                return [""] * len(row)
            
            styled_df = df.style.apply(highlight_action, axis=1)
            st.dataframe(styled_df, use_container_width=True, hide_index=True)
            st.caption(f"显示 {len(filtered)} / {len(conversations)} 条记录")
        else:
            st.info(f"没有 {action_filter} 类型的记录")
    else:
        st.info("暂无对话记录")
        st.caption("当学生通过网关发送请求后，对话将记录在此")

except ImportError as e:
    st.warning(f"模块加载失败: {e}")
except Exception as e:
    st.error(f"加载对话记录失败: {e}")
