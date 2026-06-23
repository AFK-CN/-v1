# 视频下载队列 ID 截断故障记录

记录时间：2026-06-19
状态：已修复并验证

## 1. 故障现象

下载任务第一次完整运行后出现：

- 状态文件显示76条完成、34条失败。
- 队列中只有3条明确失败，另有31条仍停留在 `pending`。
- 日志中的部分 `source_id` 比正确ID少了首字符。
- 程序报告这些截断ID `found: 0`。

典型例子：

```text
正确 source_id：7597450892647992618
错误执行 ID：  597450892647992618

正确 source_id：7520521925358030120
错误执行 ID：  520521925358030120
```

## 2. 根因

旧脚本使用进程替换直接给循环提供ID：

```bash
while IFS= read -r source_id; do
  python -m tools.video_learning ...
done < <(jq -r '...' "$QUEUE")
```

循环内启动的 Python、FFmpeg 或视频处理依赖继承了同一个标准输入。子进程读取标准输入时，会从队列ID流中消费字节，导致后续行首字符被吞掉。

这不是源数据ID错误，也不是JSON字符串/数字类型错误，而是父循环和子进程共享标准输入造成的数据竞争。

## 3. 修复

修改文件：

`tools/run_jianghushuo_all_directions_download.sh`

修复包含两层：

1. 启动前把本轮待处理ID冻结到独立临时文件：

```bash
WORKLIST="$(mktemp)"
jq -r '.items[] | select(.status == "pending" or .status == "failed") | .source_id' "$QUEUE" >"$WORKLIST"
```

2. 子 Python 进程强制从 `/dev/null` 读取标准输入：

```bash
python -m tools.video_learning ... < /dev/null
```

循环只读取冻结后的任务文件：

```bash
done <"$WORKLIST"
```

## 4. 回归测试

测试文件：

`tests/test_jianghushuo_download_plan.py`

测试用例：

`test_queue_runner_isolates_child_stdin_from_source_id_worklist`

验证内容：

- 脚本必须创建独立 `WORKLIST`。
- 子进程必须包含 `< /dev/null`。

修复后测试3项全部通过。

## 5. 实际验证

修复前误留的31条 `pending` 加3条失败，共34条重新执行：

- 成功恢复：32条
- 最终仍无视频：2条
- 最终目标完整素材：127/129

剩余两条不是本故障导致：它们只有文字元数据，没有可用视频下载地址。

## 6. 永久规则

以后所有“读取任务清单并在循环内启动子进程”的脚本必须遵守：

- 先生成不可变任务快照，再进入循环。
- 子进程默认使用 `< /dev/null`，除非明确需要交互输入。
- 不允许子进程继承任务清单的标准输入。
- 队列状态更新不能同时改变当前循环正在读取的输入源。
- 任务完成后必须核对：计划ID、实际执行ID、manifest ID三者完全一致。

如果再次出现大量 `found: 0`，第一时间比较日志ID长度和原始队列ID，不要直接判断为源数据缺失。
