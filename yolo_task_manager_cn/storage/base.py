"""存储后端接口和模型元数据定义（中文版本）。

为了让 ``YoloTaskManager`` 与底层存储解耦，所有模型的保存、列举和删除等操作都通过实现
``IStorage`` 接口来完成。这里定义了一个简单的模型元数据 ``ModelMeta``，以及存储接口的抽象基类。
"""

import abc
import datetime
from pathlib import Path


class ModelMeta(object):
    """模型元数据。

    该类简单存放模型名称、路径、标签列表以及创建时间等信息。
    """

    def __init__(self, model_name, path, labels=None, created_at=None):
        self.model_name = model_name
        # 路径转为绝对路径
        self.path = Path(path).expanduser().resolve()
        self.labels = labels or []
        # 创建时间默认为当前时间
        self.created_at = created_at or datetime.datetime.now()

    def __repr__(self):
        return (
            f"ModelMeta(model_name={self.model_name!r}, path={str(self.path)!r}, "
            f"labels={self.labels!r}, created_at={self.created_at!r})"
        )


class IStorage(object, metaclass=abc.ABCMeta):
    """存储后端抽象基类。

    所有自定义存储后端都应该继承此类并实现下列方法。该接口用于保存模型、列举模型、删除模型
    以及获取模型路径等操作。
    """

    @abc.abstractmethod
    def save_model(self, user_id, src_path, model_name, labels=None):
        """保存模型。

        参数:
            user_id (str): 用户标识，用于隔离不同用户的模型。
            src_path (Path 或 str): 模型文件路径。
            model_name (str): 模型名称（通常是训练任务名称）。
            labels (list, 可选): 标签列表，可以为空。

        返回:
            Path: 保存后的模型文件的绝对路径。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def list_models(self, user_id):
        """列举指定用户的所有模型。

        参数:
            user_id (str): 用户标识。

        返回:
            list[ModelMeta]: 模型元数据列表。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def delete_model(self, user_id, model_name):
        """删除模型。

        参数:
            user_id (str): 用户标识。
            model_name (str): 要删除的模型名称。

        返回:
            bool: 是否删除成功。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_model_path(self, user_id, model_name):
        """获取模型路径。

        参数:
            user_id (str): 用户标识。
            model_name (str): 模型名称。

        返回:
            Path: 模型文件的绝对路径。
        """
        raise NotImplementedError
