"""YOLO 任务管理器包（中文版本）。

该包提供了 ``YoloTaskManager`` 类和一个默认的存储后端 ``LocalFileSystemStorage``。
用户可以使用这些类来管理多用户的 YOLO 模型训练、推理和模型保存等任务。

示例用法::
    from yolo_task_manager_cn import YoloTaskManager, LocalFileSystemStorage

    # 创建存储后端，所有模型将保存到指定目录
    storage = LocalFileSystemStorage(root="/data/models")

    # 创建任务管理器
    manager = YoloTaskManager(storage_backend=storage, default_device="cpu")

    # 提交训练任务
    run_id = manager.train(
        user_id="alice",
        base_model="yolov8n.pt",
        dataset_dir="/datasets/alice/vehicles",
        epochs=5,
        run_name="veh_v1",
        callbacks={"on_metrics": lambda r,e,m: print(e, m)},
    )

"""

from .manager import YoloTaskManager
from .storage.local_fs import LocalFileSystemStorage
from .storage.base import IStorage, ModelMeta

__all__ = [
    "YoloTaskManager",
    "LocalFileSystemStorage",
    "IStorage",
    "ModelMeta",
]
