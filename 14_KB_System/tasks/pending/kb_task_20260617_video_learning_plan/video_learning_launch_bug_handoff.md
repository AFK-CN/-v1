# 视频深度学习启动失败交接

## 结论

当前已验证：

- `nohup` 单独启动不稳定，进程会很快退出，导致“任务没开始就结束”。
- `screen` 已经把任务放进了脱离当前会话的后台作业里，至少解决了“会话结束导致任务跟着死”的问题。

但尚未验证：

- 任务是否能稳定进入 `learn` 主流程并持续写出下载、转写、切场景结果。
- 是否存在运行时崩溃、依赖冲突或脚本逻辑提前退出。

## 已做的改动

- 新增启动脚本：`tools/run_video_learning_queue.sh`
- 由 `screen` 启动 detached 作业：`jianghushuo_video_learning`
- 日志文件：`14_KB_System/logs/video_learning/jianghushuo_top10x12_download_20260617.log`

## 当前状态

- `screen -ls` 能看到会话存在。
- 日志文件已经被创建并开始写入。
- 日志当前停在启动阶段，内容只有 macOS 的 `objc` / `av` / `cv2` 重复动态库警告，没有看到完成下载、写 manifest 或生成新卡片的结果。
- `01_Case_Cleaning/video_learning/queues/pending_deep_learning.json` 里，姜胡说批次仍有 34 条 `pending`。
- `01_Case_Cleaning/video_learning/state/learning_manifest.json` 仍停留在旧的 7 条完成记录，没有新增这批结果。

## 现象复述

上一次失败的核心现象是：

1. 后台启动命令返回了 PID。
2. 过一段时间后 PID 不存在。
3. 日志为空或几乎为空。
4. 队列和 manifest 没有推进。

这说明问题不只是“没有实时陪跑”，而是作业生命周期没有被稳住，或者进程在 very early stage 就退出了。

## 需要下一会话继续查的根因

优先级从高到低：

1. `tools.video_learning learn` 是否在启动后因运行时错误直接退出。
2. `av` 和 `cv2` 的重复动态库警告是否会触发后续崩溃。
3. `screen` 里的 shell / 环境变量是否和当前终端一致。
4. `tools/run_video_learning_queue.sh` 是否需要更明确的退出码记录和分步日志。

## 下一步建议

- 先把 `learn` 的启动和首个成功标记拆开，确认到底卡在“进入主逻辑之前”还是“下载阶段”。
- 若仍然早退，下一会话直接把 `tools/video_learning.py` 的入口加上更细的启动日志，定位第一处退出点。
