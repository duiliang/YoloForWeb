# -*- coding: utf-8 -*-
"""
YOLO 任务管理核心类（中文版本）。

`YoloTaskManager` 用于协调多用户的模型训练、推理和模型导出。通过全局信号量和用户级信号量控制并发数，
并使用线程池在后台运行长时间的训练任务。运行状态持久化到 MySQL，便于掉电恢复。训练指标同样写入 MySQL。
使用本类时，请确保环境已安装 `ultralytics` 库。
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ultralytics import YOLO

from .storage.base import IStorage
from .storage.mysql import MySQLRunStateStorage
from .metrics import MetricsStorage


class YoloTaskManager(object):
    """YOLO 任务管理器。"""

    def __init__(
        self,
        storage_backend,
        mysql_cfg,
        default_device="cpu",
        global_limit=1,
        per_user_limit=1,
        max_workers=None,
    ):
        # 存储后端
        self.storage_backend = storage_backend
        self.default_device = default_device
        # 全局信号量和用户级信号量
        self.global_sem = threading.Semaphore(global_limit)
        self.user_sems = {}
        # 线程池用于执行后台任务
        if max_workers is None:
            max_workers = max(2, global_limit * 2)
        self.pool = ThreadPoolExecutor(max_workers=max_workers)
        # MySQL 持久化
        self.metrics_db = MetricsStorage(**mysql_cfg)
        self.run_db = MySQLRunStateStorage(**mysql_cfg)
        # 从数据库加载历史 run 状态
        self._runs = self.run_db.load_all() or {}

    def _get_user_sem(self, user_id):
        """获取用户的信号量，如不存在则创建。"""
        if user_id not in self.user_sems:
            self.user_sems[user_id] = threading.Semaphore(1)
        return self.user_sems[user_id]

    # -----------------------------------------------
    # 公共 API

    def train(self, user_id, base_model, dataset_dir, epochs, run_name, callbacks=None):
        """提交训练任务，并返回 run_id。"""
        callbacks = callbacks or {}
        run_id = str(uuid.uuid4())
        # 初始化运行状态
        self._runs[run_id] = {
            "user_id": user_id,
            "run_name": run_name,
            "base_model": base_model,
            "dataset_dir": dataset_dir,
            "epochs": epochs,
            "future": None,
            "callbacks": callbacks,
            "final_model_path": None,
        }
        # 提交后台任务
        future = self.pool.submit(self._train_job, run_id)
        self._runs[run_id]["future"] = future
        return run_id

    def infer(self, user_id, model_name, images, conf=0.25, iou=0.45):
        """对一组图片进行推理。"""
        # 获取模型路径并加载
        model_path = self.storage_backend.get_model_path(user_id, model_name)
        model = YOLO(str(model_path))
        results_list = []
        for img_path in images:
            preds = model(img_path, conf=conf, iou=iou)
            simple_preds = []
            for pred in preds:
                boxes = getattr(pred, "boxes", [])
                for box in boxes:
                    simple_preds.append({
                        "bbox": [float(box.x1), float(box.y1), float(box.x2), float(box.y2)],
                        "score": float(box.conf),
                        "label": int(box.cls),
                    })
            results_list.append({"image": img_path, "predictions": simple_preds})
        return results_list

    def list_models(self, user_id):
        """列出用户的所有模型。"""
        return self.storage_backend.list_models(user_id)

    def delete_model(self, user_id, model_name):
        """删除用户的指定模型。"""
        return self.storage_backend.delete_model(user_id, model_name)

    # -----------------------------------------------
    # 内部实现

    def _train_job(self, run_id):
        """内部方法：执行实际训练流程。"""
        state = self._runs[run_id]
        user_id = state["user_id"]
        base_model = state["base_model"]
        dataset_dir = state["dataset_dir"]
        epochs = state["epochs"]
        callbacks = state["callbacks"]
        user_sem = self._get_user_sem(user_id)
        # 进入并发控制区
        self.global_sem.acquire()
        user_sem.acquire()
        try:
            # 创建模型并开始训练
            model = YOLO(base_model)
            results = model.train(data=dataset_dir, epochs=epochs, device=self.default_device)
            # 每个 epoch 保存指标
            on_metrics = callbacks.get("on_metrics")
            try:
                box_losses = results.box.losses
                box_maps = results.box.maps
            except Exception:
                box_losses = []
                box_maps = []
            for idx in range(epochs):
                loss = float(box_losses[idx]) if idx < len(box_losses) else 0.0
                mAP = float(box_maps[idx]) if idx < len(box_maps) else 0.0
                metrics = {"loss": loss, "mAP": mAP}
                # 保存到 MySQL
                self.metrics_db.save_metric(run_id, idx + 1, metrics)
                # 调用回调
                if on_metrics:
                    try:
                        on_metrics(run_id, idx + 1, metrics)
                    except Exception:
                        pass
            # 保存模型文件
            final_pt = Path(results.save_dir) / "weights" / "best.pt"
            saved_path = self.storage_backend.save_model(
                user_id,
                final_pt,
                state["run_name"],
                labels=getattr(results, "names", None),
            )
            # 更新状态
state["final_model_path"] = str(saved_path)
            # 持久化到 MySQL
            self.run_db.save(
                run_id,
                {
                    "user_id": user_id,
                    "run_name": state["run_name"],
                    "base_model": base_model,
                    "dataset_dir": dataset_dir,
                    "epochs": epochs,
                    "final_model_path": str(saved_path),
                },
            )
        finally:
            user_sem.release()
            self.global_sem.release()
