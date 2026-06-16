from __future__ import annotations

import csv
import io
import os
import re
import zipfile
from html.parser import HTMLParser
from typing import Any

import xlrd
from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader


KEY_COLUMN_PATTERNS = [
    "企业名称",
    "产品名称",
    "注册证号",
    "医保编码",
    "规格型号",
    "申报价",
    "中选价",
    "采购量",
    "地区",
    "分组",
    "分类",
]


def _contains_any(headers: list[str], keywords: list[str]) -> bool:
    text = " ".join(str(header or "") for header in headers)
    return any(keyword in text for keyword in keywords)


def _business_table_flags(headers: list[str]) -> dict[str, bool]:
    return {
        "contains_enterprise": _contains_any(headers, ["企业", "申报企业", "生产企业", "配送企业"]),
        "contains_product": _contains_any(headers, ["产品", "耗材", "品名", "通用名"]),
        "contains_registration_cert": _contains_any(headers, ["注册证", "备案号"]),
        "contains_medical_insurance_code": _contains_any(headers, ["医保编码", "医保耗材代码", "医保代码"]),
        "contains_specification": _contains_any(headers, ["规格", "型号", "规格型号"]),
        "contains_price": _contains_any(headers, ["价格", "报价", "申报价", "中选价", "挂网价"]),
        "contains_selected_status": _contains_any(headers, ["中选", "拟中选", "入围", "挂网状态", "状态"]),
        "contains_purchase_volume": _contains_any(headers, ["采购量", "报量", "需求量", "约定采购量"]),
    }


def _float_env(name: str, default: float) -> float:
    try:
        return float((os.getenv(name) or "").strip() or default)
    except ValueError:
        return default


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text


def _summary_from_text(text: str, limit: int = 600) -> str:
    clean = _clean_text(text)
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "..."


def _extract_key_facts(text: str) -> list[dict[str, str]]:
    clean = _clean_text(text)
    facts: list[dict[str, str]] = []
    for pattern, label in [
        (r"\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}", "时间"),
        (r"(?:申报|报价|采购|执行|递交).{0,30}(?:时间|截止|周期|要求)", "要求"),
        (r"(?:价格|报价|申报价|中选价).{0,40}", "价格规则"),
        (r"(?:企业|医疗机构|产品|注册证|医保编码).{0,40}", "主体/产品"),
    ]:
        for match in re.finditer(pattern, clean):
            value = match.group(0).strip()
            if value and all(item["value"] != value for item in facts):
                facts.append({"name": label, "value": value})
            if len(facts) >= 10:
                return facts
    return facts


class _HTMLTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        clean = _clean_text(data)
        if clean:
            self.parts.append(clean)


def _parse_docx(content: bytes) -> tuple[str, list[dict[str, Any]]]:
    doc = Document(io.BytesIO(content))
    parts: list[str] = [paragraph.text for paragraph in doc.paragraphs if _clean_text(paragraph.text)]
    table_summaries: list[dict[str, Any]] = []
    for index, table in enumerate(doc.tables, start=1):
        rows = [[_clean_text(cell.text) for cell in row.cells] for row in table.rows]
        if not rows:
            continue
        headers = rows[0]
        table_summaries.append(
            {
                "sheet_name": f"表格{index}",
                "rows": len(rows),
                "columns_count": len(headers),
                "headers": headers,
                "key_columns": _key_columns(headers),
                "sample_rows_count": max(0, min(len(rows) - 1, 20)),
                "summary": f"该表包含 {len(rows)} 行、{len(headers)} 列，表头包括：{', '.join(headers[:8])}。",
                "business_value": "可用于补充附件中的结构化规则或清单信息。",
                **_business_table_flags(headers),
            }
        )
        for row in rows[:10]:
            parts.append(" | ".join(row))
    return "\n".join(parts), table_summaries


def _key_columns(headers: list[str]) -> list[str]:
    result = []
    for header in headers:
        if any(pattern in str(header) for pattern in KEY_COLUMN_PATTERNS):
            result.append(str(header))
    return result


def _parse_xlsx(content: bytes) -> list[dict[str, Any]]:
    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    summaries: list[dict[str, Any]] = []
    for ws in wb.worksheets:
        rows_iter = ws.iter_rows(values_only=True)
        headers = [str(value or "").strip() for value in next(rows_iter, [])]
        sample_count = 0
        for _ in rows_iter:
            sample_count += 1
            if sample_count >= 20:
                break
        rows = ws.max_row or sample_count
        columns = ws.max_column or len(headers)
        key_columns = _key_columns(headers)
        summaries.append(
            {
                "sheet_name": ws.title,
                "rows": rows,
                "columns_count": columns,
                "headers": headers,
                "key_columns": key_columns,
                "sample_rows_count": sample_count,
                "summary": f"该表主要包含 {rows} 行、{columns} 列，关键字段包括：{', '.join(key_columns or headers[:6])}。",
                "business_value": "可用于分析产品范围、企业申报口径、价格字段或采购清单结构。",
                **_business_table_flags(headers),
            }
        )
    return summaries


def _parse_xls(content: bytes) -> list[dict[str, Any]]:
    book = xlrd.open_workbook(file_contents=content)
    summaries: list[dict[str, Any]] = []
    for sheet in book.sheets():
        headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)] if sheet.nrows else []
        key_columns = _key_columns(headers)
        summaries.append(
            {
                "sheet_name": sheet.name,
                "rows": sheet.nrows,
                "columns_count": sheet.ncols,
                "headers": headers,
                "key_columns": key_columns,
                "sample_rows_count": min(max(sheet.nrows - 1, 0), 20),
                "summary": f"该表主要包含 {sheet.nrows} 行、{sheet.ncols} 列，关键字段包括：{', '.join(key_columns or headers[:6])}。",
                "business_value": "可用于分析产品范围、企业申报口径、价格字段或采购清单结构。",
                **_business_table_flags(headers),
            }
        )
    return summaries


def _parse_csv(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    headers = [str(value).strip() for value in rows[0]] if rows else []
    key_columns = _key_columns(headers)
    return [
        {
            "sheet_name": "CSV",
            "rows": len(rows),
            "columns_count": len(headers),
            "headers": headers,
            "key_columns": key_columns,
            "sample_rows_count": min(max(len(rows) - 1, 0), 20),
            "summary": f"该 CSV 包含 {len(rows)} 行、{len(headers)} 列，关键字段包括：{', '.join(key_columns or headers[:6])}。",
            "business_value": "可用于分析清单类结构化信息。",
            **_business_table_flags(headers),
        }
    ]


def _parse_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    texts = []
    for page in reader.pages[:50]:
        texts.append(page.extract_text() or "")
    return "\n".join(texts)


def _parse_zip(content: bytes, filename: str) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    child_summaries: list[dict[str, Any]] = []
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        total = 0
        for info in archive.infolist()[:20]:
            if info.is_dir():
                continue
            if ".." in info.filename.replace("\\", "/").split("/"):
                warnings.append(f"ZIP 内文件存在路径穿越风险，已跳过: {info.filename}")
                continue
            total += info.file_size
            if total > int(_float_env("ATTACHMENT_MAX_PARSE_MB", 30) * 1024 * 1024):
                warnings.append("ZIP 内文件总大小超过解析限制，已截断处理")
                break
            child = parse_attachment_bytes(archive.read(info), info.filename, os.path.splitext(info.filename)[1], info.file_size)
            child_summaries.append(
                {
                    "filename": info.filename,
                    "summary": child.get("summary", ""),
                    "parse_statuses": child.get("parse_statuses", []),
                    "table_summaries": child.get("table_summaries", []),
                }
            )
    return child_summaries, warnings


def parse_attachment_bytes(content: bytes, filename: str, fileext: str, filesize: int | str | None = None) -> dict[str, Any]:
    ext = (fileext or os.path.splitext(filename)[1] or "").lower()
    size = int(filesize or len(content) or 0)
    max_parse_bytes = int(_float_env("ATTACHMENT_MAX_PARSE_MB", 30) * 1024 * 1024)
    warnings: list[str] = []
    parse_statuses: list[str] = []
    text = ""
    table_summaries: list[dict[str, Any]] = []
    important_sections: list[str] = []

    if size > max_parse_bytes:
        return {
            "parse_statuses": ["too_large_summary_only"],
            "text_length": 0,
            "summary": f"附件大小 {size} 字节，超过解析限制，仅保留元数据和结构信息。",
            "key_facts": [],
            "important_sections": [],
            "table_summaries": [],
            "warnings": ["附件超过最大解析大小限制"],
        }

    try:
        if ext == ".pdf":
            text = _parse_pdf(content)
            parse_statuses.append("parsed_text")
        elif ext == ".docx":
            text, table_summaries = _parse_docx(content)
            parse_statuses.append("parsed_text")
            if table_summaries:
                parse_statuses.append("parsed_table_summary")
        elif ext == ".doc":
            return {
                "parse_statuses": ["unsupported"],
                "text_length": 0,
                "summary": "DOC 格式暂未启用解析。",
                "key_facts": [],
                "important_sections": [],
                "table_summaries": [],
                "warnings": ["DOC 格式暂不支持"],
            }
        elif ext in {".xlsx", ".xlsm"}:
            table_summaries = _parse_xlsx(content)
            parse_statuses.append("parsed_table_summary")
        elif ext == ".xls":
            table_summaries = _parse_xls(content)
            parse_statuses.append("parsed_table_summary")
        elif ext == ".csv":
            table_summaries = _parse_csv(content)
            text = content.decode("utf-8-sig", errors="replace")[:5000]
            parse_statuses.extend(["parsed_text", "parsed_table_summary"])
        elif ext in {".txt", ".text"}:
            text = content.decode("utf-8", errors="replace")
            parse_statuses.append("parsed_text")
        elif ext in {".html", ".htm"}:
            parser = _HTMLTextParser()
            parser.feed(content.decode("utf-8", errors="replace"))
            text = "\n".join(parser.parts)
            parse_statuses.append("parsed_text")
        elif ext == ".zip":
            children, zip_warnings = _parse_zip(content, filename)
            warnings.extend(zip_warnings)
            table_summaries = [summary for child in children for summary in child.get("table_summaries", [])]
            text = "\n".join(child.get("summary", "") for child in children)
            parse_statuses.append("parsed_summary")
            if table_summaries:
                parse_statuses.append("parsed_table_summary")
        else:
            return {
                "parse_statuses": ["unsupported"],
                "text_length": 0,
                "summary": f"{ext or '未知'} 格式暂不支持解析。",
                "key_facts": [],
                "important_sections": [],
                "table_summaries": [],
                "warnings": ["附件格式暂不支持"],
            }
    except Exception as exc:  # noqa: BLE001
        return {
            "parse_statuses": ["parse_failed"],
            "text_length": 0,
            "summary": "附件解析失败。",
            "key_facts": [],
            "important_sections": [],
            "table_summaries": [],
            "warnings": [f"附件解析失败: {exc.__class__.__name__}"],
        }

    if table_summaries and not text:
        summary = "；".join(item.get("summary", "") for item in table_summaries[:3])
    else:
        summary = _summary_from_text(text)
    if summary and "parsed_summary" not in parse_statuses:
        parse_statuses.append("parsed_summary")
    important_sections = [line for line in re.split(r"[。；;\n]", _clean_text(text)) if any(word in line for word in ["申报", "价格", "采购", "企业", "产品", "执行"])][:8]
    return {
        "parse_statuses": parse_statuses or ["metadata_only"],
        "text_length": len(_clean_text(text)),
        "summary": summary,
        "key_facts": _extract_key_facts(text),
        "important_sections": important_sections,
        "table_summaries": table_summaries,
        "warnings": warnings,
    }
