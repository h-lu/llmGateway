"""
TeachProxy Admin - 仪表板页面
实时统计数据和趋势图表
"""
import streamlit as st
import sys
from pathlib import Path
from datetime import datetime, timedelta

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

st.set_page_config(
    page_title="仪表板 - TeachProxy Admin",
    page_icon="📊",
    layout="wide"
)

st.title("📊 仪表板")

# 检查认证
if "admin_authenticated" not in st.session_state or not st.session_state.admin_authenticated:
    st.warning("⚠️ 请先登录")
    st.stop()

# 加载数据
try:
    from admin.db_utils_v2 import get_dashboard_stats, get_recent_activity
    
    # 自动刷新
    auto_refresh = st.sidebar.checkbox("🔄 自动刷新 (30秒)", value=False)
    if auto_refresh:
        st.sidebar.caption("⏱️ 上次更新: " + datetime.now().strftime("%H:%M:%S"))
        st.rerun()
    
    # 刷新按钮
    if st.sidebar.button("🔄 立即刷新"):
        st.rerun()
    
    stats = get_dashboard_stats()
    
    # ========== 关键指标卡片 ==========
    st.markdown("### 📈 关键指标")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 1.5rem; border-radius: 1rem; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">👥 学生总数</h4>
            <h2 style="margin: 0.5rem 0; font-size: 2.5rem;">{stats['students']}</h2>
            <p style="margin: 0; opacity: 0.8; font-size: 0.875rem;">注册学生</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                    padding: 1.5rem; border-radius: 1rem; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">💬 今日对话</h4>
            <h2 style="margin: 0.5rem 0; font-size: 2.5rem;">{stats['conversations_today']}</h2>
            <p style="margin: 0; opacity: 0.8; font-size: 0.875rem;">{stats['conversations']} 总计</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); 
                    padding: 1.5rem; border-radius: 1rem; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">🔢 Token 使用</h4>
            <h2 style="margin: 0.5rem 0; font-size: 2.5rem;">{stats['tokens_today']:,}</h2>
            <p style="margin: 0; opacity: 0.8; font-size: 0.875rem;">今日 / {stats['total_tokens']:,} 总计</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        quota_rate = stats['quota_usage_rate']
        color = "#10b981" if quota_rate < 50 else "#f59e0b" if quota_rate < 80 else "#ef4444"
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); 
                    padding: 1.5rem; border-radius: 1rem; color: white;">
            <h4 style="margin: 0; opacity: 0.9;">📊 配额使用</h4>
            <h2 style="margin: 0.5rem 0; font-size: 2.5rem;">{quota_rate:.1f}%</h2>
            <p style="margin: 0; opacity: 0.8; font-size: 0.875rem;">本周 (第 {stats['current_week']} 周)</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    # ========== 图表区域 ==========
    col_chart, col_status = st.columns([2, 1])
    
    with col_chart:
        st.markdown("### 📈 最近 7 天活动趋势")
        
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            activity_data = get_recent_activity(days=7)
            
            if activity_data:
                dates = [d['date'] for d in activity_data]
                conversations = [d['conversations'] for d in activity_data]
                tokens = [d['tokens'] for d in activity_data]
                
                fig = make_subplots(specs=[[{"secondary_y": True}]])
                
                fig.add_trace(
                    go.Bar(
                        x=dates, 
                        y=conversations, 
                        name="对话数",
                        marker_color='#667eea'
                    ),
                    secondary_y=False
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=dates, 
                        y=tokens, 
                        name="Token 使用",
                        mode='lines+markers',
                        line=dict(color='#f5576c', width=3),
                        marker=dict(size=8)
                    ),
                    secondary_y=True
                )
                
                fig.update_layout(
                    height=350,
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=20, r=20, t=40, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
                fig.update_xaxes(title_text="日期", gridcolor='rgba(0,0,0,0.1)')
                fig.update_yaxes(title_text="对话数", secondary_y=False, gridcolor='rgba(0,0,0,0.1)')
                fig.update_yaxes(title_text="Token 数", secondary_y=True)
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📊 暂无活动数据")
        except ImportError:
            st.info("📊 安装 plotly 以查看图表: `pip install plotly`")
        except Exception as e:
            st.error(f"加载图表失败: {e}")
    
    with col_status:
        st.markdown("### 🚦 系统状态")
        
        # 网关健康检查
        try:
            import requests
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                health = response.json()
                
                # 整体状态
                if health.get("status") == "ok":
                    st.success("🟢 网关运行正常")
                else:
                    st.warning("🟡 网关运行降级")
                
                # 组件状态
                components = health.get("components", {})
                
                with st.container():
                    db_status = components.get("database", {}).get("status", "unknown")
                    if db_status == "ok":
                        st.markdown("🟢 数据库连接正常")
                    else:
                        st.markdown("🔴 数据库异常")
                
                with st.container():
                    cache_status = components.get("cache", {})
                    cache_type = cache_status.get("type", "unknown")
                    cache_ok = cache_status.get("status") == "ok"
                    if cache_ok:
                        st.markdown(f"🟢 缓存 ({cache_type}) 正常")
                    else:
                        st.markdown("🟡 缓存异常")
                
                with st.container():
                    providers = components.get("providers", {})
                    healthy = providers.get("healthy", 0)
                    total = providers.get("total", 0)
                    if total > 0:
                        st.markdown(f"{'🟢' if healthy == total else '🟡'} AI 提供商: {healthy}/{total} 正常")
                    else:
                        st.markdown("⚪ AI 提供商: 未配置")
            else:
                st.error("🔴 网关未响应")
        except Exception as e:
            st.error(f"🔴 网关连接失败: {e}")
        
        st.divider()
        
        # 阻断统计
        st.markdown("### 🛡️ 安全统计")
        blocked_rate = (stats['blocked'] / stats['conversations'] * 100) if stats['conversations'] > 0 else 0
        st.metric(
            label="🚫 阻断次数",
            value=f"{stats['blocked']}",
            delta=f"{blocked_rate:.1f}% 占比"
        )
        
        st.metric(
            label="⚙️ 规则数量",
            value=f"{stats['rules']}"
        )
    
    st.divider()
    
    # ========== 快速操作 ==========
    st.markdown("### ⚡ 快速操作")
    
    col_a, col_b, col_c, col_d = st.columns(4)
    
    with col_a:
        if st.button("➕ 添加学生", use_container_width=True, type="primary"):
            st.switch_page("pages/students.py")
    
    with col_b:
        if st.button("📋 查看对话", use_container_width=True):
            st.switch_page("pages/conversations.py")
    
    with col_c:
        if st.button("⚙️ 管理规则", use_container_width=True):
            st.switch_page("pages/rules.py")
    
    with col_d:
        if st.button("📝 每周提示词", use_container_width=True):
            st.switch_page("pages/weekly_prompts.py")

except ImportError as e:
    st.error(f"模块加载失败: {e}")
    st.info("请确保在项目根目录运行: `streamlit run admin/streamlit_app.py`")
except Exception as e:
    st.error(f"加载数据失败: {e}")
    import traceback
    st.code(traceback.format_exc())
