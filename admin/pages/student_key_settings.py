"""Student API Key settings page in Admin Panel."""

import streamlit as st

st.set_page_config(
    page_title="API Key 设置",
    page_icon="🔑",
    layout="wide",
)

st.title("🔑 学生 API Key 设置")

st.markdown("""
## 配置说明

您可以配置自己的 DeepSeek 或 OpenRouter API Key 来继续使用 AI 服务：

### 为什么需要配置？
- 当您的教师配额用完时，可以使用自己的 Key 继续使用
- 使用自己的 Key **不消耗**教师配额
- 系统仍会注入统一的教学提示词

### 推荐提供商

| 提供商 | 成本 (每1M tokens) | 特点 |
|--------|-------------------|------|
| **DeepSeek** | $0.55 / $2.19 | 最便宜，推荐 |
| **OpenRouter** | $0.58 / $2.31 | 有故障转移 |

### 如何获取 API Key？

1. **DeepSeek**: 访问 [platform.deepseek.com](https://platform.deepseek.com)
2. **OpenRouter**: 访问 [openrouter.ai](https://openrouter.ai)
""")

col1, col2 = st.columns(2)

with col1:
    st.subheader("当前设置")
    has_own_key = st.checkbox("已配置自己的 Key", value=False)
    
    if has_own_key:
        st.success("✅ 已配置 DeepSeek API Key")
        st.code("sk-dw...3k9a", language=None)
        
        if st.button("🗑️ 删除 Key", type="secondary"):
            st.warning("删除后需要使用教师配额")
    else:
        st.info("使用教师配额")

with col2:
    st.subheader("配额状态")
    st.metric("本周剩余配额", "8,500 / 10,000")
    st.progress(0.85)
    st.caption("第 5 周，下周重置")

st.divider()

st.subheader("配置新 Key")

with st.form("key_config_form"):
    provider = st.selectbox(
        "选择提供商",
        options=["deepseek", "openrouter"],
        format_func=lambda x: "DeepSeek (推荐)" if x == "deepseek" else "OpenRouter",
    )
    
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="sk-...",
        help="您的 Key 将被加密存储",
    )
    
    submitted = st.form_submit_button("💾 保存配置", type="primary")
    
    if submitted:
        if not api_key.startswith(("sk-", "sk-or-")):
            st.error("❌ API Key 格式不正确，应以 sk- 开头")
        elif len(api_key) < 20:
            st.error("❌ API Key 太短")
        else:
            st.success("✅ API Key 配置成功！")
            st.balloons()

st.divider()

st.subheader("帮助")

with st.expander("如何获取 DeepSeek API Key？"):
    st.markdown("""
    1. 访问 [platform.deepseek.com](https://platform.deepseek.com)
    2. 注册/登录账号
    3. 进入 "API Keys" 页面
    4. 点击 "Create new secret key"
    5. 复制生成的 Key（以 sk- 开头）
    """)

with st.expander("费用说明"):
    st.markdown("""
    **DeepSeek 定价：**
    - 输入: $0.55 / 1M tokens
    - 输出: $2.19 / 1M tokens
    
    **估算：**
    - 一次普通对话约 500-1000 tokens
    - 成本约 $0.0003 - $0.001
    - 100 次对话约 $0.03 - $0.10
    """)
