# NEXT_CHAT_HANDOFF

## 新版目标状态

当前设计已批准：主流程转向 Dify Chatflow，20 节点 Workflow 保留为兼容版本。优先完成：报告深度增强、可选关联 Word、质检、质检通过后展示、用户确认后导出 Word。用户反馈后修订分支可最后实现。

更新时间：2026-06-04

这个文件用于新开 Codex 对话后的项目交接。新窗口里可以直接发：

```text
请先读取 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\NEXT_CHAT_HANDOFF.md 和 PROJECT_CONTEXT.md，接着继续处理这个项目。
```

## 项目位置

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
```

该目录不是 Git 仓库，不能依赖 `git diff`。改动检查要用文件内容、测试和备份文件确认。

## 当前运行方式

在项目根目录执行：

```powershell
docker compose up -d --build
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8099/health
```

测试：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
```

最近验证结果：

```text
Ran 47 tests
OK
```

新版 Chatflow 蓝本已包含 first_generate、revise、approve_download 三分支。主功能优先级为：生成质量与本地质检、可选关联 Word、确认后导出 Word；用户反馈修订分支已作为最后阶段实现。

Chatflow can now be created or updated in local Dify with:

```powershell
.\scripts\import_dify_chatflow.ps1
```

The import script uses `scripts\build_dify_chatflow_dsl.py` to generate an importable `advanced-chat` DSL, calls Dify `AppDslService` inside `docker-api-1`, publishes the draft workflow, and prints the app URL.

## Dify 内置 token 与耗时统计

Dify 已保存统计，不在本地报告服务里重算 token。总量来自 `workflow_runs.total_tokens` 和 `workflow_runs.elapsed_time`；节点级统计来自 `workflow_node_executions.execution_metadata` 和 `workflow_node_executions.elapsed_time`。项目内只读导出脚本：

```powershell
.\scripts\dify_run_stats.ps1
.\scripts\dify_run_stats.ps1 -Latest 3
.\scripts\dify_run_stats.ps1 -WorkflowRunId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

脚本输出 `Dify workflow run total` 和 `Dify node totals`，分别用于查看总 token/总耗时和每个节点 token/耗时。

## 访问地址

本地辅助服务：

```text
http://127.0.0.1:8099/health
```

Dify 页面：

```text
http://localhost/apps
```

当前 Dify workflow：

```text
http://localhost/app/a09ac7aa-3f49-4fc2-aea4-55471a3c6802/workflow
```

当前 Dify Chatflow 正式入口：

```text
http://localhost/app/c0a278d7-e973-4c47-bb7f-9b2596e6648f/workflow
```

Dify 容器内调用本地辅助服务必须使用：

```text
http://host.docker.internal:8099
```

## 当前 Dify 数据

```text
app_id = a09ac7aa-3f49-4fc2-aea4-55471a3c6802
workflow_id = 8216a411-8690-42e7-932a-0d2c9a13fd76
Postgres 容器 = docker-db_postgres-1
数据库 = dify
用户 = postgres
密码 = difyai123456
```

查看 live graph 关键状态：

```powershell
$sql = @"
select
  json_array_length((graph::json)->'nodes') as nodes,
  json_array_length((graph::json)->'edges') as edges,
  graph like '%/report/render%' as has_render,
  graph like '%enterprise_tips 必须是字符串数组%' as has_tip_rule,
  graph like '%reasoning_effort%' as has_reasoning_effort,
  md5(graph) as live_md5
from workflows
where id='8216a411-8690-42e7-932a-0d2c9a13fd76';
"@
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c $sql
```

截至本文件更新时间，期望状态：

```text
nodes = 20
edges = 19
has_render = t
has_tip_rule = t
has_reasoning_effort = f
live_md5 = 1f15f6ee75958befca3d3f1d06998f5b
```

## 最近完成的关键修复

1. 模型只输出 `ReportIR`，不再同轮输出 `final_report`。
2. 后端新增 `POST /report/render`，由后端把 `ReportIR` 渲染成 Dify 展示用 Markdown。
3. `/report/export_checked` 返回 `report_markdown`，Dify 最终节点优先展示后端 Markdown 并追加 Word 下载链接。
4. Dify workflow 已加入解析/渲染节点，QA、修复、二次 QA、导出都使用规范化后的 `ReportIR/Markdown`。
5. 抓取节点证据预算已降到 `max_combined_chars=80000`。
6. 修复 Dify LLM 参数错误：关闭 `thinking` 时不能带 `reasoning_effort`。增强脚本现在会自动移除 `reasoning_effort`。
7. 修复报告无法导出 Word 的 `enterprise_tips` schema 错误：如果模型输出 `[{"tip":"..."}]`，后端会自动转成 `["..."]`。
8. Prompt 已明确要求 `enterprise_tips` 必须是字符串数组，不要输出对象数组。

## 核心文件

后端：

```text
app/main.py
```

测试：

```text
tests/test_report_export.py
```

Prompts：

```text
prompts/report_system_prompt.md
prompts/report_user_prompt.md
prompts/report_qa_fix_prompt.md
prompts/report_qa_prompt.md
```

Dify workflow 与增强脚本：

```text
dify-workflow-medical-notice-report.yml
scripts/enhance_dify_workflow_graph.py
dify-db-backups/workflow-8216a411-graph-enhanced.json
```

重要备份：

```text
dify-db-backups/workflow-8216a411-graph-live-before-render-20260603-172404.json
dify-db-backups/workflow-8216a411-graph-live-before-thinking-fix-20260604-090515.json
dify-db-backups/workflow-8216a411-graph-live-before-enterprise-tips-fix-20260604-092003.json
```

## 写回 Dify 的标准流程

先重新生成 graph：

```powershell
py scripts\enhance_dify_workflow_graph.py
```

写入前备份 live graph：

```powershell
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$out = "dify-db-backups/workflow-8216a411-graph-live-before-change-$ts.json"
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -t -A -c "select graph from workflows where id='8216a411-8690-42e7-932a-0d2c9a13fd76';" | Out-File -LiteralPath $out -Encoding utf8
Write-Output $out
```

写入增强 graph：

```powershell
docker cp "dify-db-backups/workflow-8216a411-graph-enhanced.json" docker-db_postgres-1:/tmp/workflow-8216a411-graph-enhanced.json
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -v ON_ERROR_STOP=1 -c "update workflows set graph = pg_read_file('/tmp/workflow-8216a411-graph-enhanced.json'), updated_at = now() where id='8216a411-8690-42e7-932a-0d2c9a13fd76';"
docker restart docker-api-1 docker-web-1 docker-api_websocket-1
```

写入后至少验证：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8099/health
Invoke-WebRequest -UseBasicParsing http://localhost/apps
```

## 已知故障与处理

### Dify 报 `thinking options type cannot be disabled when reasoning_effort is set`

原因：LLM 节点参数里同时有：

```json
"thinking": false,
"reasoning_effort": "max"
```

处理：

1. 确认 `scripts/enhance_dify_workflow_graph.py` 里 `disable_thinking()` 会 `pop("reasoning_effort", None)`。
2. 重新生成 graph。
3. 写回 Dify。
4. 查询 live graph，确认 `has_reasoning_effort = f`。

### Dify 报 `enterprise_tips 字段应为字符串数组而非对象数组`

原因：模型输出了：

```json
"enterprise_tips": [{"tip": "..."}]
```

后端现在已在 `app/main.py` 的 `_coerce_report_ir_payload()` 中容错，会转成：

```json
"enterprise_tips": ["..."]
```

如果再次出现：

1. 确认容器已用最新代码重建：`docker compose up -d --build`
2. 确认测试 `test_render_report_coerces_enterprise_tip_objects_to_strings` 通过。
3. 确认 Dify live graph 包含 `enterprise_tips 必须是字符串数组`。

### 报告生成失败且没有 Word

优先看 Dify 失败节点：

1. `生成采购分析报告`：通常是模型参数或输出格式。
2. `解析并渲染报告`：通常是 ReportIR JSON/schema 问题。
3. `报告质检` 或 `二次质检`：通常是 QA JSON 输出不合法或质检 block。
4. `质检通过后导出 Word`：通常是导出层质量检查、文件名或 Word 生成问题。

后端原则：

- 不完整或非法的模型输出不能直接写 Word。
- Word 正式文件继续以规范化后的 `ReportIR` 为唯一可信来源。
- 固定声明由后端统一追加，模型不应生成临时声明。

## 新对话建议开场

可以直接发：

```text
请读取 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\NEXT_CHAT_HANDOFF.md，确认当前项目状态，然后继续帮我排查 Dify 测试运行/报告导出问题。
```

如果只是要启动项目，可以发：

```text
请读取 NEXT_CHAT_HANDOFF.md，然后启动 medical-notice-analyzer 项目并做健康检查。
```
