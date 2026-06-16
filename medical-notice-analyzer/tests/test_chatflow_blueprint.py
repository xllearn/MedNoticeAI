from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHATFLOW = ROOT / "dify-chatflow-medical-notice-report.yml"


def load_chatflow() -> dict[str, Any]:
    return json.loads(CHATFLOW.read_text(encoding="utf-8"))


def node_by_id(data: dict[str, Any], node_id: str) -> dict[str, Any]:
    for node in data["workflow"]["graph"]["nodes"]:
        if node.get("id") == node_id:
            return node
    raise AssertionError(f"node not found: {node_id}")


def node_text(node: dict[str, Any]) -> str:
    return json.dumps(node, ensure_ascii=False)


class ChatflowBlueprintTests(unittest.TestCase):
    def test_chatflow_declares_required_inputs_and_state(self) -> None:
        data = load_chatflow()
        text = json.dumps(data, ensure_ascii=False)

        self.assertEqual(data["app"]["mode"], "advanced-chat")
        self.assertIn("notice_url", text)
        self.assertIn("history_report", text)
        self.assertIn(".docx", text)
        for variable in [
            "source_evidence",
            "history_insights",
            "current_report_ir",
            "current_final_report",
            "last_qa_summary",
            "repair_attempt_count",
        ]:
            self.assertIn(variable, text)

    def test_first_generate_renders_and_qas_without_export(self) -> None:
        data = load_chatflow()
        fetch_source = node_by_id(data, "fetch_source")
        parse_source_evidence = node_by_id(data, "parse_source_evidence")
        assign_source = node_by_id(data, "assign_source")
        render_report = node_by_id(data, "render_report")
        build_qa_payload = node_by_id(data, "build_qa_payload")
        parse_qa_first = node_by_id(data, "parse_qa_first")

        self.assertIn("http://192.168.34.88:8099/analyze", node_text(fetch_source))
        fetch_body = fetch_source["data"]["body"]["data"][0]["value"]
        self.assertIn('"max_combined_chars":60000', fetch_body)
        self.assertIn("evidence_for_llm", node_text(parse_source_evidence))
        self.assertIn("fallback raw body", node_text(parse_source_evidence))
        self.assertIn("parse_source_evidence", node_text(assign_source))
        self.assertNotIn('["fetch_source", "body"]', node_text(assign_source))
        self.assertIn("http://192.168.34.88:8099/report/render", node_text(render_report))
        self.assertIn("MAX_PAYLOAD_CHARS = 110000", node_text(build_qa_payload))
        self.assertIn('("evidence_text", 60000)', build_qa_payload["data"]["code"])
        self.assertIn("truncate_payload_fields", node_text(build_qa_payload))
        self.assertIn("http://192.168.34.88:8099/report/qa", node_text(parse_qa_first))
        qa_report_first = node_by_id(data, "qa_report_first")
        self.assertIn("按表内数据测算", node_text(qa_report_first))
        self.assertIn("百分比", node_text(qa_report_first))

        edges = data["workflow"]["graph"]["edges"]
        first_targets = [edge["target"] for edge in edges if edge["source"] == "route_turn" and edge["sourceHandle"] == "first"]
        self.assertEqual(first_targets, ["history_file_gate"])
        self.assertFalse(any(edge["target"] == "export_word" and edge["sourceHandle"] == "first" for edge in edges))

    def test_approve_download_uses_nonblocking_checked_export_after_user_confirmation(self) -> None:
        data = load_chatflow()
        build_export_payload = node_by_id(data, "build_export_payload")
        export_word = node_by_id(data, "export_word")
        answer_download = node_by_id(data, "answer_download")

        self.assertIn("MAX_PAYLOAD_CHARS = 110000", node_text(build_export_payload))
        self.assertIn('("evidence_text", 60000)', build_export_payload["data"]["code"])
        self.assertIn("strict_quality", node_text(build_export_payload))
        self.assertIn("False", node_text(build_export_payload))
        self.assertIn("http://192.168.34.88:8099/report/export_checked", node_text(export_word))
        self.assertIn("parse_export.answer", node_text(answer_download))

    def test_chatflow_routes_pasted_qa_feedback_to_revision(self) -> None:
        data = load_chatflow()
        classify_turn = node_by_id(data, "classify_turn")
        route_turn = node_by_id(data, "route_turn")

        self.assertIn("质检", node_text(classify_turn))
        self.assertIn("needs_fix", node_text(classify_turn))
        self.assertIn("revise", node_text(classify_turn))
        self.assertIn("repair_limit", node_text(classify_turn))
        self.assertIn("first_generate", node_text(route_turn))
        self.assertIn("approve_download", node_text(route_turn))
        self.assertIn("repair_limit", node_text(route_turn))

    def test_chatflow_revision_branch_uses_existing_evidence_and_does_not_export(self) -> None:
        data = load_chatflow()
        revise_report = node_by_id(data, "revise_report")
        assign_revised_report = node_by_id(data, "assign_revised_report")

        self.assertIn("conversation.source_evidence", node_text(revise_report))
        self.assertIn("conversation.current_report_ir", node_text(revise_report))
        self.assertIn("conversation.current_final_report", node_text(revise_report))
        self.assertIn("影响分析", node_text(revise_report))
        self.assertIn("等价写法", node_text(revise_report))
        self.assertIn("逐条定位表格标题和数值", node_text(revise_report))
        self.assertIn("不得继续保留原数值", node_text(revise_report))
        self.assertIn("整列或整行的无证据数值", node_text(revise_report))
        self.assertIn("不要只保留备注", node_text(revise_report))
        self.assertIn("具体价格详见附件清单", node_text(revise_report))
        self.assertIn("current_report_ir", node_text(assign_revised_report))
        self.assertIn("current_final_report", node_text(assign_revised_report))
        self.assertIn("repair_attempt_count", node_text(assign_revised_report))

    def test_chatflow_stops_repeated_needs_fix_feedback_after_three_repairs(self) -> None:
        data = load_chatflow()
        classify_turn = node_by_id(data, "classify_turn")
        update_repair_state = node_by_id(data, "update_repair_state")
        answer_repair_limit = node_by_id(data, "answer_repair_limit")
        edges = data["workflow"]["graph"]["edges"]

        self.assertIn("repair_attempt_count", node_text(classify_turn))
        self.assertIn("repair_count >= 3", node_text(classify_turn))
        self.assertIn("连续 3 次 needs_fix", node_text(update_repair_state))
        self.assertIn("请不要继续粘贴同类修复建议", node_text(answer_repair_limit))
        self.assertTrue(
            any(
                edge["source"] == "route_turn"
                and edge["sourceHandle"] == "repair_limit"
                and edge["target"] == "answer_repair_limit"
                for edge in edges
            )
        )

    def test_analyze_http_node_retries_transient_failures(self) -> None:
        data = load_chatflow()
        fetch_source = node_by_id(data, "fetch_source")
        retry_config = fetch_source["data"]["retry_config"]

        self.assertTrue(retry_config["enabled"])
        self.assertEqual(retry_config["max_retries"], 2)


if __name__ == "__main__":
    unittest.main()
