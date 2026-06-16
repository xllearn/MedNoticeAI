# 新 Chatflow 窗口处理文档

本文档用于单独开启一个窗口处理新版 Dify Chatflow 生产入口。这个窗口专注于文件上传、历史 Word 串联分析、多轮反馈修订、确认后导出 Word。

## 新窗口开场白

在新窗口可以直接发送：

```text
请先读取 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\docs\CHATFLOW_WINDOW_GUIDE.md、C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\NEXT_CHAT_HANDOFF.md 和 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\PROJECT_CONTEXT.md。

本窗口只处理新版 Dify Chatflow 生产入口：公告 URL + 可选历史 Word 上传，首轮生成报告，后续根据用户反馈修订，用户明确确认后才导出 Word。不要修改旧 Workflow，除非我明确要求。
```

## 定位

Chatflow 是当前推荐生产入口，适合处理完整会话式链路：

- 首轮输入公告 URL。
- 可选上传关联项目分析稿 Word。
- 抓取公告正文和附件。
- 提炼历史 Word 为 `history_insights`。
- 生成结构化 `ReportIR`。
- 后端渲染 Markdown。
- QA 后展示报告。
- 用户继续输入修改意见时走修订分支。
- 用户明确回复确认下载后才生成 Word。

旧 Workflow 只保留为一次性 URL 分析兼容入口，不承担 Chatflow 的会话能力。

## 当前 Dify 入口

Dify 应用页面：

```text
http://localhost/app/c0a278d7-e973-4c47-bb7f-9b2596e6648f/workflow
```

当前数据库状态：

```text
app_id = c0a278d7-e973-4c47-bb7f-9b2596e6648f
mode = advanced-chat
published workflow_id = a0055d5f-479a-481b-85cd-9ff88344081f
draft workflow_id = 43f03862-0995-4834-96f8-c28a338e20f4
nodes = 35
edges = 35
has_export_checked = true
has_history_report = true
```

注意：该应用历史里还存在一个较早发布版本 `dde8cca9-82a2-4646-9a9f-a037c866a1bf`，但当前应用指向的发布版本是 `a0055d5f-479a-481b-85cd-9ff88344081f`。除非明确需要清理历史版本，不要删除。

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

Chatflow 当前 HTTP 节点使用的主要接口：

```text
POST /analyze
POST /report/render
POST /report/qa
POST /report/export_checked
GET  /download/{filename}
```

## 如何从头测试 Chatflow

1. 打开 `http://localhost/app/c0a278d7-e973-4c47-bb7f-9b2596e6648f/workflow`。
2. 点击右上角的预览。
3. 在预览面板填写必填项 `公告 URL`。
4. 如需测试历史串联分析，点击 `关联项目分析稿 Word（可选）` 上传 `.docx`。
5. 在聊天输入框发送 `开始分析`。
6. 首轮应返回报告 Markdown 和 QA 摘要，不应立即生成 Word。
7. 如需修改，继续在同一预览会话输入修改意见，例如 `把企业关注点写得更具体一些`。
8. 确认报告可下载后，输入 `确认下载 Word` 或 `可以导出 Word`。
9. Chatflow 进入导出分支，调用 `/report/export_checked`，返回 Word 下载链接。

如果只想测试无历史 Word 的基本链路，第 4 步可以跳过。

## Start 节点输入

当前 Chatflow Start 节点应包含：

```text
notice_url      必填文本，公告 URL
history_report  可选文件，关联项目分析稿 Word
```

Word 上传优先用 `.docx`。虽然 DSL 允许 `.doc`，但 `.doc` 是否稳定取决于 Dify Document Extractor 和 Unstructured 能力。

## 分支规则

`ROUTE TURN` 节点负责判断本轮走哪个分支：

```text
approve_download: 用户明确说确认下载、可以导出、同意下载、下载 Word、导出 Word 等。
first_generate: 会话里 current_report_ir 为空，说明还没有首轮报告。
revise: 已有 current_report_ir，且用户没有确认下载，默认按反馈修订处理。
```

不要把普通修改意见误判成下载确认。只有用户明确要 Word 下载时才走导出分支。

## 会话变量

Chatflow 使用这些会话变量保持状态：

```text
source_evidence
history_insights
current_report_ir
current_final_report
last_qa_summary
last_export_filename
```

首轮生成后必须保存 `current_report_ir` 和 `current_final_report`，否则后续修改意见无法进入稳定修订链路。

## 历史 Word 使用规则

历史 Word 只作为串联分析和写作风格参考，不是本次公告事实来源。

必须遵守：

- 不单独新增 `历史分析`、`历史对照`、`历史项目` 等标题。
- 不把历史 Word 里的价格、周期、企业范围、产品范围、地区范围、采购量、日期写成本次公告事实。
- 最多形成一段短的历史承接内容。
- 历史承接应自然并入现有段落，不要独立成章。
- 表格、规则、时间节点必须以本次公告正文和附件为准。

## 修改 Chatflow 的方式

推荐通过脚本创建或更新本地 Dify advanced-chat 应用：

```powershell
cd C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\import_dify_chatflow.ps1
```

这个脚本会：

- 调用 `scripts\build_dify_chatflow_dsl.py` 生成 DSL。
- 把 DSL 复制进 `docker-api-1`。
- 在 Dify API 容器内调用 `AppDslService.import_app`。
- 发布 draft workflow。
- 更新应用指向最新发布版本。

只查看生成的 DSL：

```powershell
py -3 .\scripts\build_dify_chatflow_dsl.py --stdout
```

如果本机 `python` 是 Windows Store alias，优先使用 `py -3`。

## 相关文件

Chatflow 蓝本：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\dify-chatflow-medical-notice-report.yml
```

Chatflow DSL 生成器：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\scripts\build_dify_chatflow_dsl.py
```

Chatflow 导入脚本：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\scripts\import_dify_chatflow.ps1
```

本地辅助服务：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\app\main.py
```

关键 Prompt：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_system_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_user_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_history_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_revision_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_fix_prompt.md
```

## 本地验证命令

完整测试：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
```

只测 Chatflow 导入器相关用例：

```powershell
py -3 -m unittest discover -s tests -p "test_dify_chatflow_importer.py" -v
```

健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8099/health
```

查看最近 Dify 运行统计：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dify_run_stats.ps1 -Latest 1
```

查询 Chatflow 当前 graph：

```powershell
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c "select id, version, json_array_length((graph::json)->'nodes') as nodes, json_array_length((graph::json)->'edges') as edges, graph like '%history_report%' as has_history_report, graph like '%/report/export_checked%' as has_export_checked from workflows where app_id='c0a278d7-e973-4c47-bb7f-9b2596e6648f';"
```

## 修改边界

Chatflow 窗口可以处理：

- 文件上传配置。
- Document Extractor。
- 历史 Word 提炼。
- 首轮生成。
- 用户反馈修订。
- 确认下载判断。
- Chatflow 会话变量。
- `scripts\build_dify_chatflow_dsl.py` 和 `scripts\import_dify_chatflow.ps1`。

Chatflow 窗口不要处理：

- 旧 Workflow graph 修复。
- 旧 Workflow 兼容入口发布。
- 只属于一次性 Workflow 的节点布局。

如果需要改 `app\main.py`、Prompt 或测试，必须说明这会同时影响 Workflow 和 Chatflow，因为两者共用本地辅助服务和报告规则。

## 常见判断

如果预览面板里看不到上传 Word 控件，优先确认当前打开的是 Chatflow 应用，而不是旧 Workflow 应用。

如果上传 `.doc` 失败，先改用 `.docx` 测试。`.doc` 取决于 Dify 文档提取能力。

如果首轮生成后输入修改意见却重新抓取 URL，检查 `current_report_ir` 是否保存成功，以及 `ROUTE TURN` 的 first_generate 条件。

如果输入 `确认下载 Word` 没有导出，检查 `ROUTE TURN` 的 approve_download 关键词条件。

如果未确认下载前已经生成 Word，说明导出节点被错误接到了首轮或修订分支，需要立即修正。
