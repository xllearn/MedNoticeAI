# 公司 Dify 与后端服务交接文档

更新时间：2026-06-09

## 新会话第一约束

后续只处理公司服务器上的 Dify 应用和公司后端服务：

- 公司 Dify：`http://192.168.34.86`
- 公司 Dify 新建应用：`ad5e0bb6-e097-4697-91ac-9b1a2d01e10a`
- 公司后端服务器：`192.168.34.88`
- 公司后端服务目录：`/opt/medical-notice-analyzer`
- 公司后端服务地址：`http://192.168.34.88:8099`

不要再处理本地 Dify、旧 Workflow 或本地 localhost 应用，除非用户明确要求。当前本地项目目录只作为代码蓝本、测试脚本和交接资料来源。

不要把账号密码、API Key、Dify App Token 写入代码、测试报告或交接文档。新会话如需登录或部署，由用户重新提供凭据，或在已授权环境中临时使用。

## 新会话开场白

新开 Codex 会话后，可以直接发送：

```text
请先读取 C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\COMPANY_SERVER_HANDOFF.md。

后续只修改公司 Dify 应用 ad5e0bb6-e097-4697-91ac-9b1a2d01e10a 和公司后端服务 192.168.34.88:/opt/medical-notice-analyzer，不再处理本地 Dify、旧 Workflow 或 localhost 应用，除非我明确要求。

如果需要改代码，先说明会影响公司后端还是公司 Dify；如果需要测试，优先在公司 Dify 和公司后端上验证。
```

## 当前已部署状态

公司后端已部署为独立 Python 服务镜像，监听 `8099`。

最近验证：

```text
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
Ran 79 tests
OK
```

健康检查：

```text
curl http://127.0.0.1:8099/health
{"status":"ok"}
```

公司 Dify 新应用已发布，HTTP 节点指向：

```text
http://192.168.34.88:8099
```

当前模型选择：

```text
主生成/修订模型：langgenius/tongyi/tongyi / qwen3-max-2025-09-23
快速质检/历史总结模型：langgenius/tongyi/tongyi / qwen-plus-latest
```

原因：公司 Dify 当前可用模型里，Tongyi 供应商已验证可运行；`qwen3-max` 曾在江苏测试中出现长时间超时，已切换为稳定的 `qwen3-max-2025-09-23`。

## 已完成的关键修复

1. 抓取失败不再硬中断 Dify 流程

- `/analyze` 抓网页失败时，不再直接返回 502 让 Dify HTTP 节点失败。
- 会返回带 `crawl_insufficient` 标记的证据包。
- 甘肃这类源站返回 `412 Precondition Failed` 时，系统会生成“抓取不足”说明并记录问题。

相关代码：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\app\main.py
```

关键位置：

```text
公告网页抓取失败 -> warnings 加入 抓取状态: crawl_insufficient
修正后的公告网页抓取失败 -> warnings 加入 抓取状态: crawl_insufficient
```

2. 公司站点适配

已新增公司器械集采准入系统 URL 适配：

```text
qx.eliancloud.cn/zly/...projectInformationArticleContent?articleid=...
```

支持从环境变量读取登录态：

```text
ELIAN_QX_TOKEN
ELIAN_QX_COOKIE
```

如果公司站点需要验证码、SSO 或浏览器人工登录，不做绕过，系统应返回 `login_required` 或 `crawl_insufficient`。

3. Payload 长度控制

- `/analyze` 证据预算降到 Dify 安全范围：`max_combined_chars=60000`。
- QA/export payload 构建节点增加二次截断，目标上限约 `76000` 字符。
- 这是为了解决兵团类 `payload > 80000` 的 Dify 节点变量长度问题。

4. 质检不阻断 Word 下载

当前业务规则：

- 质检接口只提出缺陷和修复建议。
- 用户明确确认下载 Word 后，质检缺陷不应阻断导出。
- 只有没有可导出的有效 `ReportIR`、ReportIR 解析失败、没有上一版有效报告这类硬错误，才不能导出 Word。

5. 修订失败回退

用户把质检缺陷复制为反馈后：

- 系统应进入修订分支。
- 如果本轮修订模型输出失败或 ReportIR 解析失败，不能覆盖上一版有效报告。
- 确认下载时使用最新有效 `current_report_ir`。

6. 流程/挂网操作类报告深度

河南这类流程调整/挂网操作调整公告，不能只输出摘要。至少应包含：

- 调整内容
- 影响分析
- 企业关注点/操作建议

不强行扩写成复杂采购文件，但正文不能过短。

## 最近 10 条 URL 验收结果

测试输出目录：

```text
C:\Users\admin\Desktop\公司Dify修复后全量测试_20260608-173034
```

汇总文件：

```text
C:\Users\admin\Desktop\公司Dify修复后全量测试_20260608-173034\测试汇总.csv
C:\Users\admin\Desktop\公司Dify修复后全量测试_20260608-173034\测试汇总.json
```

结果摘要：

```text
1 河南：pass，0 轮修复，已下载 Word
2 兵团：2 轮修复后 pass，已下载 Word
3 深圳广东麻醉：pass，0 轮修复，已下载 Word
4 甘肃：crawl_insufficient，源站返回 412，未下载 Word
5 贵州：crawl_insufficient，动态页面/登录态不足，未下载 Word
6 宁夏：pass，0 轮修复，已下载 Word
7 广东骨科：2 轮修复后 pass，已下载 Word
8 吉林：pass，0 轮修复，已下载 Word
9 江苏：3 轮修复后仍 needs_fix，但已按非阻断规则下载 Word
10 重庆：pass，0 轮修复，已下载 Word
```

总体：

```text
10 条 URL 中 8 条成功下载 Word。
甘肃、贵州属于抓取不足，不是导出链路失败。
江苏仍有质检闭环优化空间，但 Word 已能导出。
```

## 当前已知问题

1. 甘肃

URL：

```text
https://ylbz.gansu.gov.cn/ylbzj/c107125/202606/174341234.shtml
```

现象：

```text
源站返回 412 Precondition Failed。
```

当前处理：

```text
记录为 crawl_insufficient，不让 Dify 流程硬失败。
```

后续如果要真正生成分析，需要更换可访问原文、提供附件，或使用可通过源站校验的访问方式。

2. 贵州

URL：

```text
https://fuwu.pubs.ylbzj.guizhou.gov.cn/hsa-pass-hallEnter/index.html#/announcementDetail?type=5&cont=%5Bobject%20Object%5D&artContId=2060175820995837953
```

现象：

```text
公网 hash 页面只返回平台壳，未取得公告正文。
```

当前处理：

```text
记录为 crawl_insufficient。
```

如果改用公司站点链接并且需要登录，应由用户提供可用登录态。优先使用 `ELIAN_QX_TOKEN` 或 `ELIAN_QX_COOKIE`，不要把凭据写入代码。

3. 江苏

现象：

```text
修复 3 轮后仍 needs_fix，但 Word 已下载。
```

判断：

```text
这是质检修订闭环和本地规则提示仍需优化的问题，不是导出链路问题。
```

后续可优先优化：

- 修订 prompt 的 checklist 执行能力。
- 本地 QA 对“专项治理/价格核查类公告”的结构要求。
- 对已经多轮无法修复的问题降级为提示，避免重复修复。

4. Dify HTTP retry 限制

DSL 里已给 HTTP 节点配置 retry，但部分 Dify 运行错误仍显示 `maximum retries (0)`。因此更可靠的策略是在后端把可预期的抓取失败降级为 `crawl_insufficient`，不要让 HTTP 节点收到 502。

## 后续修改原则

1. 只更新公司新应用

目标应用：

```text
ad5e0bb6-e097-4697-91ac-9b1a2d01e10a
```

不要改本地旧 Workflow，不要改本地 Dify 的旧应用，除非用户明确要求。

2. 后端优先部署到公司服务器

目标目录：

```text
/opt/medical-notice-analyzer
```

后端服务：

```text
medical-notice-analyzer
```

典型部署验证命令：

```bash
cd /opt/medical-notice-analyzer
docker compose up -d --build
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
curl -sS http://127.0.0.1:8099/health
```

3. 本地项目只作为代码源

本地路径：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
```

如果在本地改代码，改完要同步到公司服务器并重建容器。不要只在本地验证后就认为公司环境已更新。

4. 先验证后宣称完成

每次后端改动后至少验证：

```text
docker exec medical-notice-analyzer python -m unittest discover -s tests -v
curl -sS http://127.0.0.1:8099/health
```

每次 Dify 改动后至少验证：

- 公司 Dify 应用已发布。
- HTTP 节点仍指向 `http://192.168.34.88:8099`。
- 模型 provider/model 不为空。
- 首轮生成、用户反馈修订、确认下载 Word 三条分支都能跑。

## 关键本地文件

后端主文件：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\app\main.py
```

Chatflow DSL 生成：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\scripts\build_dify_chatflow_dsl.py
```

Chatflow 蓝本：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\dify-chatflow-medical-notice-report.yml
```

关键 prompt：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_user_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_revision_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_prompt.md
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\prompts\report_qa_fix_prompt.md
```

关键测试：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\tests\test_report_export.py
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\tests\test_report_quality.py
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\tests\test_chatflow_blueprint.py
```

## 下次最可能继续做的工作

1. 优化江苏这类“多轮修复仍 needs_fix”的质检闭环。
2. 如果用户提供公司站点登录态，继续增强贵州/公司站点公告正文抓取。
3. 重新跑 10 条 URL，全量记录修复轮次、最终 QA 状态、是否下载 Word。
4. 优化耗时：优先压缩证据包、让 QA/历史总结用快速模型，生成节点保持质量模型。
5. 对公司 Dify 发布图做再次核验，确认没有节点回退到本地地址或失效模型。

## 安全提醒

不要在交接文档、测试报告、代码、prompt 或终端输出中展示：

- 公司 Dify 登录密码
- SSH 密码
- Dify App API Key
- 公司站点 Cookie
- 公司站点 Token

如果新会话需要这些信息，直接让用户临时提供，或从已授权的安全位置读取。
