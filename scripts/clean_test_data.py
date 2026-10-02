# -*- coding: utf-8 -*-
"""清理测试数据（验证脚本用）：按手机号删除客户及其从属记录"""
import sqlite3
import sys

DB = r"H:\AgentProjects\HomeDesignGroup\db\壹城精工.db"
PHONES = ["13888888888", "13999999999"]  # 测试手机号


def clean():
    conn = sqlite3.connect(DB)
    n = 0
    for phone in PHONES:
        ids = [r[0] for r in conn.execute(
            "SELECT id FROM customers WHERE phone=?", (phone,))]
        for cid in ids:
            for tbl in ("messages", "followups", "projects", "todos"):
                conn.execute(f"DELETE FROM {tbl} WHERE customer_id=?", (cid,))
            conn.execute("DELETE FROM customers WHERE id=?", (cid,))
            n += 1
    conn.commit()
    conn.close()
    print(f"[clean] 删除测试客户 {n} 个")
    return n


if __name__ == "__main__":
    clean()
