# 文衡工作台

文衡工作台是面向中文长文档的自托管处理平台，提供文本润色、原创性增强、
Word/PDF 导入导出、模板化排版、格式检查、任务并发控制和管理后台。

本仓库是 [chi111i/BypassAIGC](https://github.com/chi111i/BypassAIGC) 的衍生版本，
保留原作者署名并在界面、文档保真、并发任务、部署方式和安全控制方面进行了扩展。

## 主要能力

- 多阶段论文润色与原创性增强
- DOCX、PDF、Markdown 和文本批量导入及 ZIP 批量导出
- 文件任务强制按原格式导出；DOCX 仅替换文字节点，TXT/Markdown 保留换行、缩进和标记
- PDF 固定原文字框、字号和颜色，文字无法容纳时阻止导出而不缩小字体
- 可复用排版规范生成与格式检查
- 用户任务并发和全局 AI 请求并发限制
- 任务停止、继续、历史记录和结果导出
- 卡密管理、会话监控和运行时配置管理
- Docker Compose 单机部署

## 快速部署

```bash
cp app.env.example app.env
# 编辑 app.env，填写模型、API Key、随机 SECRET_KEY 和管理员凭据
docker compose up -d --build
```

服务默认仅监听 `127.0.0.1:9800`，应通过 HTTPS 反向代理公开访问。

`app.env` 仅用于容器首次启动时初始化 `data/.env`。初始化完成后，
`data/.env` 是运行时配置的唯一来源，管理后台修改的模型和并发参数也会持久化到该文件。
升级前应备份 `data/`，不要仅备份 `app.env`。

镜像标签可以通过 Compose 项目目录下的 `.env` 固定：

```dotenv
WENHENG_IMAGE_TAG=2026-07-14-a1b2c3d
```

应用固定使用一个 Uvicorn worker，因为当前 SQLite 会话和文档任务队列包含进程内状态。
并发由用户任务限制、全局任务限制和全局 AI 请求限制分层控制。超过用户或全局任务并发的
文件保持 `queued` 并按公平队列等待，不应通过增加 Web worker 数量扩容。

批量任务默认限制如下，可在 `data/.env` 或管理配置接口中调整：

```dotenv
MAX_BATCH_FILES=20
MAX_BATCH_TOTAL_SIZE_MB=100
MAX_QUEUED_TASKS_PER_USER=100
```

## Agent API 与 CLI

Agent API 使用稳定的版本化路径和标准 Bearer 认证。网页端原有接口保持不变。

- Swagger：`https://your-domain.example/api/v1/agent/docs`
- OpenAPI：`https://your-domain.example/api/v1/agent/openapi.json`
- API 根路径：`https://your-domain.example/api/v1/agent`

卡密通过 `Authorization` 请求头传递：

```bash
curl -H "Authorization: Bearer YOUR_CARD_KEY" \
  https://your-domain.example/api/v1/agent/capabilities

curl -X POST \
  -H "Authorization: Bearer YOUR_CARD_KEY" \
  -F "file=@paper.docx" \
  -F "processing_mode=paper_polish_enhance" \
  https://your-domain.example/api/v1/agent/tasks/file
```

Python SDK 与 CLI 可以直接从仓库安装：

```bash
pip install "git+https://github.com/simplez2/wenheng-workspace.git@main#subdirectory=clients/python"
export WENHENG_BASE_URL="https://your-domain.example"
export WENHENG_API_KEY="YOUR_CARD_KEY"

wenheng capabilities
wenheng submit paper.docx --wait
wenheng batch chapter-1.docx chapter-2.pdf --wait
wenheng status TASK_ID
```

CLI 的任务元数据输出为 JSON，错误输出到 stderr，适合 shell、CI 和 Agent 工具调用。
完整说明见 [Agent API](AGENT_API.md) 和 [Python Agent Client](clients/python/README.md)。

生产环境必须设置：

```dotenv
ENVIRONMENT=production
CORS_ORIGINS=https://your-domain.example
SECRET_KEY=at-least-32-random-characters
ADMIN_PASSWORD=use-a-long-unique-password
ALLOW_USER_AI_CONFIG=false
ALLOW_PRIVATE_AI_ENDPOINTS=false
```

复制示例配置后不要直接启动生产服务。占位密码和占位密钥会被启动检查拒绝。

## 本地开发

后端使用 Python 3.11：

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r package/backend/requirements.txt
PYTHONPATH=package/backend uvicorn app.main:app --reload --port 9800
```

前端：

```bash
cd package/frontend
npm ci
npm run dev
```

## 验证

```bash
PYTHONPATH=package/backend python -m unittest discover -s package/backend/tests -p "test_*.py" -v
cd package/frontend && npm audit && npm run build
```

## 安全

公开部署前阅读 [SECURITY.md](SECURITY.md)。运行时配置接口不会返回已保存的 API Key，
配置文件采用白名单和原子写入；自定义 AI 地址默认关闭，并阻断私网和保留地址。
生产容器使用非 root 用户、只读根文件系统、无 Linux capabilities、受限 PID/内存/CPU、
临时文件系统和日志轮转。Secret Scanning 与 Push Protection 在 GitHub 仓库中保持启用。

## 架构与贡献

- [ARCHITECTURE.md](ARCHITECTURE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [NOTICE](NOTICE)

## 许可证

本项目依据原项目许可证继续使用
[CC BY-NC-SA 4.0](LICENSE)。必须署名、禁止商业使用，衍生版本必须使用相同许可证。
