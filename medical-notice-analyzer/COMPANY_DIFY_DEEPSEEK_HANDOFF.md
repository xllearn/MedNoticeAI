# 公司 Dify / DeepSeek 切换与测试交接

更新时间：2026-06-10 09:35（Asia/Shanghai）

## 范围

后续只处理公司环境：

- 公司 Dify：`http://192.168.34.86`
- 公司 Dify 应用：`ad5e0bb6-e097-4697-91ac-9b1a2d01e10a`
- 公司后端服务器：`192.168.34.88`
- 公司后端目录：`/opt/medical-notice-analyzer`
- 公司后端地址：`http://192.168.34.88:8099`
- 本地代码目录：`C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer`

不要处理本地旧 Dify、旧 Workflow 或 localhost 应用，除非用户明确要求。

不要把 Dify 登录密码、SSH 密码、Dify App API Key、公司站点 Cookie/Token 写入代码、交接文档、测试报告或终端输出。需要登录时让用户在当前对话临时提供。

## 当前已完成

### 后端

已部署到公司后端 `192.168.34.88:/opt/medical-notice-analyzer`。

后端部署备份：

```text
/opt/medical-notice-analyzer/dify-db-backups/codex-backup-20260609-164631
```

已验证：

```text
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
Ran 90 tests
OK
```

健康检查：

```text
http://192.168.34.88:8099/health
{"status":"ok"}
```

本地完整测试也通过：

```text
py -3.11 -m pytest -q
90 passed
```

### 后端关键修复

已修复兵团链接反复 `needs_fix` 的后端本地 QA 误判：

- 当报告写 `58元`，证据表头含 `价格（元）` 且同一产品行附近存在裸数字 `58` 时，认定为有证据。
- 不能只做连续字符串 `58元` 匹配。
- 对缺同一产品行、缺数值、跨产品拼接的情况仍会判 `needs_fix`。

相关文件：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\app\main.py
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\tests\test_report_quality.py
```

### Dify Chatflow 修复

已发布到公司 Dify 应用 `ad5e0bb6-e097-4697-91ac-9b1a2d01e10a`：

- QA payload 总上限 `MAX_PAYLOAD_CHARS = 110000`
- `evidence_text` 至少保留 `60000`
- `fetch_source` 的 `/analyze` 入参 `max_combined_chars = 60000`
- 新增 `repair_attempt_count`
- 新增 `repair_limit` 路由
- 连续 `needs_fix` 达到 3 次后停止继续要求用户粘贴同类修复建议
- 生成/修订/QA prompt 已增加价格单位等价、原始 Excel 口径、禁止自行统计等规则

相关文件：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\scripts\build_dify_chatflow_dsl.py
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\dify-chatflow-medical-notice-report.yml
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_user_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_revision_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_prompt.md
```

公司 Dify 发布前备份：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\dify-db-backups\company-dify-ad5e0bb6-e097-4697-91ac-9b1a2d01e10a-published-before-needs-fix-loop-20260609-170126.json
```

## DeepSeek 模型切换状态

2026-06-10 已确认：Draft 先由用户在 UI 改成 DeepSeek，但 Published 仍是旧 Qwen。随后已把 Draft 发布到 Published，并修正了一个参数：

- `revise_report.reasoning_effort` 补为 `high`
- `qa_revised_report.temperature` 从 `1` 修正为 `0`

发布态当前 LLM 节点应为：

| 节点 ID | 标题 | 模型 | 关键参数 |
| --- | --- | --- | --- |
| `summarize_history` | Summarize History | `deepseek-v4-flash` | temperature `0`, max_tokens `4096`, thinking `false` |
| `generate_report` | Generate Report | `deepseek-v4-pro` | temperature `0.1`, max_tokens `8192`, thinking `true`, reasoning_effort `high` |
| `qa_report_first` | QA Report | `deepseek-v4-flash` | temperature `0`, max_tokens `4096`, thinking `false` |
| `revise_report` | Revise Report | `deepseek-v4-pro` | temperature `0`, max_tokens `8192`, thinking `true`, reasoning_effort `high` |
| `qa_revised_report` | QA Revised Report | `deepseek-v4-flash` | temperature `0`, max_tokens `4096`, thinking `false` |

DeepSeek 发布与模型核对结果目录：

```text
C:\Users\admin\Desktop\deepseek_link_test_20260610-090353
```

该目录内重要文件：

```text
model_audit_before.json
model_audit_after.json
draft_before_param_fix.json
published_before.json
published_after.json
summary.json
summary.csv
url_XX_round_YY_*.md
```

## DeepSeek 链接测试当前进度

用户要求测试 15 个链接：

1. 河南：已测，`pass`，0 次修复，44.21 秒。
2. 兵团：已测，首轮 `needs_fix`，修复 2 次后返回报告但无可解析 QA 状态，记录 `qa_status_missing`，349.05 秒。
3. 深圳：已测，首轮 `needs_fix`，修复 2 次后返回报告但无可解析 QA 状态，记录 `qa_status_missing`，258.65 秒。
4. 甘肃：已测，`block`，检测到抓取/数据读取问题，按要求不修复，29.41 秒。
5. 贵州：已测，`block`，检测到抓取/数据读取问题，按要求不修复，23.26 秒。
6. 宁夏：已测，`pass`，0 次修复，102.99 秒。
7. 广东药交：已测，`block`，0 次修复，39.40 秒。
8. 吉林：已测，首轮 `needs_fix`，修复 2 次后返回报告但无可解析 QA 状态，记录 `qa_status_missing`，108.57 秒。
9. 江苏：已测，`pass`，0 次修复，114.07 秒。
10. 重庆：已测，`block`，0 次修复，72.45 秒。
11. 湖南：已测，`block`，检测到抓取/数据读取问题，按要求不修复，25.47 秒。
12. 广州 GPO：已测，`pass`，0 次修复，61.15 秒。
13. 湖北：已测，`pass`，0 次修复，26.95 秒。
14. 广西：未完成。
15. 安徽：未完成。

注意：第 9-13 个链接是在用户中断前已部分写入结果文件。后台 Python 测试进程已手动停止，避免继续消耗 Dify 调用。

已停止的进程：

```text
py.exe / python.exe，启动时间 2026-06-10 09:23:27
```

## 重要现象

DeepSeek 发布态存在一个新问题：部分修复轮返回正文，但答案尾部 `质检摘要` 为空，导致无法解析 `pass | needs_fix | block`。目前把这种情况记录为：

```text
problem_type = qa_status_missing
problem = No parseable QA status in final answer; stopped without repair.
```

这不是爬取失败，也不应继续自动修复，因为没有明确的系统生成修复建议。

可能原因：

- Dify answer 节点展示的 `conversation.last_qa_summary` 为空。
- `read_qa_*` 节点没有从 `/report/qa` 结果中读到 `qa_summary`。
- DeepSeek flash QA 输出格式不稳定，导致 `/report/qa` 解析后没有摘要。
- 中文 answer 模板在 Dify 1.2 中存在乱码，但变量仍可用；状态解析应优先读 `summary.json` 中每轮保存的 answer 文件。

## 下一步建议

1. 先继续完成未测的 2 个链接：

```text
http://ybj.gxzf.gov.cn/ztzl/ywzt/gxyyjghzbcgfwzxzl/tzgg/hccg/t27771226.shtml
http://www.ahyycg.cn/detail/categoryDetail.html?id=4366
```

2. 然后优先修复 `qa_status_missing`：

- 检查 Dify 发布图中 `read_qa_first` / `read_qa_revised` 的输入是否仍指向 `parse_qa_first.body` / `parse_qa_revised.body`。
- 检查 `/report/qa` 返回体是否在 DeepSeek QA 输出为空或非 JSON 时仍返回 `qa_summary`。
- 建议在 `answer_initial` / `answer_revised` 中额外展示 `read_qa_*.qa_status` 或 `read_qa_*.qa_body` 的简短兜底摘要，避免 QA 摘要为空。
- 或新增一个 code 节点：如果 `qa_summary` 为空但 `qa_status` 为空，则标记为 `block` 或 `qa_parse_missing`，不要让前端显示无状态报告。

3. 对乱码问题另开任务处理：

- 当前 answer 模板中中文在本地生成器里显示为乱码，线上回答也出现乱码。
- 需要检查 `scripts/build_dify_chatflow_dsl.py` 里的中文字符串是否被错误编码保存。
- 这个问题会影响用户可读性，但不影响当前模型节点和后端测试主体结论。

## 手动正文降级方案

用户问过：爬取失败时是否可以允许用户复制网页正文输入后分析生成。

答案：可以。

建议实现为明确降级入口：

- 用户粘贴正文时标记为 `manual_user_evidence`。
- 报告只基于用户粘贴正文生成。
- 如果附件未抓取或无法核验，必须写“附件读取失败/无法核验”。
- 不允许生成具体附件价格、型号统计、产品条目数等无法从粘贴正文核验的事实。

## 常用验证命令

本地：

```powershell
cd C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
py -3.11 -m pytest -q
```

后端健康：

```powershell
Invoke-WebRequest -UseBasicParsing -Uri http://192.168.34.88:8099/health
```

远程容器测试需要 SSH 登录公司后端服务器，凭据由用户在当前对话临时提供，不要写入文件。

## 安全提醒

不要在任何文件或最终回复中暴露：

- 公司 Dify 登录密码
- SSH 密码
- Dify App API Key
- Dify access_token / refresh_token
- 公司站点 Cookie / Token

