# -*- coding: utf-8 -*-
"""基于 MySQL 的训练运行状态持久化实现。

该模块提供 ``MySQLRunStateStorage`` 类，用于将训练任务的运行状态
存储到 MySQL 数据库中。这样即便服务掉电或重启，也可以从数据库
中恢复 ``run_id`` 等信息。
"""

import json
import threading


class MySQLRunStateStorage(object):
    """使用 MySQL 保存训练运行状态的简易实现。"""

    def __init__(
        self,
        host=None,
        port=3306,
        user="root",
        password="",
        database="yolo",
        table="runs",
        unix_socket=None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.table = table
        self.unix_socket = unix_socket
        self._conn = None
        self._lock = threading.Lock()

    def _get_connection(self):
        """延迟创建数据库连接并保证线程安全。"""
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
                    unix_socket=self.unix_socket,
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
                        unix_socket=self.unix_socket,
                        charset="utf8mb4",
                    )
                except Exception as e:  # noqa: F841
                    raise RuntimeError("无法连接 MySQL: %s" % e)
            # 创建表
            cur = conn.cursor()
            create_sql = (
                f"CREATE TABLE IF NOT EXISTS `{self.table}` ("
                "run_id VARCHAR(64) PRIMARY KEY, "
                "data JSON, "
                "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            )
            cur.execute(create_sql)
            cur.close()
            self._conn = conn
        return self._conn

    # 公共方法 -------------------------------------------------
    def save(self, run_id, data):
        """保存或更新一条运行状态。"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            sql = f"REPLACE INTO `{self.table}` (run_id, data) VALUES (%s, %s)"
            cur.execute(sql, (run_id, json.dumps(data, ensure_ascii=False)))
            conn.commit()
        finally:
            cur.close()

    def load_all(self):
        """加载所有运行状态，返回字典。"""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT run_id, data FROM `{self.table}`")
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
