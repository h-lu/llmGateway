# TeachProxy

AI 教学代理网关与管理面板 - 用于教学场景的 OpenAI 兼容 API 代理。

## 功能

- 🔐 API Key 认证
- 🚫 规则引擎（阻断直接代码请求、引导提问）
- 📊 按周额度管理
- 💾 对话记录存储与导出
- 🎛️ Streamlit 管理面板

## 运行方式

```bash
# 安装依赖
pip install -r requirements.txt -r requirements-dev.txt

# 启动网关服务
uvicorn gateway.app.main:app --reload --host 0.0.0.0 --port 8000

# 启动管理面板（另开终端）
streamlit run admin/streamlit_app.py
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/chat/completions` | POST | OpenAI 兼容的聊天补全接口 |

## 配置

创建 `.env` 文件：

```env
DATABASE_URL=sqlite+pysqlite:///./teachproxy.db
DEEPSEEK_API_KEY=your_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
```

## 测试

```bash
pytest
```
