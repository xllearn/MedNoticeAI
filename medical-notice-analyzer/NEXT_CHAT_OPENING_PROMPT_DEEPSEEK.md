请先读取：

```text
C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer\COMPANY_DIFY_DEEPSEEK_HANDOFF.md
```

后续只处理公司 Dify 应用和公司后端：

```text
公司 Dify：http://192.168.34.86
公司 Dify 应用：ad5e0bb6-e097-4697-91ac-9b1a2d01e10a
公司后端：http://192.168.34.88:8099
公司后端目录：/opt/medical-notice-analyzer
本地代码目录：C:\Users\admin\Documents\htmldataconclusion\medical-notice-analyzer
```

不要处理本地旧 Dify、旧 Workflow 或 localhost 应用，除非我明确要求。不要把 Dify 密码、SSH 密码、App API Key、access_token、refresh_token 写入任何文件或输出。

当前状态：

- 公司后端已部署并验证，`/health` 返回 `{"status":"ok"}`。
- 公司 Dify 发布态已切换为 DeepSeek：
  - `summarize_history` -> `deepseek-v4-flash`
  - `generate_report` -> `deepseek-v4-pro`
  - `qa_report_first` -> `deepseek-v4-flash`
  - `revise_report` -> `deepseek-v4-pro`
  - `qa_revised_report` -> `deepseek-v4-flash`
- DeepSeek 模型核对和链接测试结果目录：

```text
C:\Users\admin\Desktop\deepseek_link_test_20260610-090353
```

已完成 15 个链接中的 13 个测试，剩余未完成：

```text
http://ybj.gxzf.gov.cn/ztzl/ywzt/gxyyjghzbcgfwzxzl/tzgg/hccg/t27771226.shtml
http://www.ahyycg.cn/detail/categoryDetail.html?id=4366
```

请继续完成剩余 2 个链接测试：如果是 `needs_fix` 状态，把系统生成的修复建议作为用户输入继续修复，最多重复 3 次并记录修复次数；如果是爬取数据失败、block、API 错误或无可解析 QA 状态，只记录问题，不继续修复。测试结果继续写入：

```text
C:\Users\admin\Desktop\deepseek_link_test_20260610-090353
```

注意已有问题：

- 部分 DeepSeek 修复轮返回报告但 `质检摘要` 为空，已记录为 `qa_status_missing`。
- 这类情况不要继续自动修复，因为没有明确的系统修复建议。
- 后续可以单独修复 `qa_status_missing` 和 answer 模板中文乱码问题。
