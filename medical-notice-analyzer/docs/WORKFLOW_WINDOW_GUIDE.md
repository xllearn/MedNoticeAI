# 旧 Workflow 窗口处理文档

本文档用于单独开启一个窗口处理旧 Dify Workflow 兼容入口。这个窗口只处理一次性 URL 分析链路，不处理 Chatflow 的 Word 上传、多轮反馈修订和确认后下载编排。

## 新窗口开场白

在新窗口可以直接发送：

```text
请先读取 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\docs\WORKFLOW_WINDOW_GUIDE.md、C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\NEXT_CHAT_HANDOFF.md 和 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\PROJECT_CONTEXT.md。

本窗口只处理旧 Dify Workflow 兼容入口：一次性输入公告 URL，抓取正文和附件，生成报告，质检后导出 Word。不要修改 Chatflow，除非我明确要求。
```

## 定位

旧 Workflow 是兼容入口，适合验证旧的一次性链路：

- 输入公告 URL。
- 调用本地辅助服务 `/analyze` 抓取正文和附件。
- LLM 生成结构化 `ReportIR`。
- 调用 `/report/render` 渲染 Markdown。
- 运行 QA。
- 通过 `/report/export_checked` 导出 Word。

旧 Workflow 不适合作为正式生产入口处理以下能力：

- 用户上传历史 Word。
- 同一会话内多轮修改报告。
- 用户确认后再下载的完整会话式体验。

这些能力应在 Chatflow 窗口处理。

## 当前 Dify 入口

Dify 应用页面：

```text
http://localhost/app/a09ac7aa-3f49-4fc2-aea4-55471a3c6802/workflow
```

当前数据库状态：

```text
app_id = a09ac7aa-3f49-4fc2-aea4-55471a3c6802
mode = workflow
published workflow_id = 915e51a0-5692-4342-a562-12dee2abe27a
draft workflow_id = 8216a411-8690-42e7-932a-0d2c9a13fd76
nodes = 20
edges = 19
has_export_checked = true
has_history_report = false
```

## 启动本地服务

在项目目录执行：

```powershell
cd C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
docker compose up -d --build
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8099/health
```

正常结果应包含：

```text
{"status":"ok"}
```

Dify 容器内部访问本地辅助服务必须使用：

```text
http://host.docker.internal:8099
```

不要在 Dify HTTP 节点里写 `127.0.0.1:8099`，那会指向 Dify 容器自己。

## 如何从头测试旧 Workflow

1. 打开 `http://localhost/app/a09ac7aa-3f49-4fc2-aea4-55471a3c6802/workflow`。
2. 点击 Dify 页面右上角的预览或运行按钮。
3. 输入 `notice_url`。
4. 运行一次。
5. 查看每个节点是否成功，重点看抓取、报告生成、渲染、QA、导出节点。
6. 如果生成 Word，复制返回的下载链接在浏览器打开验证。

旧 Workflow 是单次运行，不需要也不应该在同一会话里继续输入修改意见。

## 本地接口快速验证

只验证辅助服务是否能抓取 URL：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8099/analyze `
  -ContentType application/json `
  -Body '{"url":"https://example.com/notice.html"}'
```

验证后端渲染、QA、导出相关逻辑时，优先运行测试：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
```

查看 Dify 最近运行的 token 和耗时：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dify_run_stats.ps1 -Latest 1
```

## 相关文件

Workflow 蓝本：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\dify-workflow-medical-notice-report.yml
```

Workflow 增强脚本：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\scripts\enhance_dify_workflow_graph.py
```

本地辅助服务：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\app\main.py
```

核心 Prompt：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_system_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_user_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_fix_prompt.md
```

## 修改边界

Workflow 窗口可以处理：

- 旧 Workflow 节点失败。
- URL 抓取失败。
- 附件解析失败。
- `ReportIR` 渲染失败。
- QA 或 Word 导出失败。
- Dify 节点参数和旧 graph 修复。

Workflow 窗口不要处理：

- `history_report` 文件上传。
- 多轮用户反馈修订。
- Chatflow 路由分支。
- Chatflow 导入脚本。
- Chatflow 会话变量。

如果需要改 `app\main.py`、Prompt 或测试，必须说明这会同时影响 Workflow 和 Chatflow，因为两者共用本地辅助服务和报告规则。

## 写回 Workflow 的谨慎流程

如果必须直接改 Dify live graph，先备份：

```powershell
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$out = "dify-db-backups/workflow-8216a411-graph-live-before-change-$ts.json"
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -t -A -c "select graph from workflows where id='8216a411-8690-42e7-932a-0d2c9a13fd76';" | Out-File -LiteralPath $out -Encoding utf8
Write-Output $out
```

查询当前 graph 状态：

```powershell
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c "select id, version, json_array_length((graph::json)->'nodes') as nodes, json_array_length((graph::json)->'edges') as edges, graph like '%/report/render%' as has_render, graph like '%/report/export_checked%' as has_export_checked from workflows where app_id='a09ac7aa-3f49-4fc2-aea4-55471a3c6802';"
```

写回后至少验证：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8099/health
```

## 常见判断

如果 Dify 报 `host.docker.internal` 连接失败，先确认 `medical-notice-analyzer` 容器是否运行，并检查 `8099` 端口。

如果报告生成了但 Word 不生成，优先看 `/report/export_checked` 节点响应中的 `blocked`、`qa_summary` 和错误信息。

如果 Word 里出现 JSON、Dify 变量、思考内容或临时字段，优先检查 `ReportIR` 提取和 `app\main.py` 的清洗逻辑。

如果需要用户反馈修订，不要在旧 Workflow 里硬做，切到 Chatflow 窗口。
