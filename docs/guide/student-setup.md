# 学生 IDE 配置

## Continue.dev

在 `~/.continue/config.json` 中配置：

```json
{
  "models": [{
    "provider": "openai",
    "model": "deepseek-chat",
    "apiBase": "https://your-server.com/v1",
    "apiKey": "student-unique-key"
  }]
}
```

## Cursor

在设置 (Settings) 中填写：
- **API Key**: 你的专属 API Key
- **Base URL**: `https://your-server.com/v1`
- **Model**: `deepseek-chat`

## VS Code + Continue 插件

1. 安装 Continue 插件
2. 打开 Continue 设置
3. 添加自定义 OpenAI 兼容提供商
4. 填写服务器地址和 API Key

## JetBrains AI

在 AI Assistant 设置中配置 OpenAI 兼容端点。
