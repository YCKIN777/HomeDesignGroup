# -*- coding: utf-8 -*-
"""
config_loader.py — 配置包加载器（Step 1.2）
功能（对齐 DOS-DP 校验器思路）：
  1. 加载 manifest.json / terms.yaml / rules.yaml / extensions.yaml / workflow.yaml
  2. schema 校验：填错当场报错（ValueError 带路径），不憋到运行时报
用法：
  from kernel.config_loader import load_profile
  cfg = load_profile("壹城精工")
  cfg.terms / cfg.rules / cfg.workflow / cfg.extensions / cfg.manifest
"""
import json
import os
import sys

import yaml  # 依赖 PyYAML；如未安装：pip install pyyaml

ROOT = r"H:\AgentProjects\HomeDesignGroup"
PROFILE_DIR = os.path.join(ROOT, "company_profiles")


class ConfigError(ValueError):
    """配置校验错误（带具体路径）"""


def _require(cond: bool, path: str, msg: str):
    if not cond:
        raise ConfigError(f"[配置校验失败] {path}: {msg}")


def _load_yaml(path: str):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"[YAML 解析失败] {path}: {e}") from e


def load_manifest(company: str):
    path = os.path.join(PROFILE_DIR, company, "manifest.json")
    with open(path, "r", encoding="utf-8-sig") as f:
        m = json.load(f)
    _require(m.get("company") == company, "manifest.json", f"company 应为 {company}")
    _require(m.get("kernel_version"), "manifest.json", "kernel_version 必填")
    return m


def load_terms(company: str):
    data = _load_yaml(os.path.join(PROFILE_DIR, company, "terms.yaml"))
    terms = data.get("terms", [])
    _require(isinstance(terms, list) and terms, "terms.yaml", "terms 必须为非空列表")
    for i, t in enumerate(terms):
        p = f"terms.yaml.terms[{i}]"
        _require(t.get("id"), p, "id 必填")
        _require(t.get("label"), p, "label 必填")
        _require(t.get("definition"), p, "definition 必填（文本定义）")
        _require(t.get("parent"), p, "parent 必填")
    ids = [t["id"] for t in terms]
    _require(len(ids) == len(set(ids)), "terms.yaml", "id 必须唯一（OBO P12）")
    return terms


def load_rules(company: str):
    data = _load_yaml(os.path.join(PROFILE_DIR, company, "rules.yaml"))
    _require(data.get("rules"), "rules.yaml", "rules 必填")
    r = data["rules"]
    _require(0 < r.get("discount", {}).get("need_approval_above", 0) <= 1,
             "rules.yaml.discount.need_approval_above", "折扣阈值须在 (0,1]")
    _require(r.get("sop", {}).get("first_contact_hours", 0) > 0,
             "rules.yaml.sop.first_contact_hours", "首联时限须为正数")
    return r


def load_workflow(company: str):
    data = _load_yaml(os.path.join(PROFILE_DIR, company, "workflow.yaml"))
    wf = data.get("workflow", {})
    backbone = wf.get("backbone", [])
    _require(isinstance(backbone, list) and len(backbone) >= 2,
             "workflow.yaml.backbone", "backbone 至少 2 个节点")
    locked = wf.get("locked_nodes", [])
    _require(all(n in backbone for n in locked),
             "workflow.yaml.locked_nodes", "locked_nodes 必须全部在 backbone 中")
    ts = wf.get("transitions", [])
    for i, t in enumerate(ts):
        p = f"workflow.yaml.transitions[{i}]"
        _require(t.get("from") and t.get("to") and t.get("trigger"), p,
                 "每条迁移须含 from/to/trigger")
    return wf


def load_extensions(company: str):
    data = _load_yaml(os.path.join(PROFILE_DIR, company, "extensions.yaml"))
    return data.get("extensions", {}) or {}


def load_profile(company: str):
    """加载并校验整个配置包，返回 dict"""
    return {
        "manifest": load_manifest(company),
        "terms": load_terms(company),
        "rules": load_rules(company),
        "workflow": load_workflow(company),
        "extensions": load_extensions(company),
    }


if __name__ == "__main__":
    # 自检入口：加载指定公司配置包
    company = sys.argv[1] if len(sys.argv) > 1 else "壹城精工"
    try:
        cfg = load_profile(company)
        print(f"[config_loader] {company} 配置包加载校验通过")
        print(f"  manifest: {cfg['manifest']['company']} @ kernel {cfg['manifest']['kernel_version']}")
        print(f"  terms: {len(cfg['terms'])} 条")
        print(f"  rules: {list(cfg['rules'].keys())}")
        print(f"  workflow: {len(cfg['workflow']['backbone'])} 节点, locked={cfg['workflow']['locked_nodes']}")
        print(f"  extensions: concepts={len(cfg['extensions'].get('concepts', []))}, fields={len(cfg['extensions'].get('fields', {}))}")
    except ConfigError as e:
        print(f"[config_loader] 校验失败: {e}")
        sys.exit(1)
