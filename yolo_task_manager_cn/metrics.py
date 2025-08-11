# -*- coding: utf-8 -*-
"""
指标存储实现（中文版本）。

该模块定义了一个简单的指标存储接口 ``MetricsStorage``，以及两种实现：
* ``MySQLMetricsStorage`` 将指标写入 MySQL 数据库；
* ``LocalFileMetricsStorage`` 将指标以 JSON 行的形式写入本地文件。

在使用 MySQL 存储时，需要自行安装并配置相关数据库驱动库，例如 `pymysql` 或 `mysql.connector`。
"""
import json
import os
import threading
from datetime import datetime


class MetricsStorage(object):
    """指标存储基类。"""

    def save_metric(self, run_id, epoch, metrics):
        """保存一条指标记录。"""
        raise NotImplementedError


class MySQLMetricsStorage(MetricsStorage):
    """使用 MySQL 存储训练指标的实现。"""

    def __init__(
        self,
        host=None,
        port=3306,
        user="root",
        password="",
        database="yolo",
        table="metrics",
        unix_socket=None,
    ):
        # 保存连接参数
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
                except Exception as e:
                    raise RuntimeError(f"\u65e0\u6cd5\u8fde\u63a5 MySQL: {e}")
            # 创建表
            cur = conn.cursor()
            create_sql = (
                f"CREATE TABLE IF NOT EXISTS `{self.table}` ("
                "id INT AUTO_INCREMENT PRIMARY KEY, "
                "run_id VARCHAR(64), "
                "epoch INT, "
                "metrics JSON, "
                "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;"
            )
            cur.execute(create_sql)
            cur.close()
            self._conn = conn
        return self._conn

    def save_metric(self, run_id, epoch, metrics):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            insert_sql = f"INSERT INTO `{self.table}` (run_id, epoch, metrics) VALUES (%s, %s, %s)"
            cursor.execute(insert_sql, (run_id, epoch, json.dumps(metrics, ensure_ascii=False)))
            conn.commit()
        finally:
            cursor.close()


class LocalFileMetricsStorage(MetricsStorage):
    """将指标写入本地文件。每条记录以独立的 JSON 对象存储在一行。"""

    def __init__(self, file_path):
        self.file_path = file_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        self._lock = threading.Lock()

    def save_metric(self, run_id, epoch, metrics):
        record = {
            "run_id": run_id,
            "epoch": epoch,
            "metrics": metrics,
            "created_at": datetime.utcnow().isoformat(),
        }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with open(self.file_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
