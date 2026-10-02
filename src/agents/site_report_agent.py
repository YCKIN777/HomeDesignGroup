# -*- coding: utf-8 -*-
"""site_report_agent.py — MVP Sub-agent 3：工地日报 Agent（架构契约 Step 6）

监理上传现场照片+几句描述 → OCR（MultimodalProvider，识别进度/部位）→ 模板生成
当日进度简报草稿 → 进入 pending（Sentinel external_send：须人工点发送）。
"""
from datetime import datetime

from providers.factory import get_providers
from kernel.sentinel import PendingHuman, sentinel_check
from kernel.llm_enhance import llm_enhance


class SiteReportAgent:
    def __init__(self):
        self.providers = get_providers()

    def ocr_site(self, image_bytes: bytes) -> str:
        """照片 OCR：识别现场进度/部位（真实 OCR 接入后自动升级）"""
        return self.providers.multimodal.ocr(image_bytes)

    @sentinel_check("external_send")
    def _send(self, report: dict):
        """对外发送（Sentinel 拦截：须人工点发送）——真实发送通道预留"""
        return {"sent": True, "report_id": report["id"]}

    def build_report(self, project: str, photo_desc: str = "",
                     image_bytes: bytes = b"") -> dict:
        """生成当日进度简报草稿（pending_human）"""
        ocr_text = self.ocr_site(image_bytes) if image_bytes else "[无照片]"
        # LLM 增强（可选层）：把 OCR+备注整理成业主可读的日报正文；未配 key 自动降级
        enhance = llm_enhance(
            self.providers,
            "你是家装监理。把现场信息整理成发给业主的工地日报正文，2-3 句："
            "今日完成进度 + 下一步安排。只依据给定信息，不编造。",
            f"项目：{project}\n照片识别：{ocr_text}\n监理备注：{photo_desc or '（无）'}")
        report = {
            "id": f"SR-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "project": project,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "photo_ocr": ocr_text,
            "supervisor_note": photo_desc,
            "progress_summary": f"今日进度：{ocr_text}；监理备注：{photo_desc or '（无）'}",
            "llm_note": enhance,
            "status": "pending_human",          # Sentinel：人工点发送才对外
            "sentinel": "external_send → 草稿进 pending，人工确认后发送",
        }
        return report

    def send_report(self, report: dict) -> dict:
        """尝试对外发送 → 被 Sentinel 拦截为 PendingHuman（草稿待人工）"""
        try:
            return self._send(report)
        except PendingHuman as e:
            return {"ok": False, "pending": True, "draft": e.draft or report,
                    "msg": "已生成草稿，等待人工点发送"}
