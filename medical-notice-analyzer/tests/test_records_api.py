from __future__ import annotations

import os
import tempfile
import time
import unittest
import json
from unittest.mock import patch

from docx import Document
from docx.oxml.ns import qn
from fastapi.testclient import TestClient
from openpyxl import Workbook

import app.main as main_module
from app.attachment_fetcher import AttachmentDownloadResult, build_attachment_auth_headers, fetch_attachment_bytes
from app.attachment_parser import parse_attachment_bytes


def list_row(**overrides):
    row = {
        "menu_code": "m1",
        "articleid": "a1",
        "title": "Stent procurement notice",
        "audittime": "2026-06-01 10:00:00",
        "menu_name": "Procurement",
        "areaname": "山东",
        "source": "Source",
        "publicorg": "Agency",
        "projectphase": "申报",
        "projecttype": "耗材",
        "category": "医用耗材",
        "sourceurl": "https://example.com/a1",
        "summary": "summary",
        "attachment_count": 2,
        "list_attach_filename": "first.docx",
    }
    row.update(overrides)
    return row


def detail_row(**overrides):
    row = {
        **list_row(),
        "updatetime": "2026-06-02 10:00:00",
        "dl_project_type": "带量",
        "referencenumber": "REF-1",
        "policytype": "policy",
        "belongproject": "project",
        "projectabbreviation": "abbr",
        "content": "<h1>公告标题</h1><script>bad()</script><p>申报时间为2026年6月1日。</p><table><tr><td>价格规则</td></tr></table>",
    }
    row.update(overrides)
    return row


def attachment_row(**overrides):
    row = {
        "articleattid": "att1",
        "filename": "file.docx",
        "filepath": "/files/file.docx",
        "fileext": ".docx",
        "filesize": 1234,
        "uploadtime": "2026-06-01 11:00:00",
        "sortnum": 1,
        "fileerrortype": "",
    }
    row.update(overrides)
    return row


def wait_until(predicate, timeout: float = 2.0):
    deadline = time.time() + timeout
    last_value = None
    while time.time() < deadline:
        last_value = predicate()
        if last_value:
            return last_value
        time.sleep(0.02)
    return last_value


class RecordsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main_module.app)

    def test_records_list_filters_paginates_and_omits_content(self) -> None:
        calls = []

        def fake_fetch_one(sql: str, params: list[object]):
            calls.append(("one", sql, params))
            return {"total": 2}

        def fake_fetch_all(sql: str, params: list[object]):
            calls.append(("all", sql, params))
            return [
                list_row(articleid="a1", title="Stent A"),
                list_row(articleid="a2", title="Stent B", attachment_count=0),
            ]

        with patch.object(main_module, "_db_fetch_one", fake_fetch_one, create=True), patch.object(
            main_module, "_db_fetch_all", fake_fetch_all, create=True
        ):
            response = self.client.get(
                "/records",
                params={
                    "keyword": "stent",
                    "menu_code": "menu-01",
                    "areaname": "山东",
                    "projectphase": "申报",
                    "projecttype": "耗材",
                    "start_date": "2026-06-01",
                    "end_date": "2026-06-30",
                    "page": 2,
                    "page_size": 20,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["page"], 2)
        self.assertEqual(body["page_size"], 20)
        self.assertEqual(body["total"], 2)
        self.assertEqual(body["total_pages"], 1)
        self.assertEqual(len(body["items"]), 2)
        self.assertNotIn("content", body["items"][0])

        list_sql = calls[1][1]
        list_params = calls[1][2]
        self.assertIn("a.status = %s", list_sql)
        self.assertIn("LEFT JOIN", list_sql)
        self.assertIn("GROUP BY", list_sql)
        self.assertIn("ORDER BY a.audittime DESC", list_sql)
        self.assertIn("LIMIT %s OFFSET %s", list_sql)
        self.assertIn("%stent%", list_params)
        self.assertEqual(list_params[-2:], [20, 20])

    def test_records_ui_serves_static_page(self) -> None:
        response = self.client.get("/records-ui")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn("数据库文章选材", response.text)
        self.assertIn("/analysis/prepare", response.text)
        self.assertIn("/analysis/run", response.text)
        self.assertIn("run-analysis-report", response.text)
        self.assertNotIn("enableAttachmentDownload", response.text)
        self.assertNotIn("attachmentCookie", response.text)
        self.assertNotIn("attachmentHeadersJson", response.text)
        self.assertIn("复制 pack_id", response.text)
        self.assertIn("查看证据包摘要", response.text)
        self.assertNotIn("查看完整 evidence_pack</a>", response.text)

    def test_records_list_tolerates_nullable_optional_fields(self) -> None:
        with patch.object(main_module, "_db_fetch_one", return_value={"total": 1}, create=True), patch.object(
            main_module,
            "_db_fetch_all",
            return_value=[list_row(projectphase=None, list_attach_filename=None, attachment_count=None)],
            create=True,
        ):
            response = self.client.get("/records?page=1&page_size=5")

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["projectphase"], "")
        self.assertEqual(item["list_attach_filename"], "")
        self.assertEqual(item["attachment_count"], 0)

    def test_record_detail_returns_clean_text_and_attachments(self) -> None:
        def fake_fetch_one(sql: str, params: list[object]):
            self.assertIn("sample_article_wide", sql)
            self.assertEqual(params, [0, "m1", "a1"])
            return {
                **list_row(),
                "updatetime": "2026-06-02 10:00:00",
                "dl_project_type": "带量",
                "referencenumber": "REF-1",
                "policytype": "policy",
                "belongproject": "project",
                "projectabbreviation": "abbr",
                "content": "<h1>Title</h1><p>Hello <b>world</b></p>",
            }

        def fake_fetch_all(sql: str, params: list[object]):
            self.assertIn("sample_article_attach", sql)
            self.assertEqual(params, ["m1", "a1"])
            return [
                {
                    "articleattid": "att1",
                    "filename": "file.docx",
                    "filepath": "/files/file.docx",
                    "fileext": ".docx",
                    "filesize": 1234,
                    "uploadtime": "2026-06-01 11:00:00",
                    "sortnum": 1,
                }
            ]

        with patch.object(main_module, "_db_fetch_one", fake_fetch_one, create=True), patch.object(
            main_module, "_db_fetch_all", fake_fetch_all, create=True
        ):
            response = self.client.get("/records/m1/a1")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["menu_code"], "m1")
        self.assertIn("Hello world", body["content_text"])
        self.assertEqual(body["attachments"][0]["filename"], "file.docx")

    def test_selection_preview_validates_limits_overlap_and_missing_records(self) -> None:
        with patch.object(main_module, "_records_by_keys", return_value={}, create=True):
            response = self.client.post(
                "/analysis/selection/preview",
                json={"primary_materials": [], "auxiliary_materials": []},
            )
        self.assertEqual(response.status_code, 422)
        self.assertIn("primary_materials", response.text)

        with patch.object(main_module, "_records_by_keys", return_value={}, create=True):
            response = self.client.post(
                "/analysis/selection/preview",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "a1"}],
                    "auxiliary_materials": [{"menu_code": "m1", "articleid": "a1"}],
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertIn("同时作为主分析材料和辅助分析材料", response.text)

        with patch.object(main_module, "_records_by_keys", return_value={}, create=True):
            response = self.client.post(
                "/analysis/selection/preview",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "missing"}],
                    "auxiliary_materials": [],
                },
            )
        self.assertEqual(response.status_code, 422)
        self.assertIn("不存在", response.text)

    def test_selection_preview_returns_primary_and_auxiliary_records(self) -> None:
        records = {
            ("m1", "a1"): list_row(menu_code="m1", articleid="a1", title="Primary"),
            ("m2", "a2"): list_row(menu_code="m2", articleid="a2", title="Auxiliary", areaname="北京"),
        }

        with patch.object(main_module, "_records_by_keys", return_value=records, create=True):
            response = self.client.post(
                "/analysis/selection/preview",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "a1"}],
                    "auxiliary_materials": [{"menu_code": "m2", "articleid": "a2"}],
                    "enable_attachment_download": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["primary_materials"][0]["title"], "Primary")
        self.assertEqual(body["auxiliary_materials"][0]["areaname"], "北京")

    def test_analysis_prepare_builds_and_persists_database_evidence_pack(self) -> None:
        def fake_fetch_all(sql: str, params: list[object]):
            if "sample_article_wide" in sql:
                return [
                    detail_row(menu_code="m1", articleid="a1", title="Primary", summary="primary summary"),
                    detail_row(menu_code="m2", articleid="a2", title="Aux", summary="", content="<p>辅助正文内容足够用于摘要。</p>"),
                ]
            if "sample_article_attach" in sql:
                return [
                    attachment_row(menu_code="m1", articleid="a1", articleattid="att1", filename="primary.pdf", fileext=".pdf"),
                    attachment_row(menu_code="m2", articleid="a2", articleattid="att2", filename="aux.xlsx", fileext=".xlsx"),
                ]
            return []

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_db_fetch_all", fake_fetch_all, create=True
        ), patch.object(main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True):
            response = self.client.post(
                "/analysis/prepare",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "a1"}],
                    "auxiliary_materials": [{"menu_code": "m2", "articleid": "a2"}],
                    "enable_attachment_download": False,
                },
            )

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["success"])
            self.assertTrue(body["pack_id"].startswith("pack_"))
            self.assertEqual(body["primary_count"], 1)
            self.assertEqual(body["auxiliary_count"], 1)
            self.assertEqual(body["attachment_count"], 2)

            pack = body["evidence_pack"]
            self.assertEqual(pack["source"], "database_selection")
            self.assertEqual(pack["primary_materials"][0]["material_role"], "primary")
            self.assertEqual(pack["auxiliary_materials"][0]["material_role"], "auxiliary")
            self.assertIn("公告标题", pack["primary_materials"][0]["content_text"])
            self.assertNotIn("<script>", pack["primary_materials"][0]["content_text"])
            self.assertEqual(pack["primary_materials"][0]["content_summary"], "primary summary")
            attachment = pack["primary_materials"][0]["attachments"][0]
            self.assertEqual(attachment["download_method"], "internal_attid")
            self.assertEqual(attachment["parse_status"], "metadata_only")
            self.assertIn("{articleattid}", attachment["download_url_template"])
            self.assertEqual(pack["pack_version"], "2.0")
            self.assertIn("primary_evidence", pack)
            self.assertIn("auxiliary_evidence", pack)
            self.assertIn("attachment_evidence", pack)
            self.assertIn("generation_guidance", pack)
            self.assertIn("relation_to_primary", pack["auxiliary_materials"][0])

            pack_response = self.client.get(f"/analysis/packs/{body['pack_id']}")
            self.assertEqual(pack_response.status_code, 200)
            self.assertEqual(pack_response.json()["pack_id"], body["pack_id"])

            summary_response = self.client.get(f"/analysis/packs/{body['pack_id']}/summary")
            self.assertEqual(summary_response.status_code, 200)
            self.assertEqual(summary_response.json()["attachment_count"], 2)

    def test_attachment_download_without_cookie_attempts_request_and_handles_rejection(self) -> None:
        with patch.dict(
            main_module.os.environ,
            {
                "ENABLE_ATTACHMENT_DOWNLOAD": "true",
                "ATTACHMENT_COOKIE": "",
                "ATTACHMENT_HEADERS_JSON": "",
            },
        ), patch("app.attachment_fetcher.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.return_value.get.return_value = main_module.httpx.Response(403, text="forbidden")
            result = fetch_attachment_bytes({"articleattid": "att-auth", "filename": "a.pdf"})

        self.assertEqual(result.download_status, "download_failed")
        self.assertEqual(result.auth_mode, "none")
        self.assertIsNone(result.content)

    def test_attachment_headers_include_cookie(self) -> None:
        with patch.dict(
            main_module.os.environ,
            {
                "ATTACHMENT_COOKIE": "SESSION=secret",
                "ATTACHMENT_HEADERS_JSON": '{"X-Test":"ok"}',
            },
        ):
            headers, mode = build_attachment_auth_headers()

        self.assertEqual(mode, "configured_cookie")
        self.assertEqual(headers["Cookie"], "SESSION=secret")
        self.assertEqual(headers["X-Test"], "ok")

    def test_docx_and_excel_attachment_parsers_return_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = main_module.Path(tmpdir) / "notice.docx"
            doc = Document()
            doc.add_paragraph("申报时间为2026年6月，企业需要关注价格规则。")
            table = doc.add_table(rows=2, cols=2)
            table.cell(0, 0).text = "企业名称"
            table.cell(0, 1).text = "产品名称"
            table.cell(1, 0).text = "企业A"
            table.cell(1, 1).text = "产品B"
            doc.save(doc_path)

            wb = Workbook()
            ws = wb.active
            ws.title = "产品清单"
            ws.append(["企业名称", "产品名称", "注册证号", "医保编码", "申报价"])
            ws.append(["企业A", "产品B", "证号1", "码1", 10])
            excel_path = main_module.Path(tmpdir) / "list.xlsx"
            wb.save(excel_path)

            doc_result = parse_attachment_bytes(doc_path.read_bytes(), "notice.docx", ".docx", 1024)
            excel_result = parse_attachment_bytes(excel_path.read_bytes(), "list.xlsx", ".xlsx", 2048)

        self.assertIn("parsed_summary", doc_result["parse_statuses"])
        self.assertIn("申报时间", doc_result["summary"])
        self.assertIn("parsed_table_summary", excel_result["parse_statuses"])
        self.assertEqual(excel_result["table_summaries"][0]["sheet_name"], "产品清单")
        self.assertIn("企业名称", excel_result["table_summaries"][0]["key_columns"])
        self.assertTrue(excel_result["table_summaries"][0]["contains_enterprise"])
        self.assertTrue(excel_result["table_summaries"][0]["contains_product"])
        self.assertTrue(excel_result["table_summaries"][0]["contains_price"])

    def test_attachment_parse_cache_reuses_success_and_marks_core_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            workbook_path = main_module.Path(tmpdir) / "core.xlsx"
            wb = Workbook()
            ws = wb.active
            ws.title = "产品清单"
            ws.append(["企业名称", "产品名称", "注册证号", "医保编码", "中选价", "采购量"])
            ws.append(["企业A", "产品A", "国械注准1", "C001", "12.50", "100"])
            wb.save(workbook_path)
            content = workbook_path.read_bytes()

            row = attachment_row(
                articleattid="att-core-cache",
                filename="中选结果产品清单.xlsx",
                fileext=".xlsx",
                filesize=len(content),
                uploadtime="2026-06-01 11:00:00",
            )
            env = {
                "ENABLE_ATTACHMENT_PARSE_CACHE": "true",
                "ATTACHMENT_PARSE_CACHE_DIR": str(main_module.Path(tmpdir) / "cache"),
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "app.main.fetch_attachment_bytes",
                return_value=AttachmentDownloadResult("downloaded", "none", content=content, content_type="", filename=row["filename"], warnings=[]),
            ) as fetch:
                first = main_module._database_attachment_metadata(row, {"enable_download": True})
                second = main_module._database_attachment_metadata(row, {"enable_download": True})

        self.assertEqual(fetch.call_count, 1)
        self.assertTrue(first["core_attachment"])
        self.assertEqual(first["business_type"], "中选结果")
        self.assertEqual(first["cache_status"], "cache_miss")
        self.assertEqual(second["cache_status"], "cache_hit_success")
        self.assertTrue(second["table_summaries"][0]["contains_enterprise"])
        self.assertTrue(second["table_summaries"][0]["contains_product"])
        self.assertTrue(second["table_summaries"][0]["contains_price"])
        self.assertFalse(second["stored_original_file"])

    def test_attachment_parse_failure_cache_is_short_and_force_refreshable(self) -> None:
        row = attachment_row(articleattid="att-fail-cache", filename="价格表.xlsx", fileext=".xlsx", filesize=123, uploadtime="2026")
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {
                "ENABLE_ATTACHMENT_PARSE_CACHE": "true",
                "ATTACHMENT_PARSE_CACHE_DIR": str(main_module.Path(tmpdir) / "cache"),
                "ATTACHMENT_PARSE_CACHE_FAILURE_TTL_MINUTES": "10",
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "app.main.fetch_attachment_bytes",
                return_value=AttachmentDownloadResult("network_unreachable", "none", warnings=["timeout"]),
            ) as fetch:
                first = main_module._database_attachment_metadata(row, {"enable_download": True})
                second = main_module._database_attachment_metadata(row, {"enable_download": True})
                refreshed = main_module._database_attachment_metadata(row, {"enable_download": True, "force_refresh": True})

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(first["parse_status"], "network_unreachable")
        self.assertEqual(first["cache_status"], "cache_miss")
        self.assertEqual(second["cache_status"], "cache_hit_failure_short")
        self.assertGreaterEqual(second["retry_after_seconds"], 1)
        self.assertEqual(refreshed["cache_status"], "force_refreshed")
        self.assertTrue(refreshed["core_attachment_unavailable"])

    def test_analysis_prepare_downloads_attachment_by_default_without_cookie(self) -> None:
        content = "default intranet attachment content with price rule and product scope".encode("utf-8")
        with patch.dict(
            main_module.os.environ,
            {
                "ENABLE_ATTACHMENT_PARSE": "true",
                "ENABLE_ATTACHMENT_PARSE_CACHE": "false",
                "ATTACHMENT_COOKIE": "",
                "ATTACHMENT_HEADERS_JSON": "",
                "ELIAN_QX_COOKIE": "",
            },
        ), patch.object(main_module, "_fetch_database_material_rows", return_value={("m1", "a1"): detail_row()}, create=True), patch.object(
            main_module,
            "_fetch_database_attachments",
            return_value={("m1", "a1"): [attachment_row(articleattid="att-default", filename="notice.txt", fileext=".txt")]},
            create=True,
        ), patch.object(
            main_module,
            "fetch_attachment_bytes",
            return_value=AttachmentDownloadResult(
                "downloaded",
                "none",
                content=content,
                content_type="text/plain",
                filename="notice.txt",
                warnings=[],
            ),
        ) as fetch_mock, tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True
        ):
            response = self.client.post(
                "/analysis/prepare",
                json={"primary_materials": [{"menu_code": "m1", "articleid": "a1"}], "auxiliary_materials": []},
            )

        self.assertEqual(response.status_code, 200)
        fetch_mock.assert_called_once()
        _, kwargs = fetch_mock.call_args
        self.assertTrue(kwargs["enable_download"])
        self.assertEqual(kwargs["user_cookie"], "")
        self.assertEqual(kwargs["user_headers"], {})
        attachment = response.json()["evidence_pack"]["primary_materials"][0]["attachments"][0]
        self.assertEqual(attachment["download_auth_mode"], "none")
        self.assertIn("parsed_summary", attachment["parse_statuses"])
        self.assertGreater(attachment["text_length"], 0)
        self.assertFalse(attachment["stored_original_file"])

    def test_fetch_attachment_marks_network_unreachable(self) -> None:
        with patch.dict(main_module.os.environ, {"ENABLE_ATTACHMENT_DOWNLOAD": "true"}), patch(
            "app.attachment_fetcher.httpx.Client"
        ) as client_cls:
            client_cls.return_value.__enter__.return_value.get.side_effect = main_module.httpx.ConnectError("no route")
            result = fetch_attachment_bytes({"articleattid": "att1", "filename": "a.pdf"})

        self.assertEqual(result.download_status, "network_unreachable")
        self.assertEqual(result.auth_mode, "none")

    def test_analysis_prepare_can_disable_attachment_download_per_request(self) -> None:
        with patch.dict(
            main_module.os.environ,
            {
                "ENABLE_ATTACHMENT_DOWNLOAD": "true",
                "ENABLE_ATTACHMENT_PARSE": "true",
                "ATTACHMENT_COOKIE": "",
                "ATTACHMENT_HEADERS_JSON": "",
                "ELIAN_QX_COOKIE": "",
            },
        ), patch.object(main_module, "_fetch_database_material_rows", return_value={("m1", "a1"): detail_row()}, create=True), patch.object(
            main_module, "_fetch_database_attachments", return_value={("m1", "a1"): [attachment_row(articleattid="att-auth")]}, create=True
        ), tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True
        ):
            response = self.client.post(
                "/analysis/prepare",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "a1"}],
                    "auxiliary_materials": [],
                    "enable_attachment_download": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        attachment = response.json()["evidence_pack"]["primary_materials"][0]["attachments"][0]
        self.assertEqual(attachment["parse_status"], "metadata_only")
        self.assertEqual(attachment["download_auth_mode"], "none")
        self.assertFalse(attachment["stored_original_file"])

    def test_analysis_prepare_uses_request_cookie_to_download_and_parse_attachment(self) -> None:
        content = "申报时间为2026年6月，企业需要关注价格规则和产品范围。".encode("utf-8")
        with patch.dict(
            main_module.os.environ,
            {
                "ENABLE_ATTACHMENT_DOWNLOAD": "false",
                "ENABLE_ATTACHMENT_PARSE": "true",
                "ENABLE_ATTACHMENT_PARSE_CACHE": "false",
                "ATTACHMENT_COOKIE": "",
                "ATTACHMENT_HEADERS_JSON": "",
                "ELIAN_QX_COOKIE": "",
            },
        ), patch.object(main_module, "_fetch_database_material_rows", return_value={("m1", "a1"): detail_row()}, create=True), patch.object(
            main_module,
            "_fetch_database_attachments",
            return_value={("m1", "a1"): [attachment_row(articleattid="att-txt", filename="notice.txt", fileext=".txt")]},
            create=True,
        ), patch.object(
            main_module,
            "fetch_attachment_bytes",
            return_value=AttachmentDownloadResult(
                "downloaded",
                "user_cookie",
                content=content,
                content_type="text/plain",
                filename="notice.txt",
                warnings=[],
            ),
        ) as fetch_mock, tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True
        ):
            response = self.client.post(
                "/analysis/prepare",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "a1"}],
                    "auxiliary_materials": [],
                    "enable_attachment_download": True,
                    "attachment_cookie": "SESSION=temp-cookie",
                    "attachment_headers": {"X-Test": "ok"},
                },
            )

        self.assertEqual(response.status_code, 200)
        fetch_mock.assert_called_once()
        _, kwargs = fetch_mock.call_args
        self.assertTrue(kwargs["enable_download"])
        self.assertEqual(kwargs["user_cookie"], "SESSION=temp-cookie")
        self.assertEqual(kwargs["user_headers"], {"X-Test": "ok"})
        attachment = response.json()["evidence_pack"]["primary_materials"][0]["attachments"][0]
        self.assertEqual(attachment["download_auth_mode"], "user_cookie")
        self.assertIn("parsed_summary", attachment["parse_statuses"])
        self.assertIn("申报时间", attachment["summary"])
        self.assertGreater(attachment["text_length"], 0)
        self.assertFalse(attachment["stored_original_file"])

    def test_analysis_prepare_returns_structured_validation_error(self) -> None:
        response = self.client.post(
            "/analysis/prepare",
            json={"primary_materials": [], "auxiliary_materials": []},
        )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "INVALID_SELECTION")

    def test_analysis_prepare_rejects_missing_database_records(self) -> None:
        with patch.object(main_module, "_db_fetch_all", return_value=[], create=True):
            response = self.client.post(
                "/analysis/prepare",
                json={
                    "primary_materials": [{"menu_code": "m1", "articleid": "missing"}],
                    "auxiliary_materials": [],
                },
            )

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "MATERIAL_NOT_FOUND")

    def test_get_analysis_pack_returns_404_for_missing_pack(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True
        ):
            response = self.client.get("/analysis/packs/pack_missing")

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.text)

    def test_get_analysis_pack_defaults_to_dify_safe_compact_response(self) -> None:
        long_attachment_summary = "附件摘要" * 7000
        pack = {
            "pack_id": "pack_20260615_bigpack1",
            "created_at": "2026-06-15 10:00:00",
            "pack_version": "2.0",
            "source": "database_selection",
            "primary_materials": [
                {
                    "material_role": "primary",
                    "menu_code": "m1",
                    "articleid": "a1",
                    "title": "Big notice",
                    "content_text": "正文" * 12000,
                    "content_text_length": 24000,
                    "content_summary": "summary",
                    "attachments": [
                        {
                            "articleattid": "att1",
                            "filename": "中选结果价格表.pdf",
                            "fileext": ".pdf",
                            "core_attachment": True,
                            "business_type": "中选结果",
                            "parse_status": "parsed_summary",
                            "text_length": 50000,
                            "summary": long_attachment_summary,
                            "important_sections": ["重点内容" * 500],
                            "table_summaries": [],
                            "warnings": ["附件仅解析到元数据层面，不应混入正式正文"],
                        }
                    ],
                }
            ],
            "auxiliary_materials": [],
            "warnings": [],
            "primary_evidence": {"attachment_summaries": [{"summary": long_attachment_summary}]},
            "attachment_evidence": {"parsed_summaries": [{"summary": long_attachment_summary}], "warnings": []},
            "generation_guidance": {"do_not_use_as_basis": []},
        }
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True
        ):
            main_module._write_database_evidence_pack(pack)
            compact_response = self.client.get("/analysis/packs/pack_20260615_bigpack1")
            full_response = self.client.get("/analysis/packs/pack_20260615_bigpack1?full=true")

        self.assertEqual(compact_response.status_code, 200)
        compact = compact_response.json()
        self.assertTrue(compact["dify_compacted"])
        self.assertLess(len(json.dumps(compact, ensure_ascii=False)), 80000)
        self.assertLess(len(compact["primary_materials"][0]["attachments"][0]["summary"]), len(long_attachment_summary))
        self.assertEqual(compact["pack_variant"], "dify_compact")
        self.assertIn("compression_strategy", compact)
        self.assertIn("omitted_content", compact)
        self.assertEqual(compact["primary_materials"][0]["attachments"][0]["business_type"], "中选结果")
        self.assertNotIn("附件仅解析到元数据层面", json.dumps(compact["primary_materials"][0]["attachments"][0], ensure_ascii=False))
        self.assertIn("资料说明", json.dumps(compact["generation_guidance"], ensure_ascii=False))
        self.assertEqual(full_response.status_code, 200)
        self.assertGreater(len(json.dumps(full_response.json(), ensure_ascii=False)), 80000)

    def test_pack_diagnostics_reports_evidence_level_and_attachment_status(self) -> None:
        pack = {
            "pack_id": "pack_20260612_diag1234",
            "created_at": "2026-06-12 10:00:00",
            "primary_materials": [
                {
                    "menu_code": "m1",
                    "articleid": "a1",
                    "title": "Primary",
                    "summary": "summary",
                    "content_text": "A" * 1200,
                    "content_text_length": 1200,
                    "key_facts": [{"name": "fact"}],
                    "attachments": [{"articleattid": "att1", "parse_status": "metadata_only"}],
                }
            ],
            "auxiliary_materials": [
                {
                    "menu_code": "m2",
                    "articleid": "a2",
                    "title": "Aux",
                    "summary": "",
                    "content_text": "B" * 300,
                    "attachments": [],
                }
            ],
            "combined_key_facts": [],
            "warnings": ["content warning"],
        }
        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_database_evidence_pack_dir", return_value=main_module.Path(tmpdir), create=True
        ):
            main_module._write_database_evidence_pack(pack)
            response = self.client.get("/analysis/packs/pack_20260612_diag1234/diagnostics")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        diagnostics = body["diagnostics"]
        self.assertEqual(diagnostics["estimated_evidence_level"], "medium")
        self.assertEqual(diagnostics["attachment_count"], 1)
        self.assertEqual(diagnostics["metadata_only_attachment_count"], 1)
        self.assertEqual(diagnostics["primary_content_chars"], 1200)
        self.assertEqual(diagnostics["auxiliary_content_chars"], 300)
        self.assertGreater(diagnostics["weighted_evidence_chars"], 0)
        self.assertEqual(diagnostics["primary_attachment_summary_chars"], 0)
        self.assertIn("raw_total_content_chars", diagnostics)
        self.assertIn("dify_compact_pack_chars", diagnostics)
        self.assertIn("ATTACHMENTS_NOT_PARSED", {item["code"] for item in diagnostics["diagnosis"]})
        self.assertIn("PACK_WARNINGS_EXIST", {item["code"] for item in diagnostics["diagnosis"]})

    def test_analysis_run_page_progress_and_diagnostics(self) -> None:
        pack = {
            "pack_id": "pack_20260612_rundiag1",
            "created_at": "2026-06-12 10:00:00",
            "primary_materials": [
                {
                    "menu_code": "m1",
                    "articleid": "a1",
                    "title": "Primary",
                    "summary": "short",
                    "content_text": "A" * 6000,
                    "content_text_length": 6000,
                    "key_facts": [],
                    "attachments": [{"articleattid": "att1", "parse_status": "metadata_only"}],
                }
            ],
            "auxiliary_materials": [],
            "warnings": [],
        }
        run = {
            "success": True,
            "run_id": "run_20260612_diag1234",
            "pack_id": "pack_20260612_rundiag1",
            "status": "finished",
            "workflow_run_id": "wf-1",
            "report_title": "Short report",
            "report_markdown": "Too short.",
            "version": 1,
            "quality_check": {"passed": True, "issues": []},
            "generation_warnings": [],
            "remaining_issues": [],
            "created_at": "2026-06-12 10:01:00",
            "updated_at": "2026-06-12 10:02:00",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            root = main_module.Path(tmpdir)
            pack_dir = root / "packs"
            run_dir = root / "runs"
            with patch.object(main_module, "_database_evidence_pack_dir", return_value=pack_dir, create=True), patch.object(
                main_module, "_analysis_run_dir", return_value=run_dir, create=True
            ):
                main_module._write_database_evidence_pack(pack)
                main_module._write_analysis_run(run)

                page_response = self.client.get("/analysis-runs/run_20260612_diag1234")
                status_response = self.client.get("/analysis/runs/run_20260612_diag1234")
                diagnostics_response = self.client.get("/analysis/runs/run_20260612_diag1234/diagnostics")

        self.assertEqual(page_response.status_code, 200)
        self.assertIn("报告生成详情", page_response.text)
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["progress"]["percent"], 100)
        self.assertEqual(diagnostics_response.status_code, 200)
        codes = {item["code"] for item in diagnostics_response.json()["diagnostics"]["diagnosis"]}
        self.assertIn("REPORT_TOO_SHORT_FOR_WEIGHTED_EVIDENCE", codes)
        self.assertIn("ATTACHMENTS_NOT_PARSED", codes)
        evidence = diagnostics_response.json()["diagnostics"]["evidence"]
        self.assertIn("weighted_evidence_chars", evidence)
        self.assertIn("raw_total_content_chars", evidence)
        self.assertIn("dify_compact_pack_chars", evidence)
        self.assertIn("primary_attachment_summary_chars", evidence)

    def test_analysis_run_progress_is_smooth_while_running(self) -> None:
        with patch("app.diagnostics.datetime") as datetime_mock:
            datetime_mock.fromisoformat.side_effect = main_module.datetime.fromisoformat
            datetime_mock.now.return_value = main_module.datetime.fromisoformat("2026-06-12 10:00:30")
            progress = main_module.build_run_progress(
                {
                    "status": "running",
                    "created_at": "2026-06-12 10:00:00",
                    "updated_at": "2026-06-12 10:00:00",
                    "version": 1,
                    "quality_check": {"passed": None, "issues": []},
                }
            )

        self.assertGreaterEqual(progress["percent"], 65)
        self.assertLessEqual(progress["percent"], 82)
        self.assertEqual(progress["current_step"], "Dify 工作流执行中")
        by_key = {step["key"]: step for step in progress["steps"]}
        self.assertEqual(by_key["create_run"]["status"], "finished")
        self.assertEqual(by_key["fetch_pack"]["status"], "finished")
        self.assertEqual(by_key["generate_report"]["status"], "running")
        self.assertEqual(by_key["quality_check"]["status"], "pending")
        self.assertEqual(by_key["revision"]["status"], "pending")

    def test_analysis_run_progress_finished_does_not_duplicate_middle_timestamps(self) -> None:
        progress = main_module.build_run_progress(
            {
                "status": "finished",
                "created_at": "2026-06-12 10:00:00",
                "updated_at": "2026-06-12 10:02:00",
                "version": 1,
                "quality_check": {"passed": True, "issues": []},
            }
        )

        self.assertEqual(progress["percent"], 100)
        by_key = {step["key"]: step for step in progress["steps"]}
        self.assertEqual(by_key["create_run"]["timestamp"], "2026-06-12 10:00:00")
        self.assertEqual(by_key["fetch_pack"]["timestamp"], "2026-06-12 10:00:00")
        self.assertIsNone(by_key["generate_report"]["timestamp"])
        self.assertIsNone(by_key["quality_check"]["timestamp"])
        self.assertEqual(by_key["revision"]["status"], "skipped")
        self.assertIsNone(by_key["revision"]["timestamp"])
        self.assertEqual(by_key["final_output"]["timestamp"], "2026-06-12 10:02:00")

    def test_analysis_run_calls_dify_and_persists_report(self) -> None:
        calls: list[tuple[str, str]] = []

        def fake_call(pack_id: str, run_id: str):
            calls.append((pack_id, run_id))
            return {
                "workflow_run_id": "wf-run-1",
                "status": "finished",
                "report_title": "Report title",
                "report_markdown": "# Report\n\nBody",
                "version": 1,
                "quality_check": {"passed": True, "issues": []},
                "generation_warnings": ["metadata only"],
                "remaining_issues": [],
            }

        with tempfile.TemporaryDirectory() as tmpdir, patch.object(
            main_module, "_analysis_run_dir", return_value=main_module.Path(tmpdir), create=True
        ), patch.object(
            main_module, "_read_database_evidence_pack", return_value={"pack_id": "pack_20260612_abcdef1234"}, create=True
        ), patch.object(main_module, "_call_dify_workflow", fake_call, create=True):
            response = self.client.post("/analysis/run", json={"pack_id": "pack_20260612_abcdef1234"})

            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["success"])
            self.assertTrue(body["run_id"].startswith("run_"))
            self.assertEqual(body["pack_id"], "pack_20260612_abcdef1234")
            self.assertEqual(body["status"], "running")

            wait_until(lambda: self.client.get(f"/analysis/runs/{body['run_id']}").json().get("status") == "finished")
            self.assertEqual(calls, [("pack_20260612_abcdef1234", body["run_id"])])

            status_response = self.client.get(f"/analysis/runs/{body['run_id']}")
            self.assertEqual(status_response.status_code, 200)
            self.assertEqual(status_response.json()["workflow_run_id"], "wf-run-1")
            self.assertEqual(status_response.json()["status"], "finished")

            report_response = self.client.get(f"/analysis/runs/{body['run_id']}/report")
            self.assertEqual(report_response.status_code, 200)
            report_body = report_response.json()
            self.assertEqual(report_body["report_markdown"], "# Report\n\nBody")
            self.assertTrue(report_body["quality_check"]["passed"])

    def test_analysis_run_download_exports_markdown_docx(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = main_module.Path(tmpdir) / "runs"
            report_dir = main_module.Path(tmpdir) / "reports"
            run_dir.mkdir()
            with patch.object(main_module, "_analysis_run_dir", return_value=run_dir, create=True):
                main_module._write_analysis_run(
                    {
                        "success": True,
                        "run_id": "run_test1234",
                        "pack_id": "pack_test",
                        "status": "finished",
                        "report_title": "测试报告",
                        "report_markdown": "# 测试报告\n\n正文内容",
                        "version": 1,
                        "quality_check": {"passed": True, "issues": []},
                    }
                )
            with patch.object(main_module, "_analysis_run_dir", return_value=run_dir, create=True), patch.object(
                main_module, "REPORT_DIR", report_dir
            ):
                response = self.client.get("/analysis/runs/run_test1234/download")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            response.headers["content-type"],
        )
        self.assertGreater(len(response.content), 1000)

    def test_markdown_docx_uses_manual_report_style_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = main_module.Path(tmpdir) / "styled.docx"
            main_module._markdown_to_docx(
                "\n".join(
                    [
                        "## 重点内容",
                        "<blue>企业需关注申报截止时间。</blue>",
                        "",
                        "| 挂网状态 | 序号 | 对应情形 |",
                        "| --- | --- | --- |",
                        "| 暂停挂网 | 1 | 普通内容 |",
                        "| 暂停挂网 | 2 | <red>未进行价格联动的产品暂停挂网。</red> |",
                    ]
                ),
                path,
                "测试报告",
            )
            doc = Document(path)

        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        self.assertIn("声  明", text)
        self.assertIn("企业需关注申报截止时间。", text)
        self.assertEqual(len(doc.tables), 1)
        header_shading = doc.tables[0].cell(0, 0)._tc.tcPr.find(qn("w:shd"))
        self.assertEqual(header_shading.get(qn("w:fill")), "0070C0")
        red_runs = [
            run
            for row in doc.tables[0].rows
            for cell in row.cells
            for paragraph in cell.paragraphs
            for run in paragraph.runs
            if "未进行价格联动" in run.text
        ]
        self.assertTrue(red_runs)
        self.assertEqual(str(red_runs[0].font.color.rgb), "FF0000")

    def test_markdown_docx_cleans_analysis_highlight_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(main_module.os.environ, {"ENABLE_ANALYSIS_HIGHLIGHT": "false"}):
            path = main_module.Path(tmpdir) / "highlight.docx"
            main_module._markdown_to_docx(
                '事实内容。<span class="analysis-highlight">这是分析内容。</span>',
                path,
                "测试报告",
            )
            doc = Document(path)

        text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        self.assertIn("这是分析内容。", text)
        self.assertNotIn("analysis-highlight", text)
        self.assertNotIn("<span", text)

    def test_analysis_run_download_rejects_not_ready_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = main_module.Path(tmpdir) / "runs"
            run_dir.mkdir()
            with patch.object(main_module, "_analysis_run_dir", return_value=run_dir, create=True):
                main_module._write_analysis_run(
                    {
                    "success": True,
                    "run_id": "run_pending1",
                    "pack_id": "pack_test",
                    "status": "running",
                    "report_markdown": "",
                    }
                )
                response = self.client.get("/analysis/runs/run_pending1/download")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "REPORT_NOT_READY")

    def test_normalize_dify_result_parses_json_string_fields(self) -> None:
        result = main_module._normalize_dify_result(
            {
                "workflow_run_id": "wf-1",
                "data": {
                    "status": "succeeded",
                    "outputs": {
                        "result": {
                            "status": "needs_manual_review",
                            "pack_id": "pack_test",
                            "report_title": "标题",
                            "report_markdown": "正文",
                            "version": 2,
                            "quality_check": '{"passed": false, "issues": [{"issue_id": "Q001"}]}',
                            "generation_warnings": '["附件仅元数据"]',
                            "remaining_issues": '[{"issue_id": "Q001"}]',
                        }
                    },
                },
            },
            "pack_test",
        )

        self.assertEqual(result["quality_check"]["passed"], False)
        self.assertEqual(result["generation_warnings"], ["附件仅元数据"])
        self.assertEqual(result["remaining_issues"][0]["issue_id"], "Q001")

    def test_unusable_dify_report_gets_fallback_from_evidence_pack(self) -> None:
        pack = {
            "pack_id": "pack_test",
            "primary_materials": [
                {
                    "title": "天津市医保局市卫生健康委市药监局关于执行集采结果有关工作的通知",
                    "audittime": "2026-06-15",
                    "areaname": "天津市",
                    "publicorg": "天津市医保局",
                    "projectphase": "执行",
                    "projecttype": "医用耗材",
                    "category": "集采",
                    "summary": "执行国家组织药物球囊、泌尿介入类和省际联盟相关医用耗材集采结果。",
                    "content_text": "本通知明确执行国家组织药物球囊、泌尿介入类和省际联盟组织硬脑膜补片类等医用耗材集采结果。医疗机构应按要求执行中选结果，企业需关注产品范围、执行时间和医保支付标准衔接。",
                    "key_facts": [{"name": "地区", "value": "天津市"}],
                    "attachments": [
                        {"filename": "附件1.pdf", "parse_status": "auth_required", "warnings": ["需要登录态"]},
                    ],
                }
            ],
            "auxiliary_materials": [],
            "warnings": [],
        }
        result = {
            "workflow_run_id": "wf-empty",
            "status": "finished",
            "pack_id": "pack_test",
            "report_title": "...",
            "report_markdown": "...",
            "version": 2,
            "quality_check": {"passed": True, "issues": []},
            "generation_warnings": [],
            "warnings": [],
            "remaining_issues": [],
        }

        repaired = main_module._repair_unusable_dify_result(result, pack)

        self.assertEqual(repaired["status"], "needs_manual_review")
        self.assertGreater(len(repaired["report_markdown"]), 300)
        self.assertIn("天津市医保局", repaired["report_title"])
        self.assertIn("后端兜底版本", repaired["report_markdown"])
        self.assertFalse(repaired["quality_check"]["passed"])
        self.assertEqual(repaired["remaining_issues"][0]["issue_id"], "Q_DIFY_EMPTY_REPORT")

    def test_user_feedback_revision_updates_latest_report_and_keeps_previous_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = main_module.Path(tmpdir)
            run_dir = root / "runs"
            pack_dir = root / "packs"
            run_dir.mkdir()
            pack_dir.mkdir()
            with patch.object(main_module, "_analysis_run_dir", return_value=run_dir, create=True), patch.object(
                main_module, "_database_evidence_pack_dir", return_value=pack_dir, create=True
            ):
                main_module._write_database_evidence_pack({"pack_id": "pack_20260615_revise1", "primary_materials": [], "auxiliary_materials": []})
                main_module._write_analysis_run(
                    {
                        "success": True,
                        "run_id": "run_20260615_revise1",
                        "pack_id": "pack_20260615_revise1",
                        "status": "finished",
                        "report_title": "旧标题",
                        "report_markdown": "旧正文",
                        "version": 1,
                        "quality_check": {"passed": True, "issues": []},
                        "created_at": "2026-06-15 09:00:00",
                        "updated_at": "2026-06-15 09:01:00",
                    }
                )

                def fake_revision(*args, **kwargs):
                    return {
                        "report_title": "新标题",
                        "report_markdown": '<span class="analysis-highlight">新增企业影响分析。</span>',
                        "warnings": [],
                    }

                with patch.object(main_module, "_call_dify_revision_workflow", fake_revision, create=True):
                    response = self.client.post(
                        "/analysis/runs/run_20260615_revise1/revise",
                        json={"feedback": "增加企业影响分析", "analysis_highlight": True},
                    )
                    report_response = self.client.get("/analysis/runs/run_20260615_revise1/report")
                    record = main_module._read_analysis_run("run_20260615_revise1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["version"], 2)
        self.assertIn("analysis-highlight", response.json()["report_markdown"])
        self.assertEqual(report_response.json()["version"], 2)
        self.assertEqual(record["report_versions"][0]["version"], 1)
        self.assertEqual(record["revisions"][0]["feedback"], "增加企业影响分析")

    def test_analysis_run_rejects_missing_pack(self) -> None:
        with patch.object(
            main_module,
            "_read_database_evidence_pack",
            side_effect=main_module.HTTPException(status_code=404, detail="evidence pack not found"),
            create=True,
        ):
            response = self.client.post("/analysis/run", json={"pack_id": "pack_20260612_missing1"})

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "PACK_NOT_FOUND")

    def test_analysis_run_returns_structured_error_when_dify_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir, patch.dict(
            main_module.os.environ,
            {
                "DIFY_BASE_URL": "http://192.168.34.86/v1",
                "DIFY_WORKFLOW_API_KEY": "",
                "DIFY_REPORT_WORKFLOW_ENDPOINT": "/workflows/run",
            },
        ), patch.object(
            main_module, "_analysis_run_dir", return_value=main_module.Path(tmpdir), create=True
        ), patch.object(
            main_module, "_read_database_evidence_pack", return_value={"pack_id": "pack_20260612_abcdef1234"}, create=True
        ):
            response = self.client.post("/analysis/run", json={"pack_id": "pack_20260612_abcdef1234"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertTrue(body["success"])
            self.assertEqual(body["status"], "running")
            run_id = body["run_id"]

            wait_until(lambda: self.client.get(f"/analysis/runs/{run_id}").json().get("status") == "failed")
            status_response = self.client.get(f"/analysis/runs/{run_id}")

        self.assertEqual(status_response.status_code, 200)
        status_body = status_response.json()
        self.assertFalse(status_body["success"])
        self.assertEqual(status_body["status"], "failed")
        self.assertEqual(status_body["error_message"], "Dify API 配置不完整")


if __name__ == "__main__":
    unittest.main()
