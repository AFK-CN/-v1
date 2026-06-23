from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tools import video_learning

from .asset_builder import build_candidate_assets
from .schemas import SYSTEM_DIR, as_posix, now_iso
from .task_runner import create_task, finish_task, find_task_dir, move_task_dir, tasks_root


WEB_PREFIX = "web_"
WEB_STATE_FILE = "web_console_state.json"


def web_state_path(root: Path) -> Path:
    return root / SYSTEM_DIR / "state" / WEB_STATE_FILE


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def load_web_state(root: Path) -> dict[str, Any]:
    state = read_json_file(web_state_path(root), {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("server_started_at", "")
    state.setdefault("worker_started_at", "")
    state.setdefault("worker_heartbeat_at", "")
    state.setdefault("worker_current_task", "")
    state.setdefault("worker_status", "offline")
    state.setdefault("worker_error", "")
    return state


def save_web_state(root: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now_iso()
    write_json_file(web_state_path(root), state)


def task_dirs(root: Path) -> list[Path]:
    root_dir = tasks_root(root)
    if not root_dir.exists():
        return []
    dirs: list[Path] = []
    for status in ("pending", "running", "done", "failed", "paused"):
        current = root_dir / status
        if not current.exists():
            continue
        for task_dir in sorted(current.iterdir()):
            if task_dir.is_dir():
                dirs.append(task_dir)
    return dirs


def read_task(task_dir: Path) -> dict[str, Any]:
    status = read_json_file(task_dir / "status.json", {})
    if not isinstance(status, dict):
        status = {}
    request = read_json_file(task_dir / "request.json", {})
    if not isinstance(request, dict):
        request = {}
    summary = ""
    summary_path = task_dir / "summary_report.md"
    if summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8").replace("# 摘要报告", "").strip()
    status["request"] = request
    status["summary"] = summary
    status["task_dir"] = as_posix(task_dir)
    return status


def list_tasks(root: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for task_dir in task_dirs(root):
        data = read_task(task_dir)
        if str(data.get("task_name", "")).startswith(WEB_PREFIX):
            tasks.append(data)
    tasks.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return tasks


def candidate_batches(root: Path) -> list[dict[str, Any]]:
    path = root / SYSTEM_DIR / "assets" / "candidate_topics.jsonl"
    if not path.exists():
        return []

    grouped: dict[str, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            direction = str(item.get("领域") or "未归类").strip() or "未归类"
            grouped.setdefault(direction, []).append(item)

    batches: list[dict[str, Any]] = []
    records, _, _ = video_learning.load_unique_records(root)
    by_id = video_learning.records_by_source_id(records)
    queue_items = video_learning.load_queue(root).get("items", [])

    for direction, items in grouped.items():
        sorted_items = sorted(items, key=lambda row: (float(row.get("score") or 0), -int(row.get("rank") or 999)), reverse=True)
        source_ids = [str(item.get("source_id") or "") for item in sorted_items if item.get("source_id")]
        downloaded = 0
        ready = 0
        queued = 0
        for source_id in source_ids:
            record = by_id.get(source_id)
            if not record:
                continue
            artifact = root / "01_Case_Cleaning" / "video_learning" / "video_artifacts" / f"{record.platform}_{record.source_id}" / "source.mp4"
            if artifact.exists():
                downloaded += 1
            if any(str(item.get("source_id")) == source_id and str(item.get("status")) == "pending" for item in queue_items):
                queued += 1
        ready = sum(1 for source_id in source_ids if _batch_item_is_downloaded(root, by_id.get(source_id)))
        batches.append(
            {
                "direction": direction,
                "count": len(source_ids),
                "top_titles": [_candidate_title(item) for item in sorted_items[:3]],
                "source_ids": source_ids,
                "downloaded_count": downloaded,
                "queued_count": queued,
                "ready_count": ready,
                "has_video_download_url_count": sum(1 for item in sorted_items if item.get("has_video_download_url")),
            }
        )
    batches.sort(key=lambda item: (item["count"], item["direction"]), reverse=True)
    return batches


def _batch_item_is_downloaded(root: Path, record: video_learning.NormalizedRecord | None) -> bool:
    if not record:
        return False
    artifact = root / "01_Case_Cleaning" / "video_learning" / "video_artifacts" / f"{record.platform}_{record.source_id}" / "source.mp4"
    return artifact.exists()


def _candidate_title(item: dict[str, Any]) -> str:
    titles = item.get("可生成标题") or []
    if isinstance(titles, list) and titles:
        return str(titles[0])
    return str(item.get("title") or "")


def dashboard_state(root: Path) -> dict[str, Any]:
    queue_status = video_learning.learning_status(root)
    manifest = video_learning.load_manifest(root)
    batches = candidate_batches(root)
    tasks = list_tasks(root)
    latest_downloads: dict[str, dict[str, Any]] = {}
    for task in tasks:
        request = task.get("request") if isinstance(task.get("request"), dict) else {}
        if request.get("action") != "download":
            continue
        direction = str(request.get("direction") or "")
        if direction and direction not in latest_downloads:
            latest_downloads[direction] = {
                "task_status": task.get("task_status", ""),
                "updated_at": task.get("updated_at", ""),
                "summary": task.get("summary", ""),
            }
    for batch in batches:
        batch["latest_download"] = latest_downloads.get(str(batch.get("direction") or ""), {})
    state = load_web_state(root)
    return {
        "root": as_posix(root),
        "generated_at": now_iso(),
        "queue_status": queue_status,
        "manifest_completed": sum(1 for item in manifest.get("items", {}).values() if item.get("status") == "completed"),
        "batches": batches,
        "tasks": tasks,
        "web_state": state,
    }


def enqueue_task(root: Path, task_name: str, command: str, request: dict[str, Any]) -> dict[str, Any]:
    task = create_task(root, task_name, command=command, payload=request)
    task_dir = root / task["task_dir"]
    status_path = task_dir / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["task_type"] = "web"
    status["updated_at"] = now_iso()
    write_json_file(status_path, status)
    return task


def queue_scan_task(root: Path, top_n: int) -> dict[str, Any]:
    return enqueue_task(
        root,
        "web_scan_assets",
        f"web console: scan assets (top_n={max(top_n, 1)})",
        {"action": "scan", "top_n": max(top_n, 1)},
    )


def queue_download_task(root: Path, direction: str, source_ids: list[str]) -> dict[str, Any]:
    safe_direction = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in direction).strip("_") or "batch"
    return enqueue_task(
        root,
        f"web_download_{safe_direction}",
        f"web console: download batch (direction={direction or 'manual'})",
        {"action": "download", "direction": direction, "source_ids": source_ids},
    )


def run_scan_task(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    top_n = max(int(request.get("top_n") or 10), 1)
    result = build_candidate_assets(root, top_n=top_n)
    return {
        "summary": f"候选资产已生成，方向数 {result['directions']}，候选数 {result['candidate_topics_count']}",
        "outputs": [
            "14_KB_System/assets/candidate_topics.jsonl",
            "14_KB_System/assets/candidate_top10_by_category.md",
            "14_KB_System/assets/candidate_method_cards.md",
        ],
        "result": result,
    }


def _candidate_source_ids(root: Path, direction: str) -> list[str]:
    path = root / SYSTEM_DIR / "assets" / "candidate_topics.jsonl"
    if not path.exists():
        return []
    source_ids: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(item.get("领域") or "") != direction:
                continue
            source_id = str(item.get("source_id") or "")
            if source_id:
                source_ids.append(source_id)
    return source_ids


def run_download_task(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    direction = str(request.get("direction") or "").strip()
    source_ids = [str(item) for item in request.get("source_ids") or [] if str(item).strip()]
    if direction and not source_ids:
        source_ids = _candidate_source_ids(root, direction)
    if not source_ids:
        raise ValueError("no source ids provided for download")
    queue_result = video_learning.select_deep_learning(root, source_ids=set(source_ids))
    download_result = video_learning.download_selected_media(root, source_ids=set(source_ids))
    outputs = [queue_result["queue"], download_result["report"]]
    outputs.extend(download_result.get("downloaded_files", []))
    summary = (
        f"方向 {direction or '未命名批次'} 已排队 {queue_result['queued']} 条，"
        f"下载完成 {download_result['downloaded']} 条，复用 {download_result['reused']} 条"
    )
    return {"summary": summary, "outputs": outputs, "result": {"queue": queue_result, "download": download_result}}


def process_web_task(root: Path, task_dir: Path) -> dict[str, Any]:
    status = read_json_file(task_dir / "status.json", {})
    request = read_json_file(task_dir / "request.json", {})
    task_name = str(status.get("task_name") or "")
    if task_name == "web_scan_assets":
        return run_scan_task(root, request if isinstance(request, dict) else {})
    if task_name.startswith("web_download_"):
        return run_download_task(root, request if isinstance(request, dict) else {})
    raise ValueError(f"unknown web task: {task_name}")


def run_pending_web_tasks_once(root: Path, state: dict[str, Any] | None = None) -> bool:
    pending_root = tasks_root(root) / "pending"
    if not pending_root.exists():
        return False
    for task_dir in sorted(pending_root.iterdir()):
        if not task_dir.is_dir():
            continue
        status = read_json_file(task_dir / "status.json", {})
        if not isinstance(status, dict):
            continue
        task_name = str(status.get("task_name") or "")
        if not task_name.startswith(WEB_PREFIX):
            continue
        if state is not None:
            state["worker_status"] = "running"
            state["worker_current_task"] = task_name
            state["worker_heartbeat_at"] = now_iso()
            save_web_state(root, state)
        move_task_dir(root, str(status.get("task_id")), "running")
        running_dir = find_task_dir(root, str(status.get("task_id")))
        try:
            result = process_web_task(root, running_dir)
            finish_task(
                root,
                str(status.get("task_id")),
                "done",
                summary=str(result.get("summary") or ""),
                outputs=[str(item) for item in result.get("outputs", [])],
            )
        except Exception as exc:
            finish_task(
                root,
                str(status.get("task_id")),
                "failed",
                summary=f"任务失败：{exc}",
                errors=[str(exc)],
            )
        if state is not None:
            state["worker_status"] = "idle"
            state["worker_current_task"] = ""
            state["worker_heartbeat_at"] = now_iso()
            save_web_state(root, state)
        return True
    return False


def worker_loop(root: Path, poll_interval: float = 2.0, stop_event: threading.Event | None = None) -> None:
    state = load_web_state(root)
    state["worker_started_at"] = now_iso()
    state["worker_status"] = "idle"
    save_web_state(root, state)
    while stop_event is None or not stop_event.is_set():
        try:
            processed = run_pending_web_tasks_once(root, state)
            state["worker_status"] = "idle"
            state["worker_heartbeat_at"] = now_iso()
            save_web_state(root, state)
            if not processed:
                time.sleep(poll_interval)
        except Exception as exc:
            state["worker_status"] = "error"
            state["worker_error"] = str(exc)
            state["worker_heartbeat_at"] = now_iso()
            save_web_state(root, state)
            time.sleep(max(poll_interval, 1.0))


def start_worker_thread(root: Path, poll_interval: float = 2.0) -> tuple[threading.Thread, threading.Event]:
    stop_event = threading.Event()
    thread = threading.Thread(target=worker_loop, args=(root, poll_interval, stop_event), daemon=True)
    thread.start()
    return thread, stop_event


def _escape_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def render_dashboard_html(root: Path) -> str:
    state = dashboard_state(root)
    initial_state = _escape_json(state)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>知识库通用控制台</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #d8dde3;
      --text: #1f2328;
      --muted: #66707a;
      --accent: #0f62fe;
      --accent-soft: #e8f0ff;
      --warn: #af601a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    header {{
      padding: 20px 24px 12px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, #fff, #f8fafc);
    }}
    h1 {{ margin: 0 0 8px; font-size: 22px; }}
    .meta {{ color: var(--muted); font-size: 13px; }}
    main {{ padding: 20px 24px 28px; display: grid; gap: 16px; }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .toolbar input {{
      width: 100px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
    }}
    button {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 12px;
      background: var(--panel);
      color: var(--text);
      cursor: pointer;
    }}
    button.primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }}
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    section h2 {{
      margin: 0 0 12px;
      font-size: 16px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    th, td {{
      border-top: 1px solid var(--line);
      padding: 8px 6px;
      vertical-align: top;
      text-align: left;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      background: #fafbfc;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
    }}
    .muted {{ color: var(--muted); }}
    .task-ok {{ color: #1f7a1f; }}
    .task-fail {{ color: #b42318; }}
    .row-actions {{ white-space: nowrap; }}
    .batch-titles {{ max-width: 420px; color: var(--muted); }}
    .download-result {{ min-width: 220px; color: var(--muted); }}
    .download-result strong {{ color: var(--text); font-weight: 600; }}
    .empty {{ color: var(--muted); padding: 8px 0; }}
    code {{ background: #f1f3f5; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <header>
    <h1>知识库通用控制台</h1>
    <div class="meta">本地控制台，面向批次。扫描、下载、队列和日志都在这里看，深度学习仍回到对话里完成。</div>
  </header>
  <main>
    <section>
      <h2>操作</h2>
      <div class="toolbar">
        <label>TopN <input id="top_n" type="number" min="1" value="10" /></label>
        <button class="primary" onclick="runScan()">触发扫描</button>
        <button onclick="refreshState()">刷新状态</button>
      </div>
      <div id="worker-line" class="meta"></div>
    </section>

    <section>
      <h2>批次</h2>
      <div id="batches"></div>
    </section>

    <section>
      <h2>任务</h2>
      <div id="tasks"></div>
    </section>

    <section>
      <h2>队列摘要</h2>
      <div id="queue"></div>
    </section>
  </main>
  <script id="initial-state" type="application/json">{initial_state}</script>
  <script>
    const initialState = JSON.parse(document.getElementById('initial-state').textContent);

    async function api(path, options = {{}}) {{
      const response = await fetch(path, {{
        headers: {{ 'Content-Type': 'application/json' }},
        ...options,
      }});
      if (!response.ok) {{
        const text = await response.text();
        throw new Error(text || response.statusText);
      }}
      return response.json();
    }}

    async function runAction(action, payload = {{}}) {{
      const body = JSON.stringify(payload);
      const route = action === 'scan' ? '/api/actions/scan' : '/api/actions/download';
      await api(route, {{
        method: 'POST',
        body,
      }});
      await refreshState();
    }}

    async function runScan() {{
      await runAction('scan', {{
        top_n: Number(document.getElementById('top_n').value || 10),
      }});
    }}

    async function downloadBatch(direction, sourceIds) {{
      await runAction('download', {{
        direction,
        source_ids: sourceIds,
      }});
    }}

    function renderBatches(state) {{
      const target = document.getElementById('batches');
      const batches = state.batches || [];
      if (!batches.length) {{
        target.innerHTML = '<div class="empty">还没有候选批次。先触发一次扫描。</div>';
        return;
      }}
      const rows = batches.map(batch => {{
        const titles = (batch.top_titles || []).filter(Boolean).join('；');
        const ready = batch.ready_count ?? 0;
        const latest = batch.latest_download || {{}};
        const result = latest.summary
          ? `<div><strong>${{latest.task_status || ''}}</strong> ${{latest.summary}}</div><div class="muted">${{latest.updated_at || ''}}</div>`
          : '<span class="muted">尚未下载</span>';
        return `
          <tr>
            <td><span class="badge">${{batch.direction}}</span></td>
            <td>${{batch.count || 0}}</td>
            <td>${{batch.downloaded_count || 0}} / ${{batch.count || 0}}</td>
            <td class="download-result">${{result}}</td>
            <td class="batch-titles">${{titles || '-'}}</td>
            <td class="row-actions">
              <button
                class="primary"
                data-direction="${{batch.direction.replaceAll('"', '&quot;').replaceAll("'", '&#39;')}}"
                data-source-ids='${{JSON.stringify(batch.source_ids || []).replaceAll("'", '&#39;')}}'
                onclick="downloadBatch(this.dataset.direction, JSON.parse(this.dataset.sourceIds))"
              >下载批次</button>
            </td>
          </tr>`;
      }}).join('');
      target.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>方向</th>
              <th>条数</th>
              <th>本地文件</th>
              <th>最近下载结果</th>
              <th>Top 标题</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>`;
    }}

    function renderTasks(state) {{
      const target = document.getElementById('tasks');
      const tasks = state.tasks || [];
      if (!tasks.length) {{
        target.innerHTML = '<div class="empty">暂无 web 任务。</div>';
        return;
      }}
      const rows = tasks.map(task => {{
        const status = task.task_status || '';
        const cls = status === 'failed' ? 'task-fail' : (status === 'done' ? 'task-ok' : 'muted');
        const summary = task.summary || '';
        return `
          <tr>
            <td>${{task.task_name || ''}}</td>
            <td class="${{cls}}">${{status || ''}}</td>
            <td>${{task.created_at || ''}}</td>
            <td>${{task.updated_at || ''}}</td>
            <td class="batch-titles">${{summary || '-'}}</td>
          </tr>`;
      }}).join('');
      target.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>任务</th>
              <th>状态</th>
              <th>创建</th>
              <th>更新</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>`;
    }}

    function renderQueue(state) {{
      const target = document.getElementById('queue');
      const queue = state.queue_status || {{}};
      const web = state.web_state || {{}};
      target.innerHTML = `
        <div>队列：pending <code>${{queue.queue_pending ?? 0}}</code>，completed <code>${{queue.queue_completed ?? 0}}</code>，failed <code>${{queue.queue_failed ?? 0}}</code></div>
        <div>manifest completed：<code>${{state.manifest_completed ?? 0}}</code></div>
        <div>worker：<code>${{web.worker_status || 'offline'}}</code>，heartbeat：<code>${{web.worker_heartbeat_at || 'n/a'}}</code>，current：<code>${{web.worker_current_task || 'idle'}}</code></div>`;
      document.getElementById('worker-line').textContent = `worker 状态：${{web.worker_status || 'offline'}}`;
    }}

    async function refreshState() {{
      const state = await api('/api/state');
      renderBatches(state);
      renderTasks(state);
      renderQueue(state);
    }}

    document.getElementById('top_n').value = 10;
    refreshState().catch(err => {{
      console.error(err);
      document.body.insertAdjacentHTML('beforeend', `<pre style="color:#b42318;padding:16px;">${{String(err.message || err)}}</pre>`);
    }});
    setInterval(() => refreshState().catch(console.error), 5000);
  </script>
</body>
</html>
"""


def json_response(handler: BaseHTTPRequestHandler, value: Any, status: int = 200) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def text_response(handler: BaseHTTPRequestHandler, value: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
    payload = value.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def parse_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length else b"{}"
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("request body must be a JSON object")
    return data


class WebConsoleHandler(BaseHTTPRequestHandler):
    root: Path
    worker_thread: threading.Thread | None = None
    worker_stop: threading.Event | None = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            text_response(self, render_dashboard_html(self.root), content_type="text/html; charset=utf-8")
            return
        if parsed.path == "/api/state":
            json_response(self, dashboard_state(self.root))
            return
        json_response(self, {"error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        try:
            body = parse_json_body(self)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, status=400)
            return

        if parsed.path == "/api/actions/scan":
            top_n = int(body.get("top_n") or 10)
            task = queue_scan_task(self.root, top_n)
            json_response(self, {"ok": True, "task": task})
            return

        if parsed.path == "/api/actions/download":
            direction = str(body.get("direction") or "").strip()
            source_ids = [str(item) for item in body.get("source_ids") or [] if str(item).strip()]
            if not direction and not source_ids:
                json_response(self, {"error": "direction or source_ids required"}, status=400)
                return
            task = queue_download_task(self.root, direction, source_ids)
            json_response(self, {"ok": True, "task": task})
            return

        json_response(self, {"error": "not found"}, status=404)


def serve(root: Path, host: str = "127.0.0.1", port: int = 8787, start_worker: bool = True) -> int:
    root = root.resolve()
    state = load_web_state(root)
    state["server_started_at"] = now_iso()
    state["worker_status"] = state.get("worker_status") or "offline"
    save_web_state(root, state)

    worker_thread: threading.Thread | None = None
    stop_event: threading.Event | None = None
    if start_worker:
        worker_thread, stop_event = start_worker_thread(root)

    handler_cls = type("BoundWebConsoleHandler", (WebConsoleHandler,), {"root": root, "worker_thread": worker_thread, "worker_stop": stop_event})
    server = ThreadingHTTPServer((host, port), handler_cls)
    try:
        print(f"Web console ready at http://{host}:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if stop_event is not None:
            stop_event.set()
        server.server_close()
    return 0
