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
| `API_KEY_ENCRYPTION_SECRET` | 是 | — | API Key 加密密钥，生产环境必须更换为随机强密码 |
| `REDIS_URL` | 否 | `redis://localhost:6379` | Redis 连接地址（Worker 队列） |

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
uv run uvicorn main:app --reload --port 8000
```

然后访问 http://localhost:8000/docs 查看 Swagger UI。

### 5. 启动 Worker（异步任务队列）

审查等长时间任务通过 Arq Worker 异步执行，需单独启动：

```powershell
cd backend
uv run arq workers.config.WorkerSettings
```

前提：Redis 服务已启动，且 `.env` 中 `REDIS_URL` 配置正确。

## API Key 功能（Agent API 认证）

系统支持通过 API Key 进行外部程序认证（Agent API），用于第三方集成调用。

### API Key 说明

- 每个 API Key 以 `glzd_live_` 或 `glzd_test_` 前缀开头
- Key 值经过加密存储，创建后仅在响应中完整展示一次
- 支持 Key 的创建、吊销和列表查询

### Agent API 认证示例

所有 Agent API 请求需在 Header 中携带 `Authorization: Bearer <api_key>`：

```bash
# 查询身份
curl -H "Authorization: Bearer glzd_live_xxx" http://localhost:8000/api/v1/agent/me

# 创建审查任务
curl -X POST -H "Authorization: Bearer glzd_live_xxx" -H "Content-Type: application/json" \
  http://localhost:8000/api/v1/agent/jobs/inspect

# 查询任务状态
curl -H "Authorization: Bearer glzd_live_xxx" http://localhost:8000/api/v1/agent/jobs/{job_id}
```

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/inspection/upload` | 上传文档并执行智能体检 |
| GET | `/inspection/records` | 体检记录列表 |
| GET | `/inspection/records/{id}` | 单条记录详情 |
| GET | `/health` | 健康检查 |
| POST | `/api/v1/agent/keys` | 创建 API Key |
| GET | `/api/v1/agent/keys` | 查询 API Key 列表 |
| DELETE | `/api/v1/agent/keys/{key_id}` | 吊销 API Key |
| GET | `/api/v1/agent/me` | 查询 API Key 对应身份 |
| POST | `/api/v1/agent/jobs/inspect` | 创建审查任务 |
| GET | `/api/v1/agent/jobs/{job_id}` | 查询任务状态 |
