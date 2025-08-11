# -*- coding: utf-8 -*-
"""MySQL 运行状态存储实现。"""

import json
import threading


class MySQLRunStateStorage(object):
    """将训练任务的运行状态持久化到 MySQL。"""

    def __init__(self, host, port, user, password, database, table="runs"):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.table = table
        self._conn = None
        self._lock = threading.Lock()

    def _get_connection(self):
        """获取数据库连接，如未连接则创建。"""
        if self._conn:
            return self._conn
        with self._lock:
            if self._conn:
                return self._conn
            conn = None
            try:
                import pymysql
                conn = pymysql.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.database,
                    charset="utf8mb4",
                )
            except Exception:
                try:
                    import mysql.connector
                    conn = mysql.connector.connect(
                        host=self.host,
                        port=self.port,
                        user=self.user,
                        password=self.password,
                        database=self.database,
                        charset="utf8mb4",
                    )
                except Exception as e:
                    raise RuntimeError("无法连接 MySQL: %s" % e)
            cur = conn.cursor()
            create_sql = (
                "CREATE TABLE IF NOT EXISTS `%s` (" % self.table
                + "run_id VARCHAR(64) PRIMARY KEY,"
                + "data JSON,"
                + "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                + ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            )
            cur.execute(create_sql)
            cur.close()
            self._conn = conn
        return self._conn

    def save(self, run_id, data):
        """保存或更新运行状态。"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            sql = (
                "REPLACE INTO `%s` (run_id, data) VALUES (%%s, %%s)" % self.table
            )
            cur.execute(sql, (run_id, json.dumps(data, ensure_ascii=False)))
            conn.commit()
        finally:
            cur.close()

    def load_all(self):
        """加载全部运行状态，返回字典。"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("SELECT run_id, data FROM `%s`" % self.table)
            rows = cur.fetchall()
            result = {}
            for run_id, data in rows:
                try:
                    result[run_id] = json.loads(data)
                except Exception:
                    result[run_id] = {}
            return result
        finally:
            cur.close()
