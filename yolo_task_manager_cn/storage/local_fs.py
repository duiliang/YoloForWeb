"""本地文件系统存储后端（中文版本）。

该模块实现了 ``IStorage`` 接口，使用本地磁盘保存模型文件。模型会存储在 ``root/{user_id}/models``
目录下，并使用 ``模型名称_时间戳`` 的方式命名，避免重名冲突。标签信息（如果有）会保存在同名
``.labels`` 文件中。
"""

import shutil
from pathlib import Path

from .base import IStorage, ModelMeta


class LocalFileSystemStorage(IStorage):
    """本地文件系统存储实现。

    参数:
        root (str): 存储根目录，所有用户的模型都存储在此目录下。
    """

    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _ensure_user_dir(self, user_id):
        models_dir = self.root / user_id / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir

    def save_model(self, user_id, src_path, model_name, labels=None):
        models_dir = self._ensure_user_dir(user_id)
        src_path = Path(src_path).expanduser().resolve()
        timestamp = src_path.stat().st_mtime_ns
        suffix = src_path.suffix or ".pt"
        dest_name = f"{model_name}_{timestamp}{suffix}"
        dest_path = models_dir / dest_name
        shutil.copy2(src_path, dest_path)
        if labels:
            labels_path = dest_path.with_suffix(dest_path.suffix + ".labels")
            with open(labels_path, "w", encoding="utf-8") as f:
                f.write("\n".join(labels))
        return dest_path

    def list_models(self, user_id):
        models_dir = self._ensure_user_dir(user_id)
        metas = []
        for item in sorted(models_dir.glob("*")):
            if not item.is_file() or item.name.endswith(".labels"):
                continue
            model_name = item.stem
            labels = []
            labels_path = item.with_suffix(item.suffix + ".labels")
            if labels_path.exists():
                with open(labels_path, "r", encoding="utf-8") as f:
                    labels = [line.strip() for line in f if line.strip()]
            metas.append(ModelMeta(model_name=model_name, path=item, labels=labels))
        return metas

    def delete_model(self, user_id, model_name):
        models_dir = self._ensure_user_dir(user_id)
        deleted = False
        for item in models_dir.glob(f"{model_name}*"):
            if item.is_file():
                item.unlink(missing_ok=True)
                deleted = True
        for labels_file in models_dir.glob(f"{model_name}*.labels"):
            if labels_file.is_file():
                labels_file.unlink(missing_ok=True)
                deleted = True
        return deleted

    def get_model_path(self, user_id, model_name):
        models_dir = self._ensure_user_dir(user_id)
        candidates = [
            p
            for p in models_dir.glob(f"{model_name}*")
            if p.is_file() and not p.name.endswith(".labels")
        ]
        if not candidates:
            raise FileNotFoundError(f"找不到用户 {user_id} 的模型 {model_name}")
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0]
