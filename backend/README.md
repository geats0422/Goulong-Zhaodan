# 后端开发环境说明

## 环境变量设置（必须）

本系统使用 `pydantic-settings` 从**系统环境变量**或本地 `.env` 文件读取配置。

### 1. 复制环境变量模板

```powershell
cd backend
Copy-Item env.example .env
# 然后编辑 .env 填入你的真实 API Key
```

`.env` 已被 `.gitignore` 忽略，不会提交到仓库。

### 2. 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `MODEL_API_KEY` | 是 | — | 模型 API 密钥 |
| `MODEL_BASE_URL` | 否 | `https://api.openai.com/v1` | 模型 API 基础地址 |
| `MODEL_NAME` | 否 | `gpt-4o` | 模型名称 |
| `LOG_LEVEL` | 否 | `INFO` | 日志级别 |
| `MAX_DOCUMENT_LENGTH` | 否 | `8000` | 单次体检最大字符数 |

### 3. 常用模型提供商配置示例

**OpenAI**
```env
MODEL_API_KEY=sk-xxx
MODEL_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o
```

**DeepSeek**
```env
MODEL_API_KEY=sk-xxx
MODEL_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
```

**通义千问**
```env
MODEL_API_KEY=sk-xxx
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen-max
```

**智谱 GLM**
```env
MODEL_API_KEY=xxx
MODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
MODEL_NAME=glm-4
```

### 4. 启动开发服务器

```powershell
cd backend
.venv\Scripts\uvicorn main:app --reload --port 8000
```

然后访问 http://localhost:8000/docs 查看 Swagger UI。

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/inspection/upload` | 上传文档并执行智能体检 |
| GET | `/inspection/records` | 体检记录列表 |
| GET | `/inspection/records/{id}` | 单条记录详情 |
| GET | `/health` | 健康检查 |
