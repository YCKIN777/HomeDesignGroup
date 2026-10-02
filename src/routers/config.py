# -*- coding: utf-8 -*-
"""config 路由：M5 配置接通验证（改配置不改代码的实证入口）"""
from fastapi import APIRouter

from kernel import config_loader

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def config_summary():
    """返回当前生效配置摘要（管理员核对用）"""
    cfg = config_loader.load_profile("壹城精工")
    return {
        "company": cfg["manifest"]["company"],
        "kernel_version": cfg["manifest"]["kernel_version"],
        "terms": [t["label"] for t in cfg["terms"]],
        "rules": cfg["rules"],
        "workflow": {"backbone": cfg["workflow"]["backbone"],
                     "locked_nodes": cfg["workflow"]["locked_nodes"]},
        "extensions": cfg["extensions"],
    }
