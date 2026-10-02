# -*- coding: utf-8 -*-
"""
init_platform.py — 平台初始化脚本（Step 1.1）
功能（幂等，可重复执行）：
  1. 创建平台目录结构
  2. 创建公司数据库（SQLite，每公司一库）与 8 张表
  3. 写入 schema 版本（meta 表）
  4. 创建默认主管账号 admin（pbkdf2 加盐哈希）
用法：
  python scripts/init_platform.py [公司名]   # 默认 壹城精工
"""
import hashlib
import os
import sqlite3
import sys

ROOT = r"H:\AgentProjects\HomeDesignGroup"
COMPANY = sys.argv[1] if len(sys.argv) > 1 else "壹城精工"
DB_PATH = os.path.join(ROOT, "db", f"{COMPANY}.db")
SCHEMA_VERSION = "1"

# 目录结构（与《整体技术框架v1》工程目录对齐）
DIRS = [
    os.path.join(ROOT, "src", "kernel"),
    os.path.join(ROOT, "company_profiles", COMPANY),
    os.path.join(ROOT, "db"),
    os.path.join(ROOT, "knowledge"),
    os.path.join(ROOT, "sedimentation"),
    os.path.join(ROOT, "memory"),
    os.path.join(ROOT, "tests"),
    os.path.join(ROOT, "scripts"),
]

# 8 张表 + meta（schema 版本）
TABLES = {
    "customers": """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,               -- 脱敏展示
            name TEXT,
            estate TEXT,              -- 楼盘
            layout TEXT,              -- 户型
            area REAL,                -- 面积
            budget_range TEXT,        -- 预算区间
            style TEXT,               -- 风格
            intent_time TEXT,         -- 意向时间
            channel TEXT,             -- 渠道
            tags TEXT,                -- 需求标签(逗号分隔)
            score INTEGER DEFAULT 0,  -- 评分 0-100
            status TEXT DEFAULT '线索', -- 线索/跟进/邀约/到店/派单/成交/流失
            source TEXT,              -- 来源
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "projects": """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            designer TEXT,
            summary TEXT,             -- 需求摘要
            status TEXT DEFAULT '量房', -- 八阶段: 量房/设计/报价/签约/施工/验收/售后
            dispatched_at TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""",
    "messages": """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            direction TEXT,           -- in/out
            content TEXT,
            author TEXT,              -- ai/sales
            approve_status TEXT DEFAULT 'draft', -- draft/approved/rejected/sent
            source_ref TEXT,          -- 来源标注(哪条记录/哪个记忆文件)
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""",
    "followups": """
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            channel TEXT,             -- 电话/微信/到店...
            content TEXT,
            result TEXT,
            next_at TEXT,             -- 下次跟进时间
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""",
    "sedimentation_items": """
        CREATE TABLE IF NOT EXISTS sedimentation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,            -- 规则/话术/术语/最佳实践
            title TEXT,
            description TEXT,
            condition TEXT,           -- 适用条件
            evidence TEXT,            -- 验证证据(匿名)
            status TEXT DEFAULT '候选', -- 候选/已评审/已入内核/已剔除
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account TEXT UNIQUE,
            pwd_hash TEXT,
            role TEXT DEFAULT '销售', -- 主管/销售/客服/设计师
            company TEXT
        )""",
    "audit_log": """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            action TEXT,              -- 审批/驳回/修改/派单/发送
            target TEXT,              -- 表+id
            before TEXT,
            after TEXT,
            time TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "sessions": """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT,
            customer_id INTEGER,
            context TEXT,             -- 会话上下文
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "todos": """
        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            task TEXT,                -- 待办事项（如：首联超时/SOP跟进）
            due_at TEXT,
            done INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )""",
    "decisions": """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now','localtime')),
            kind TEXT,                -- score/invite/noshow/transition/approve/reject/dispatch
            customer_id INTEGER,
            user TEXT,
            context TEXT,             -- 决策输入+结果 JSON（匿名可喂沉淀证据）
            outcome TEXT DEFAULT '',  -- 后续结果回填（邀约到店/未到店、成交/流失）
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""",
    "meta": """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )""",
    "design_plans": """
        CREATE TABLE IF NOT EXISTS design_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            version INTEGER DEFAULT 1,    -- 方案版本（迭代递增）
            style TEXT,                   -- 设计风格（新中式/奶油诧寂/现代简约…）
            points TEXT,                  -- 设计要点（分区/材质/收纳/灯光…）
            status TEXT DEFAULT '初稿',    -- 初稿/评审中/已定稿/已否决
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )""",
    "quotes": """
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            total REAL DEFAULT 0,         -- 估算总价（按面积套算）
            discount REAL DEFAULT 1.0,    -- 折扣（0.98=98折；低于需审批）
            status TEXT DEFAULT '草稿',    -- 草稿/待审批/已审批/已否决/已签约
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )""",
    "site_reports": """
        CREATE TABLE IF NOT EXISTS site_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            stage TEXT,                   -- 当前施工阶段（水电/防水/泥木/油漆/安装…）
            content TEXT,                 -- 日报内容
            reporter TEXT,                -- 报告人（项目经理）
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )""",
    "inspections": """
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            node TEXT,                    -- 验收节点：水电/防水/泥木/油漆/竣工
            result TEXT DEFAULT '待验收',  -- 待验收/合格/整改
            checked_by TEXT,
            checked_at TEXT,
            note TEXT,
            UNIQUE(project_id, node),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )""",
    "quote_templates": """
        CREATE TABLE IF NOT EXISTS quote_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT,                 -- 分类（一、客餐厅门厅过道 / 柜体柜门 / 大理石类）
            item TEXT,                    -- 项目名称
            spec TEXT,                    -- 工艺/规格说明
            unit TEXT,                    -- 单位
            unit_price REAL DEFAULT 0,    -- 单价（元）
            source TEXT,                  -- 制安预算/成品定制/主材估价
            sort INTEGER DEFAULT 0
        )""",
    "quote_items": """
        CREATE TABLE IF NOT EXISTS quote_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER,
            section TEXT,                 -- 分类（继承模板）
            item TEXT,
            spec TEXT,
            unit TEXT,
            unit_price REAL DEFAULT 0,
            qty REAL DEFAULT 0,           -- 工程量（按面积估算后待设计师复核）
            amount REAL DEFAULT 0,        -- qty × unit_price
            est INTEGER DEFAULT 0,        -- 1=估算工程量（量房后需修正）
            sort INTEGER DEFAULT 0,
            FOREIGN KEY(quote_id) REFERENCES quotes(id)
        )""",
    "payments": """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER,
            stage TEXT,                   -- 签约/阶段验收/验收（对应 payment_stages）
            amount REAL DEFAULT 0,        -- 本次实收金额（元）
            method TEXT DEFAULT '',       -- 转账/刷卡/现金/其他
            paid_at TEXT DEFAULT '',      -- 收款日期
            operator TEXT DEFAULT '',     -- 经办人
            note TEXT DEFAULT '',         -- 备注
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(quote_id) REFERENCES quotes(id)
        )""",
    "soft_furnishings": """
        CREATE TABLE IF NOT EXISTS soft_furnishings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            category TEXT,                -- 家具/灯具/窗帘/布艺/装饰
            name TEXT,                    -- 品名
            spec TEXT DEFAULT '',         -- 规格/型号
            qty REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            amount REAL DEFAULT 0,        -- qty × unit_price
            status TEXT DEFAULT '待确认',  -- 待确认/已确认/已下单
            note TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(project_id) REFERENCES projects(id)
        )""",
    "after_sales": """
        CREATE TABLE IF NOT EXISTS after_sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            customer_id INTEGER,
            kind TEXT,                    -- 质保登记/售后工单/回访
            title TEXT,
            content TEXT DEFAULT '',
            status TEXT DEFAULT '待处理',  -- 待处理/处理中/已关闭
            warranty_type TEXT DEFAULT '', -- 整体/防水（质保登记用）
            warranty_until TEXT DEFAULT '',-- 质保截止（竣工+年限）
            assignee TEXT DEFAULT '',
            result TEXT DEFAULT '',
            created_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY(project_id) REFERENCES projects(id),
            FOREIGN KEY(customer_id) REFERENCES customers(id)
        )""",
}


def hash_pwd(password: str) -> str:
    salt = b"homedesigngroup-v1"  # 固定盐(开发期)；上线前换随机盐
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000).hex()


def main():
    # 1. 目录
    for d in DIRS:
        os.makedirs(d, exist_ok=True)
    print(f"[init] 目录就绪: {len(DIRS)} 个")

    # 2. 建库建表
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    created = []
    for name, ddl in TABLES.items():
        cur.execute(ddl)
        created.append(name)
    # 3. 版本
    cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)", (SCHEMA_VERSION,))
    cur.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('company', ?)", (COMPANY,))
    # 4. 默认账号（幂等）
    cur.execute("SELECT COUNT(*) FROM users WHERE account='admin'")
    if cur.fetchone()[0] == 0:
        cur.execute(
            "INSERT INTO users(account, pwd_hash, role, company) VALUES(?,?,?,?)",
            ("admin", hash_pwd("12345678"), "主管", COMPANY),
        )
        print("[init] 默认账号已创建: admin / 12345678（请尽快修改）")
    else:
        print("[init] 默认账号已存在，跳过")
    conn.commit()
    conn.close()
    print(f"[init] 数据库就绪: {DB_PATH}")
    print(f"[init] 表: {', '.join(created)} | schema_version={SCHEMA_VERSION}")
    print("[init] 完成（幂等，可重复执行）")


if __name__ == "__main__":
    main()
