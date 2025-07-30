# YoloTaskManager 说明文档

>  **Beta 0.2** — 面向多用户、离线环境的 YOLO 训练/推理核心类。
> 仅提供 **纯 Python API**，无需绑定任何 Web 框架，后端工程师可按需接入 Flask / FastAPI / Celery 等。
>
> *本文件聚焦类设计与用法，部署细节请交由上层服务处理。*

---

## 1. 项目定位

| 关键特性        | 说明                                                                                                                    |
| ----------- | --------------------------------------------------------------------------------------------------------------------- |
| **框架无关**    | 依赖 Python 3.10+ 与 `ultralytics >= 8.2`；其余仅标准库                                                                         |
| **多用户隔离**   | 所有持久化路径自动拼接 `user_id`；**文件上传/下载由上层框架负责**，类中只接收本地路径或对象存储 URI                                                           |
| **可插拔存储**   | 默认 `LocalFileSystemStorage`；如需对象存储/数据库等场景，可自行实现 `IStorage` 接口（本文档不再赘述）                                                |
| **并发安全**    | 内置 `Scheduler` + `DeviceManager`<br>  - `Semaphore` 控制 **GLOBAL\_LIMIT / PER\_USER\_LIMIT**<br>  - 单 GPU 同样适用，任务串行或排队 |
| **实时指标回调**  | 通过回调函数向外暴露训练指标，**示例采用 SSE** 推流；若需双向控制可自行换 WebSocket                                                                   |
| **离线预训练权重** | 所有训练均基于 **官方 YOLOv8 预训练权重** 做二次微调；在无外网环境下需提前把 `yolov8*.pt` 拷贝/挂载到本地 `pretrained/` 目录                                  |

---

## 2. 快速上手

### 2.1 预训练模型准备（离线环境必读）

1. 前往有外网的机器下载所需权重，例如：

   ```bash
   wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
   wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8s.pt
   # ... 按需下载更多体量
   ```
2. 将 `*.pt` 文件拷贝至 K8s 集群共享卷或本地目录，例如 `/data/dl-platform/pretrained/`。
3. 在调用 `train()` 时，通过 `base_model="/data/dl-platform/pretrained/yolov8n.pt"` 传绝对路径。

> **Tips**：
>
> * Ultralytics 会把权重信息登记到 `$ULTRALYTICS_HOME/weights_cache.yaml`（默认 `~/.config/ultralytics`；可通过环境变量修改）。无论权重来自 URL 还是本地路径，登记后均 **不再访问外网**。
> * 推荐把常用权重打包到 Docker 镜像或使用 InitContainer 提前解压到共享卷。

```python
from yolo_task_manager import YoloTaskManager
from yolo_task_manager.storage.local_fs import LocalFileSystemStorage

mgr = YoloTaskManager(
    storage_backend=LocalFileSystemStorage(root="/data/dl-platform"),
    default_device="cuda:0"   # 单 GPU 亦可设为 "cuda:0" / "cpu"
)

run_id = mgr.train(
    user_id="alice",
    base_model="yolov8n.pt",
    dataset_dir="/datasets/alice/vehicles",
    epochs=100,
    run_name="veh_v1",
    callbacks={
        "on_metrics": lambda r,e,m: queue.put(m)  # 推送给 SSE 生产者
    }
)
```

**SSE 示例（Flask ≥ 2.2）**

```python
@app.get("/api/metrics")
def stream_metrics():
    def gen():
        while True:
            msg = queue.get()
            yield f"data: {json.dumps(msg)}\n\n"
    return Response(gen(), mimetype="text/event-stream")
```

---

## 3. 公共 API（同步阻塞）

| 方法               | 功能                       | 关键参数                                                             | 返回值                |
| ---------------- | ------------------------ | ---------------------------------------------------------------- | ------------------ |
| `train()`        | 新建训练任务                   | `user_id, base_model, dataset_dir, epochs, run_name, callbacks`  | `run_id`           |
| `resume()`       | **断点续训**（若 `last.pt` 存在） | `user_id, run_id`                                                | None               |
| `stop()`         | 终止训练                     | `user_id, run_id`                                                | `bool`             |
| `infer()`        | 推理（批量图片/视频）              | `user_id, model_name, images, conf, iou`                         | `List[Prediction]` |
| `export()`       | **模型导出**                 | `user_id, model_name, fmt` (`onnx` / `engine` / `torchscript` …) | `Path`             |
| `list_models()`  | 列出该用户全部模型                | `user_id`                                                        | `List[ModelMeta]`  |
| `delete_model()` | 删除模型                     | `user_id, model_name`                                            | `bool`             |

> *`resume()` 可选但推荐：任何 Pod 重启或 OOM 后可无痛接续训练。*

---

## 4. StorageBackend 约定

```python
class IStorage(Protocol):
    def save_model(self, user_id: str, src_path: Path, model_name: str, labels: list[str]): ...
    def list_models(self, user_id: str) -> list[ModelMeta]: ...
    def delete_model(self, user_id: str, model_name: str) -> bool: ...
    def get_model_path(self, user_id: str, model_name: str) -> Path: ...
```

### 内置实现

* **LocalFileSystemStorage** — 将文件保存至 `/root/{user_id}/models/`（或初始化时配置的根目录）。

> 高级用户可参考 `yolo_task_manager/storage/base.py` 自行扩展对象存储、网络文件系统等后端，本 README 不再提供示例。

