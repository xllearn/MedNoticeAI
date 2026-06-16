# PROJECT_CONTEXT

## 新版目标状态

当前设计已批准：主流程转向 Dify Chatflow，20 节点 Workflow 保留为兼容版本。优先完成：报告深度增强、可选关联 Word、质检、质检通过后展示、用户确认后导出 Word。用户反馈后修订分支可最后实现。

当前本地 Dify 已创建并发布 advanced-chat 应用：

```text
app_id = c0a278d7-e973-4c47-bb7f-9b2596e6648f
app_url = http://localhost/app/c0a278d7-e973-4c47-bb7f-9b2596e6648f/workflow
mode = advanced-chat
workflow type = chat
```

创建或更新该 Chatflow：

```powershell
.\scripts\import_dify_chatflow.ps1
```

该脚本通过 `scripts\build_dify_chatflow_dsl.py` 生成 Dify 可导入 DSL，调用 `docker-api-1` 内的 Dify `AppDslService` 导入并发布 draft workflow。旧 Workflow 应用 `a09ac7aa-3f49-4fc2-aea4-55471a3c6802` 保留为兼容入口。

## Dify 内置 token 与耗时统计

Dify 已保存统计，不在本地报告服务里重算 token。总量来自 `workflow_runs.total_tokens` 和 `workflow_runs.elapsed_time`；节点级统计来自 `workflow_node_executions.execution_metadata` 和 `workflow_node_executions.elapsed_time`。项目内只读导出脚本：

```powershell
.\scripts\dify_run_stats.ps1
.\scripts\dify_run_stats.ps1 -Latest 3
.\scripts\dify_run_stats.ps1 -WorkflowRunId "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

脚本输出 `Dify workflow run total` 和 `Dify node totals`，分别用于查看总 token/总耗时和每个节点 token/耗时。

## 项目位置

项目根目录：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
```

当前不是 Git 仓库，不能依赖 `git diff` 查看改动。

## 项目目标

这是一个配合 Dify 使用的本地辅助服务，用于：

1. 输入医药器械采购/集采/挂网/价格联动公告 URL。
2. 抓取网页正文。
3. 自动发现并解析 Word、Excel、PDF、CSV 附件。
4. 将正文和附件整理成 LLM 证据包。
5. Dify LLM 生成结构化 `ReportIR` 和 Markdown 正式报告。
6. 本地服务根据 `ReportIR` 导出正式 Word。
7. 支持质检模型检查、一次自动修复、二次质检，严重问题阻断 Word 导出。

## 运行地址

Dify 页面：

```text
http://localhost/apps
```

当前 Dify 应用：

```text
http://localhost/app/a09ac7aa-3f49-4fc2-aea4-55471a3c6802/workflow
```

本地辅助服务：

```text
http://localhost:8099/health
```

Dify Docker 容器内调用本地辅助服务必须使用：

```text
http://host.docker.internal:8099
```

主要接口：

```text
POST /analyze
POST /report/export
POST /report/qa
POST /report/export_checked
GET  /download/{filename}
```

## 运行命令

在项目根目录执行：

```powershell
docker compose up -d --build
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8099/health
```

容器内测试：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
```

最近一次验证结果：

```text
Ran 47 tests
OK
```

## 核心文件

后端服务：

```text
app/main.py
```

测试：

```text
tests/test_report_export.py
```

Dify Prompt：

```text
prompts/report_system_prompt.md
prompts/report_user_prompt.md
prompts/report_history_prompt.md
prompts/report_revision_prompt.md
prompts/report_qa_prompt.md
prompts/report_qa_fix_prompt.md
prompts/report_prompt.md
```

Dify 配置：

```text
dify-workflow-medical-notice-report.yml
dify-chatflow-medical-notice-report.yml
```

Dify 数据库 workflow 备份：

```text
dify-db-backups/workflow-8216a411-graph-before.json
dify-db-backups/workflow-8216a411-graph-enhanced.json
dify-db-backups/workflow-8216a411-graph-after.json
```

生成 Dify 增强 workflow graph 的脚本：

```text
scripts/enhance_dify_workflow_graph.py
```

## 当前已完成的能力

### 1. 网页和附件解析

`/analyze` 负责：

- 抓取公告网页正文。
- 提取标题、发布时间候选、地区候选。
- 发现附件链接。
- 解析 Word、Excel、PDF、CSV。
- 对大表做摘要化输出，避免证据包过长。
- 对新疆兵团 `https://gwt.xjbtylbz.cn/hallEnter/#/news/320` 这类 hash 路由做详情接口兜底。
- 对河南无附件短通知页面做正文区域优先提取。

注意：不要为了单个 URL 硬编码正文内容。已有逻辑是站点级/结构级适配。

### 2. ReportIR

Word 导出优先使用结构化 `ReportIR`：

```json
{
  "title": "",
  "suggested_filename": "",
  "notice_type": "",
  "publish_date": "",
  "source_agency": "",
  "document_name": "",
  "lead_paragraphs": [],
  "sections": [
    {
      "heading": "",
      "paragraphs": [],
      "tables": [
        {
          "title": "",
          "headers": [],
          "rows": [],
          "notes": []
        }
      ],
      "highlights": []
    }
  ],
  "enterprise_tips": [],
  "disclaimer": ""
}
```

`notice_type` 只作为内部分类和命名参考，不在 Word 正文显示。

### 3. Word 导出

Word 导出逻辑在 `app/main.py`。

特点：

- 根据 `report_ir.suggested_filename`、`title`、`document_name` 等自动命名。
- 中文文件名通过 `Content-Disposition: filename*=UTF-8''...` 支持下载。
- 清理 `<think>`、`analysis`、`scratchpad`、Dify 变量、Markdown 代码块、JSON 外壳。
- 只把正式报告写入 Word。
- 表格分主题渲染。
- 表头有底纹，表格边框清晰。
- 固定声明为最后一部分。
- 不写水印。

固定声明：

```text
声  明

本文基于互联网公开资料进行整理，目的在于传递分享信息，仅供读者参考之用。本网站不保证信息的准确性、有效性、及时性和完整性。本公司及其雇员一概毋须以任何方式就任何信息传递或传送的失误、不准确或错误，对用户或任何其他人士负任何直接或间接责任。在法律允许的范围内，本公司在此声明，不承担用户或任何人士就使用或未能使用本网站所提供的信息或任何链接所引致的任何直接、间接、附带、从属、特殊、惩罚性或惩戒性的损害赔偿。
```

### 4. 规则完整性

Prompt 和证据包会要求模型尽量保留以下规则，不要压缩成几句：

- 采购品种范围
- 产品分类
- 最高有效申报价
- 参考价
- 企业报价要求
- 有效报价
- 拟中选产品确定
- 中选产品确定
- 协议采购量
- 首年协议采购量
- 采购执行
- 价格联动
- 非中选产品管理
- 新获批产品管理
- 名词解释
- 信用评价
- 失信约束
- 取消中选资格
- 暂不予挂网

这套规则是通用要求，不是针对广东麻醉管路写死。

### 5. 历史知识

新增历史 Word 相关 prompt：

```text
prompts/report_history_prompt.md
```

规则：

- 历史分析稿只能用于历史对照、风格参考、项目延续性观察、企业关注点补充。
- 不得作为本次公告事实来源。
- 强制不新增“历史对照”“历史分析”等标题。
- 不得把历史 Word 中的规则、价格、周期、企业范围、产品范围、地区范围、采购量、时间节点误写成本次公告事实。
- 最多形成 1 段简短历史承接，并自然并入现有相关段落后半段。

当前正式入口已切换为本地 Dify advanced-chat 应用；旧 Workflow 仅保留为一次性 URL 分析兼容版本。

Chatflow 蓝本：

```text
dify-chatflow-medical-notice-report.yml
```

### 6. 多轮反馈修改

新增修订 prompt：

```text
prompts/report_revision_prompt.md
```

用于 Chatflow 后续消息：

- 基于原始证据。
- 基于当前 ReportIR。
- 基于当前 Markdown。
- 根据用户修改要求局部修订。
- 不允许脱离原文新增事实。

当前 Chatflow 已具备多轮会话状态、可选历史 Word 上传、用户反馈修订和确认后导出 Word 的基础编排。

### 7. 质检和自动修复

新增后端接口：

```text
POST /report/qa
POST /report/export_checked
```

新增 prompt：

```text
prompts/report_qa_prompt.md
prompts/report_qa_fix_prompt.md
```

质检 JSON 结构：

```json
{
  "status": "pass | needs_fix | block",
  "issues": [],
  "unsupported_claims": [],
  "history_leakage": [],
  "missing_rules": [],
  "language_issues": [],
  "fix_instructions": [],
  "summary": ""
}
```

后端会额外做轻量历史泄漏检查：

- 报告里出现 `历史对照`、`历史分析`、`历史知识` 等标题会标记。
- 历史稿中的价格、采购周期、日期、百分比等如果出现在报告中，但不在本次证据中，会标记。

`/report/export_checked` 行为：

- 如果质检阻断，返回 `success:false`、`blocked:true`、`qa_summary`，不生成 Word。
- 如果通过，才生成 Word 并返回下载链接。

## 当前 Dify 画布状态

用户当前 Dify 应用：

```text
app_id = a09ac7aa-3f49-4fc2-aea4-55471a3c6802
workflow_id = 8216a411-8690-42e7-932a-0d2c9a13fd76
```

该应用本来是 `workflow` 模式，有 7 个节点。

已经直接更新 Dify Postgres 草稿 workflow graph，增强后为 14 个节点：

- `Start`
- `抓取正文与附件`
- `生成采购分析报告`
- `报告质检`
- `构造质检解析参数`
- `解析质检结果`
- `质检修复`
- `二次质检`
- `构造二次质检解析参数`
- `解析二次质检结果`
- `构造 Word 导出参数`
- `质检通过后导出 Word`
- `提取正文并拼接下载链接`
- `End`

写回数据库后已重启：

```powershell
docker restart docker-api-1 docker-web-1 docker-api_websocket-1
```

如果 Dify UI 没显示新节点：

1. 在浏览器中 `Ctrl + F5` 强制刷新。
2. 重新进入应用 workflow 页面。
3. 如果仍不显示，检查数据库：

```powershell
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c "select graph like '%报告质检%' as has_qa, graph like '%export_checked%' as has_export_checked from workflows where id='8216a411-8690-42e7-932a-0d2c9a13fd76';"
```

应返回：

```text
has_qa = t
has_export_checked = t
```

## Dify 数据库连接信息

Postgres 容器：

```text
docker-db_postgres-1
```

数据库：

```text
dify
```

用户名：

```text
postgres
```

密码：

```text
difyai123456
```

常用命令：

```powershell
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c "\dt"
```

查看应用：

```powershell
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c "select id, name, mode, status from apps;"
```

查看 workflow：

```powershell
docker exec -e PGPASSWORD=difyai123456 docker-db_postgres-1 psql -U postgres -d dify -c "select id, type, version from workflows where app_id='a09ac7aa-3f49-4fc2-aea4-55471a3c6802';"
```

## 重要限制

1. 旧 Workflow 模式无法自然支持同一会话多轮修改和可选历史 Word 上传，因此仅作为兼容入口保留。
2. 正式入口为 `c0a278d7-e973-4c47-bb7f-9b2596e6648f` advanced-chat 应用。
3. Chatflow 已包含首轮生成、历史 Word 提炼、质检、用户反馈修订和确认后导出 Word。
4. 若需重新生成或更新 Chatflow，使用：

```text
scripts\import_dify_chatflow.ps1
scripts\build_dify_chatflow_dsl.py
dify-chatflow-medical-notice-report.yml
prompts/report_qa_prompt.md
prompts/report_qa_fix_prompt.md
```

## 最近测试覆盖

测试文件：

```text
tests/test_report_export.py
```

覆盖点：

- Word 不包含模型思考内容。
- Word 不包含 JSON、Dify 变量、水印。
- 固定声明存在。
- `notice_type` 不显示在 Word 正文。
- 文件名自动生成和非法字符清理。
- 表格行列安全处理。
- 新疆兵团 hash 路由解析。
- 河南短通知正文提取。
- 质检 JSON 解析。
- 质检 JSON 非法时阻断。
- 历史泄漏检测。
- `export_checked` 遇到历史泄漏不导出 Word。
- prompt 文件包含历史、修订、质检约束。

运行：

```powershell
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
```

最近结果：

```text
Ran 26 tests
OK
```

## 后续建议

如果继续当前 Workflow：

1. 刷新 Dify 页面，确认新增节点显示。
2. 用一个公告 URL 测试完整链路。
3. 若质检节点输出 JSON 不稳定，把模型 temperature 调低，并确认 prompt 只要求输出 JSON。

完整需求已通过 Chatflow 入口实现。维护或重建时：

1. 运行 `.\scripts\import_dify_chatflow.ps1` 创建或更新 Dify advanced-chat 应用。
2. 生成器会声明 `notice_url` 输入。
3. 生成器会声明可选 `history_report` 文件上传。
4. 生成器会增加 Dify 文档提取节点读取历史 Word。
5. 生成器会使用 `report_history_prompt.md` 生成 `history_insights`。
6. 设置会话变量：

```text
source_evidence
history_insights
current_report_ir
current_final_report
last_export_filename
last_qa_summary
```

7. 首轮走生成分支。
8. 后续用户消息走 `report_revision_prompt.md` 修订分支。
9. 每次生成/修订后走质检、一次修复、二次质检、导出。
