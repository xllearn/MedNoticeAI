# HANDOFF_FOR_NEW_CODEX_WINDOW_20260617

> 敏感信息文件：本文件包含公司服务器账号、数据库账号、Dify 账号/API Key。仅限本机 Codex 新窗口和公司内网联调使用，不要提交到 Git，不要发给外部人员，不要截图外传。

## 新窗口启动提示词

新开 Codex 窗口后，可以直接发送：

```text
请先阅读 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\HANDOFF_FOR_NEW_CODEX_WINDOW_20260617.md，然后继续维护当前已部署在公司服务器的医药公告采购分析报告项目。不要重新询问文档中已有的服务器、Dify、数据库、接口和部署信息。修改代码前先确认当前工作目录和服务状态。
```

## 当前项目定位

- 项目名称：医药公告采购分析报告 / medical-notice-analyzer
- 本地目录：`C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer`
- 公司服务器目录：`/opt/medical-notice-analyzer`
- 后端框架：FastAPI
- 入口文件：`app/main.py`
- 前端方式：FastAPI 静态 HTML 页面，无 React/Vue 构建系统
- 当前主要页面：
  - 选材页：`http://192.168.34.88:8099/records-ui`
  - 报告详情页：`http://192.168.34.88:8099/analysis-runs/{run_id}`
- 当前部署方式：Docker Compose
- 服务端口：`8099`

## 公司服务器信息

后端分析服务服务器：

```text
HOST=192.168.34.88
USER=root
PASSWORD=Elian@123
OS=Ubuntu
PROJECT_DIR=/opt/medical-notice-analyzer
SERVICE_URL=http://192.168.34.88:8099
```

常用命令：

```bash
ssh root@192.168.34.88
cd /opt/medical-notice-analyzer
docker compose ps
docker compose logs --tail=200 medical-notice-analyzer
docker compose build
docker compose up -d
docker compose exec -T medical-notice-analyzer python -m unittest discover -s tests -v
```

健康检查：

```text
GET http://192.168.34.88:8099/health
```

最近一次线上健康检查结果正常，返回 `status=ok`。

## Dify 信息

公司 Dify：

```text
DIFY_WEB_BASE=http://192.168.34.86
DIFY_API_BASE=http://192.168.34.86/v1
DIFY_LOGIN_EMAIL=admin@elian.net
DIFY_LOGIN_PASSWORD=Elian2025@
```

当前用于后端调用的 Dify Workflow API Key：

```text
DIFY_WORKFLOW_API_KEY=app-5tLw4yIOfzH1fODtBay8fzgA
```

当前新建并发布的 Dify Workflow 页面：

```text
http://192.168.34.86/app/d62ae6b9-ffe3-408d-bd1a-19cd80e508e0/workflow
```

旧工作流/历史信息，除非用户明确要求不要改：

```text
旧 Dify Workflow 页面：
http://192.168.34.86/app/b380094d-aa69-462e-a765-43d1afba862c/workflow

旧 Dify API Key：
app-rLv1IN7zQNzFdkGMpQKp2qXR
```

后端调用 Dify 的请求形态：

```json
{
  "inputs": {
    "pack_id": "pack_xxx"
  },
  "response_mode": "blocking",
  "user": "analysis_frontend"
}
```

请求头：

```text
Authorization: Bearer ${DIFY_WORKFLOW_API_KEY}
Content-Type: application/json
```

Dify 工作流内应通过 HTTP 节点请求后端：

```text
GET http://192.168.34.88:8099/analysis/packs/{{pack_id}}
```

注意：Dify 容器里不能用 `localhost` 指向后端，必须用公司服务器内网地址 `192.168.34.88:8099`。

## 数据库信息

数据库服务器：

```text
DB_HOST=192.168.36.36
DB_PORT=3306
DB_NAME=wangfanqi_test
DB_USER=wangfanqi
DB_PASSWORD=Elian#WfQ05*21
DB_CHARSET=utf8mb4
```

核心表：

```text
sample_article_wide
sample_article_attach
```

关联方式：

```sql
sample_article_wide.menu_code = sample_article_attach.menu_code
AND sample_article_wide.articleid = sample_article_attach.articleid
```

文章唯一标识必须使用：

```text
menu_code + articleid
```

不要只用 `articleid`。

## 当前核心功能状态

已经完成：

1. 数据库文章列表与筛选页面。
2. 主材料 1-3 条、辅助材料 0-10 条选择。
3. `/analysis/prepare` 根据选材生成 `evidence_pack`。
4. `/analysis/packs/{pack_id}` 供 Dify HTTP 节点读取证据包。
5. `/analysis/run` 后端代理调用 Dify，不暴露 API Key 到前端。
6. `/analysis-runs/{run_id}` 报告生成详情页，显示进度、报告预览、诊断、下载 Word、复制 Markdown。
7. 附件下载和解析默认开启，服务器在内网可直接访问附件下载接口。
8. 附件原文件不长期保存，只保存解析摘要 JSON 缓存。
9. 大 PDF 支持前若干页文本抽取和 OCR 兜底。
10. `.doc` 支持通过 LibreOffice headless 转换为 `.docx` 后解析；失败不阻断证据包。
11. 报告正文中的技术性说明已经清理，不应出现 OCR、元数据、未解析、资料说明等系统状态。
12. 若 Dify 返回片段报告，例如直接从“二、三、四”开始，后端会判定为片段并走保守兜底/人工确认。

## 当前主要接口

### 基础

```text
GET /health
GET /records-ui
GET /analysis-runs/{run_id}
```

### 数据库文章

```text
GET /records
GET /records/{menu_code}/{articleid}
POST /analysis/selection/preview
```

`GET /records` 参数：

```text
keyword
menu_code
areaname
projectphase
projecttype
start_date
end_date
page
page_size
```

### 证据包

```text
POST /analysis/prepare
GET /analysis/packs/{pack_id}
GET /analysis/packs/{pack_id}?full=true
GET /analysis/packs/{pack_id}/summary
GET /analysis/packs/{pack_id}/diagnostics
POST /analysis/cache/cleanup
```

`POST /analysis/prepare` 请求体示例：

```json
{
  "primary_materials": [
    {"menu_code": "xxx", "articleid": "xxx"}
  ],
  "auxiliary_materials": [
    {"menu_code": "xxx", "articleid": "xxx"}
  ],
  "force_refresh_attachments": false
}
```

`force_refresh_attachments=false` 时优先使用附件解析缓存，速度更快。

只有用户主动点击“重新解析附件并生成证据包”时才传：

```json
{"force_refresh_attachments": true}
```

### 报告生成

```text
POST /analysis/run
GET /analysis/runs/{run_id}
GET /analysis/runs/{run_id}/diagnostics
GET /analysis/runs/{run_id}/report
GET /analysis/runs/{run_id}/download
POST /analysis/runs/{run_id}/revise
```

`POST /analysis/run` 请求体：

```json
{
  "pack_id": "pack_xxx"
}
```

## 重要配置项

配置来自 `.env` 或服务器环境变量，不要把新密码/API Key 写死到代码里。

Dify：

```text
DIFY_BASE_URL=http://192.168.34.86/v1
DIFY_WORKFLOW_API_KEY=app-5tLw4yIOfzH1fODtBay8fzgA
DIFY_REPORT_WORKFLOW_ENDPOINT=/workflows/run
DIFY_RESPONSE_MODE=blocking
DIFY_USER=analysis_frontend
DIFY_TIMEOUT_SECONDS=600
```

附件：

```text
ENABLE_ATTACHMENT_DOWNLOAD=true
ENABLE_ATTACHMENT_PARSE=true
ATTACHMENT_DOWNLOAD_BASE_URL=https://qx.eliancloud.cn/Common/EmailFileDownLoad?AttID=
ATTACHMENT_TEMP_DIR=/tmp/medical_notice_attachments
ATTACHMENT_MAX_DOWNLOAD_MB=50
ATTACHMENT_MAX_PARSE_MB=30
ATTACHMENT_REQUEST_TIMEOUT=60
ATTACHMENT_COOKIE=
ATTACHMENT_HEADERS_JSON=
```

附件缓存：

```text
ENABLE_ATTACHMENT_PARSE_CACHE=true
ATTACHMENT_PARSE_CACHE_DIR=/app/data/attachment_parse_cache
ATTACHMENT_PARSE_CACHE_SUCCESS_TTL_DAYS=30
ATTACHMENT_PARSE_CACHE_FAILURE_TTL_MINUTES=10
ATTACHMENT_PARSE_CACHE_PARSE_FAILURE_TTL_MINUTES=30
ATTACHMENT_PARSE_CACHE_MAX_MB=500
ATTACHMENT_PARSE_CACHE_CLEANUP_ON_START=true
```

报告标注/反馈：

```text
ENABLE_ANALYSIS_HIGHLIGHT=true
ENABLE_USER_FEEDBACK_REVISION=true
```

## 附件解析能力

当前支持：

```text
PDF
DOCX
DOC
XLSX
XLSM
XLS
CSV
TXT
HTML/HTM
ZIP
```

`.doc` 处理方式：

1. 用 LibreOffice headless 转换 `.doc -> .docx`。
2. 复用 DOCX 解析逻辑。
3. 只使用临时目录。
4. 解析后删除临时文件和转换产物。
5. 失败时返回 `parse_failed` 或 `unsupported`，写入 warnings，不阻断报告生成。

PDF：

1. 先走文本抽取。
2. 对大 PDF 做前若干页抽取。
3. 如果文本抽取为空或极短，走 OCR 兜底。
4. OCR 依赖容器内的 `poppler-utils`、`tesseract-ocr`、`tesseract-ocr-chi-sim`、`tesseract-ocr-eng`。

Excel/CSV：

1. 不把全表塞进 Dify。
2. 生成 `table_summaries`：sheet 名、行数、列数、表头、关键列、业务摘要。
3. 识别企业、产品、注册证号、医保编码、价格、中选状态、采购量等关键列。

ZIP：

1. 有路径穿越防护。
2. 限制层级和大小。

## evidence_pack 设计

后端保存完整版本：

```text
evidence_pack_full
```

Dify 使用精简版本：

```text
evidence_pack_for_dify
```

原则：

1. 不直接字符串截断。
2. 不长期保存附件原文件。
3. 不把附件全文或 Excel 全表塞给 Dify。
4. 主材料正文和主材料关键事实优先保留。
5. 核心附件摘要和表格摘要优先保留。
6. 辅助材料优先压缩，只保留摘要、相关片段和对比点。
7. Dify compact 包尽量控制在 75000 字符以内，避免 Dify 变量 80000 字符限制。

诊断字段会显示：

```text
primary_content_chars
primary_attachment_summary_chars
auxiliary_content_chars
auxiliary_relevant_snippet_chars
raw_total_content_chars
dify_compact_pack_chars
weighted_evidence_chars
suggested_report_length
compression_applied
omitted_content
```

## 报告字数统计口径

曾经用户反馈：系统显示字数与 WPS 不一致。

当前做法：

1. 报告详情页和诊断应尽量使用 WPS-like visible word count。
2. 不应简单使用 Markdown 原始字符长度。
3. HTML span、Markdown 标记、表格符号、技术 JSON 不应计入用户看到的报告字数。

相关测试：

```text
test_run_diagnostics_uses_wps_like_visible_word_count
```

## 最近重点修复记录

### 1. 安庆市医疗服务价格项目通知

用户指定的问题材料：

```text
title=安徽省安庆市医疗保障局关于规范整合呼吸系统、神经系统等十二类医疗服务价格项目的通知
menu_code=ylsf
articleid=af562a9c-240e-4ea0-b1f1-feb9493327a2
```

问题：

1. 正文只有约 63 字。
2. 主要信息在一个约 39MB 的 PDF 附件中。
3. 早期报告只有 278 字或从第二节开始。
4. 报告正文出现 OCR、元数据、未解析、资料说明、识别错误等技术性说明。

已修：

1. 大 PDF 支持前若干页抽取和 OCR 兜底。
2. 该附件摘要进入主材料附件摘要统计。
3. 诊断显示附件主导：`ATTACHMENT_LED_PRIMARY_MATERIAL`。
4. 技术性说明从报告正文清理，只保留在诊断/warnings。
5. Dify 返回中间片段时，后端识别并触发兜底/人工确认。

最近线上验证：

```text
pack_id=pack_20260616_4d3e4eeb1d
run_id=run_20260616_3383e902c9
status=needs_manual_review
primary_content_chars=63
primary_attachment_summary_chars=4312
weighted_evidence_chars=3299
suggested_report_length=1000-1800字
report_chars_after_clean=1368
bad_terms=[]
```

`bad_terms=[]` 检查词包括：

```text
OCR
元数据
未解析
附件PDF因
资料说明
仅解析
metadata
系统未获取
解析失败
evidence_pack
Dify
识别错误
识别问题
正式文件为准
根据医学常识
暂无法确认
```

### 2. 技术性资料说明不应进入分析报告

用户明确要求：

```text
这类技术性资料说明应集中到诊断区，不要出现在分析报告里面
```

因此：

1. 报告正文不要出现“资料说明：附件仅解析到元数据层面”。
2. 报告正文不要出现“OCR识别可能存在误差”。
3. 报告正文不要出现“原文识别问题”“以正式文件为准”“根据医学常识修正”。
4. 这些内容放入 diagnostics、warnings、附件解析状态卡片。

相关代码：

```text
app/main.py
  _clean_model_output
  _strip_generated_material_note_sections
  _strip_technical_attachment_note_lines
  _is_fragmentary_dify_report_markdown
  _repair_unusable_dify_result
```

相关测试：

```text
tests/test_records_api.py
  test_clean_model_output_removes_technical_attachment_parse_notes
  test_clean_model_output_keeps_analysis_when_technical_note_is_same_line
  test_clean_model_output_removes_recognition_error_notes_in_tables
  test_clean_model_output_removes_source_recognition_problem_notes
  test_report_starting_from_second_section_is_treated_as_fragment
  test_fragmentary_dify_revision_gets_fallback_from_attachment_rich_pack
```

## Dify DSL 文件

项目内主要 DSL：

```text
dify_workflow_pack_id.yml
dify_workflow_pack_id_human_style.yml
dify_workflow_pack_id_manual_style.yml
```

最近建议使用：

```text
dify_workflow_pack_id_human_style.yml
```

注意：

1. 修改本地 DSL 不会自动更新 Dify UI。
2. 若修改 DSL，需要在 Dify UI 手动导入或通过 Dify API/脚本更新。
3. 每个 LLM 节点建议输出 JSON。
4. 后端仍有解析和兜底逻辑，防止模型偶发输出异常。

Dify 拓扑应保持：

```text
Start(pack_id)
-> HTTP 获取 evidence_pack
-> Generate Report JSON
-> Parse Generation JSON
-> Quality Check JSON
-> Parse Quality JSON
-> Quality Gate
-> Revise Report JSON
-> Parse Revision JSON
-> Second Quality Check JSON
-> Final Result
```

## 手工部署流程

本地打包，不包含 `.env`：

```powershell
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$archive = Join-Path $env:TEMP "medical-notice-analyzer_$ts.tar.gz"
tar --exclude='.env' --exclude='.venv' --exclude='.cache' --exclude='.pytest_cache' --exclude='reports' --exclude='site-cache' --exclude='dify-db-backups' --exclude='*.log' --exclude='tmp_report_compare.json' -czf $archive -C . .
Write-Output $archive
```

上传和部署可以用 Paramiko。密码是：

```text
Elian@123
```

示例：

```powershell
$env:DEPLOY_PASS = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('RWxpYW5AMTIz'))
$env:DEPLOY_ARCHIVE = 'C:\Users\admin\AppData\Local\Temp\medical-notice-analyzer_YYYYMMDD_HHMMSS.tar.gz'
$env:PYTHONIOENCODING='utf-8'
@'
import os, time, paramiko
from pathlib import Path

host='192.168.34.88'
user='root'
password=os.environ['DEPLOY_PASS']
archive=Path(os.environ['DEPLOY_ARCHIVE'])
remote_archive=f'/tmp/{archive.name}'
ts=time.strftime('%Y%m%d_%H%M%S')
project_dir='/opt/medical-notice-analyzer'

client=paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=user, password=password, timeout=20, look_for_keys=False, allow_agent=False)
try:
    sftp=client.open_sftp()
    sftp.put(str(archive), remote_archive)
    sftp.close()
    cmd=f"set -e; cd {project_dir}; mkdir -p deploy_backups; tar --exclude='./deploy_backups' --exclude='./.env' --exclude='./data' --exclude='./reports' --exclude='./.cache' --exclude='./.venv' -czf deploy_backups/code_before_{ts}.tar.gz .; tar -xzf {remote_archive} -C {project_dir}; rm -f {remote_archive}; docker compose build; docker compose up -d; docker compose ps"
    stdin, stdout, stderr=client.exec_command(cmd, get_pty=True, timeout=1200)
    for line in iter(stdout.readline, ''):
        print(line, end='')
    err=stderr.read().decode('utf-8', errors='replace')
    rc=stdout.channel.recv_exit_status()
    if err.strip():
        print(err)
    raise SystemExit(rc)
finally:
    client.close()
'@ | .\.venv\Scripts\python.exe -
```

部署后验证：

```powershell
$env:PYTHONIOENCODING='utf-8'
@'
import urllib.request
with urllib.request.urlopen('http://192.168.34.88:8099/health', timeout=30) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8'))
'@ | .\.venv\Scripts\python.exe -
```

服务器容器内跑关键测试：

```bash
cd /opt/medical-notice-analyzer
docker compose exec -T medical-notice-analyzer python -m unittest discover -s tests -v
```

## 最近测试状态

最近本地完整测试：

```text
Ran 123 tests
OK
```

最近服务器容器内关键回归：

```text
test_clean_model_output_removes_source_recognition_problem_notes ... ok
test_report_starting_from_second_section_is_treated_as_fragment ... ok
```

最近线上健康检查：

```text
GET http://192.168.34.88:8099/health
HTTP 200
status=ok
```

## 当前容易踩坑的点

1. 不要把 `.env`、数据库密码、Dify API Key、Cookie、服务器密码提交或打印到公开日志。
2. 前端绝不能直接调用 Dify，Dify API Key 只能在后端 `.env`。
3. Dify 中访问后端必须用 `http://192.168.34.88:8099`，不能用 `localhost`。
4. Dify DSL 文件在本地改完不会自动发布到 Dify UI。
5. 文章唯一标识必须是 `menu_code + articleid`。
6. 文章列表不能直接普通 JOIN 附件表，否则多附件文章会重复。
7. 附件原文件不要长期保存；只缓存解析摘要 JSON。
8. 大附件不要全文塞给 Dify，只放摘要、关键事实、表格结构。
9. 辅助材料不能反客为主，只用于背景、对比、补充。
10. 技术性说明不要进报告正文，集中到诊断区。
11. 如果 Dify 返回报告从第二节开始或明显很短，要检查 `_is_fragmentary_dify_report_markdown`。
12. 如果报告页面字数与 WPS 不一致，要检查 WPS-like visible word count，不要用 Markdown 原始长度。

## 常用真实测试材料

### 安庆测试材料

```text
title=安徽省安庆市医疗保障局关于规范整合呼吸系统、神经系统等十二类医疗服务价格项目的通知
menu_code=ylsf
articleid=af562a9c-240e-4ea0-b1f1-feb9493327a2
```

用途：

1. 测试正文很短但附件很重要的情况。
2. 测试大 PDF/OCR。
3. 测试技术性说明不进报告正文。
4. 测试 Dify 片段返回保护。

### 深圳/广东测试材料

用户曾指定：

```text
广东省深圳公共资源交易中心关于开展外周血管介入类医用耗材产品信息维护的通知
广东省深圳公共资源交易中心关于公布部分中选超声刀头产品注册证类别调整信息变更结果的通知（第四批）
```

用途：

1. 测试多个主材料。
2. 测试 DOC/DOCX/Excel 附件解析。
3. 测试报告内容覆盖度。

### 浙江辅助材料

用户曾指定：

```text
浙江省医疗保障局关于公布放射治疗、妇科、呼吸系统、耳鼻喉科、骨骼肌肉系统、心血管系统、神经系统、泌尿系统、体被系统和疝、甲乳等10类医疗服务价格项目及医保支付政策的通知
```

用途：

1. 测试辅助材料对比。
2. 测试辅助材料不反客为主。

## 用户偏好和产品要求

1. 用户希望报告“严格遵守原文内容，但仍有一定分析观点”。
2. 不要自由发挥或编造证据包外的信息。
3. 报告不是简单摘要，要有：规则梳理、影响分析、企业关注点、必要表格。
4. 主材料决定主题和主体内容。
5. 附件如果是核心附件，应尽量结构化解析并进入证据包。
6. 如果资料不足，应在诊断区提示，不要在正文里写技术说明。
7. 声明部分只保留原本 Word 最后一页的声明，不要在正文额外增加“资料说明”。
8. 重点内容可用红/蓝标注；分析性内容可用黄色标注测试模式。
9. 报告正文里不应出现 JSON、调试信息、Dify、evidence_pack、OCR、元数据等内部词。

## 如果新窗口要继续修改，建议先做

1. 打开本文件确认上下文。
2. 运行：

```powershell
cd C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

3. 查看服务：

```powershell
Invoke-WebRequest -UseBasicParsing http://192.168.34.88:8099/health
```

4. 如果要改部署代码，先在本地完成测试，再部署。
5. 如果要改 Dify 节点，必须确认是改 Dify UI 还是只改本地 DSL。

