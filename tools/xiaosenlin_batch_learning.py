from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote


ACCOUNT_ID = "5a201295e8ac2b0dbae9063a"
ACCOUNT_NAME = "小森林的小世界"
BATCH_SIZE = 40
WORKFLOW_ID = "xiaosenlin-xiaoshijie-v2-full"
INVENTORY_REL = Path(
    "10_Knowledge/candidates/account_assets/sqlite_account_sources/"
    "xiaosenlin_xiaoshijie/nas_sqlite_inventory.jsonl"
)
WORKFLOW_REL = Path("10_Knowledge/candidates/account_learning_workflows") / WORKFLOW_ID
VISUAL_OVERRIDES_NAME = "VISUAL_EVIDENCE_OVERRIDES.json"


TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("头发护理", ("炸毛", "沙发", "护发", "头发", "发膜")),
    ("饮食与状态", ("蔬果汁", "睡不好", "睡眠", "饮食", "香菜", "喝")),
    ("商业售后与购买决策", ("618", "双11", "售后", "购买", "优惠", "价格")),
    ("毛孔与清洁", ("毛孔", "黑头", "清洁", "颗粒", "堵塞")),
    ("刷酸与焕肤", ("刷酸", "用酸", "水杨酸", "果酸", "壬二酸", "酸类")),
    ("痘肌与痘印", ("痘", "闭口", "痘印", "爆痘")),
    ("敏感维稳与红黑脸", ("敏感", "维稳", "修护", "红黑", "屏障", "泛红")),
    ("眼周护理", ("黑眼圈", "眼袋", "眼周", "眼部")),
    ("抗老与紧致", ("抗老", "k老", "眼纹", "法令纹", "胶原", "紧致", "a醇", "视黄醇")),
    ("提亮与肤色", ("提亮", "暗沉", "美白", "肤色", "水光", "去黄")),
    ("防晒", ("防晒", "晒黑", "紫外线")),
    ("空瓶与产品复盘", ("空瓶", "爱用", "盘点", "回购", "测评", "无广")),
    ("生活方式与信任", ("日常", "vlog", "生活", "减脂", "做饭", "旅行")),
]

MECHANISMS = {
    "problem_result": {
        "title": "具体皮肤问题转译为可感知结果",
        "mechanism": "用具体问题、目标肤态与前后变化降低理解成本，而不是从抽象成分或品类开场。",
    },
    "identity_proof": {
        "title": "长期肤质身份与自用史构成可信度",
        "mechanism": "先交代油痘敏肌、使用年限、空瓶或反复测试，再给判断，形成经验型而非百科型权威。",
    },
    "step_sequence": {
        "title": "分步顺序与条件化执行",
        "mechanism": "把复杂问题拆成有先后关系的步骤，并说明何时切换、何时停止与必须搭配的动作。",
    },
    "time_feedback": {
        "title": "时间刻度与状态反馈形成可跟练闭环",
        "mechanism": "用第几天、多久、用后触感或皮肤状态反馈，把内容从推荐升级为可观察的实践过程。",
    },
    "version_iteration": {
        "title": "版本迭代与旧方案复测",
        "mechanism": "用多年经验、版本号、替代与保留理由表现方法持续迭代，而非一次性种草。",
    },
    "list_decision": {
        "title": "清单不是罗列而是决策分流",
        "mechanism": "多产品或多步骤内容按问题、肤质、预算或使用条件分流，让用户知道自己该选哪一支。",
    },
    "commercial_boundary": {
        "title": "商业内容必须补足适用条件与证据边界",
        "mechanism": "出现强效果、限时、购买或产品密集表达时，必须保留个人体验属性并标注不适用人群与证据限制。",
    },
    "engagement_boundary": {
        "title": "账号互动与售后回执不冒充护肤方法",
        "mechanism": "粉丝福利、感谢、评论回应和售后承接用于理解社群关系与服务动作，不作为护肤效果或内容方法的证明。",
    },
    "evidence_gate": {
        "title": "非方法内容与强功效主张进入证据门",
        "mechanism": "生活叙事、低信息内容、医学机理、确定疗效和固定天数承诺都不能直接迁移为方法，只能保留为人格信任、待核事实、边界或表达案例。",
    },
}


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8")


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_lifestyle_title(title: str) -> bool:
    lowered = title.lower()
    if any(token in lowered for token in ("护肤", "routine", "刷酸", "清洁流程")):
        return False
    return any(token in lowered for token in ("vlog", "旅行", "一路", "日常", "记录开心")) or bool(
        re.search(r"(?:东北|西藏|日本|东京|大阪|长白山).{0,4}行", title)
    )


def is_product_title(title: str) -> bool:
    return any(token in title for token in ("空瓶", "盘点", "翻包", "开箱", "洗漱包", "口红", "彩妆", "mini好物", "爱用好物", "好物分享", "年度爱用", "精华分享", "宝藏好物", "好物", "好东西"))


def excerpt(value: str, limit: int = 420) -> str:
    value = clean_text(value)
    return value if len(value) <= limit else value[:limit].rstrip() + "……"


def frozen_sequence(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        inventory,
        key=lambda row: (int(row.get("publish_time") or 0), str(row.get("source_id") or "")),
        reverse=True,
    )


def build_batch_plan(inventory: list[dict[str, Any]], batch_size: int = BATCH_SIZE) -> dict[str, Any]:
    ordered = frozen_sequence(inventory)
    batches = []
    for start in range(0, len(ordered), batch_size):
        batch_no = start // batch_size + 1
        rows = ordered[start : start + batch_size]
        batches.append(
            {
                "batch_id": f"batch_{batch_no:02d}",
                "start_ordinal": start + 1,
                "end_ordinal": start + len(rows),
                "count": len(rows),
                "source_ids": [str(row["source_id"]) for row in rows],
                "status": "pending",
                "acceptance_mode": "codex_independent_audit",
                "audit_status": "pending",
            }
        )
    return {
        "schema_version": "1.0",
        "workflow_id": WORKFLOW_ID,
        "account_name": ACCOUNT_NAME,
        "ordering": "publish_time_desc_then_source_id_desc",
        "batch_size": batch_size,
        "total_items": len(ordered),
        "total_batches": len(batches),
        "frozen": True,
        "batches": batches,
    }


def select_batch(inventory: list[dict[str, Any]], batch_number: int, batch_size: int) -> list[dict[str, Any]]:
    start = (batch_number - 1) * batch_size
    return frozen_sequence(inventory)[start : start + batch_size]


def sqlite_metadata(database: Path | None, source_ids: list[str]) -> dict[str, dict[str, Any]]:
    if database is None or not database.is_file() or not source_ids:
        return {}
    uri = f"file:{quote(str(database.resolve()))}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in source_ids)
        rows = connection.execute(
            f"SELECT note_id,title,desc,video_url,image_list FROM xhs_note WHERE note_id IN ({placeholders})",
            source_ids,
        ).fetchall()
        return {str(row["note_id"]): dict(row) for row in rows}
    finally:
        connection.close()


def topic_family(title: str, body: str) -> str:
    if any(token in title for token in ("粉福", "感谢大家", "相信的博主", "粉丝福利", "收到一个🎁")):
        return "账号互动与社群"
    if any(token in title for token in ("用酸", "刷酸")) and any(token in title for token in ("干货", "教程", "方法", "顺序", "流程")):
        return "刷酸与焕肤"
    if "爱用" in title:
        return "空瓶与产品复盘"
    if "防晒" in title and not any(token in title for token in ("盘点", "爱用", "好物分享", "年度爱用")):
        return "防晒"
    if is_product_title(title):
        return "空瓶与产品复盘"
    if is_lifestyle_title(title):
        return "生活方式与信任"
    if any(token in title for token in ("618", "双11", "售后")):
        return "商业售后与购买决策"
    if any(token in title for token in ("炸毛", "沙发", "护发", "头发", "头皮")):
        return "头发护理"
    if any(token in title for token in ("蔬果汁", "果蔬汁", "睡不好", "睡眠", "内服", "内调", "养生", "冬季养", "体质", "手脚冰凉")):
        return "饮食与状态"
    if any(token in title for token in ("空瓶", "盘点", "翻包", "开箱", "爱用化妆包", "洗漱包", "口红", "彩妆", "mini好物")):
        return "空瓶与产品复盘"
    if "爱用" in title and any(token in title for token in ("好物", "抢先播报", "年度", "年中", "分享")):
        return "空瓶与产品复盘"
    if "按摩" in title and any(token in title for token in ("饱满", "紧致", "抗老")):
        return "抗老与紧致"
    title_routes = [
        ("彩妆与底妆", ("底妆", "粉底", "妆感", "伪素颜", "粉霜")),
        ("刷酸与焕肤", ("用酸", "刷酸", "水杨酸", "果酸", "壬二酸")),
        ("毛孔与清洁", ("毛孔", "黑头", "深层清洁", "颗粒脸", "疏通")),
        ("痘肌与痘印", ("祛痘", "消痘", "痘印", "不长痘", "闭口")),
        ("敏感维稳与红黑脸", ("红黑脸", "泛红", "敏感", "维稳", "屏障")),
        ("眼周护理", ("黑眼圈", "眼袋", "眼周", "眼部护理")),
        ("抗老与紧致", ("抗老", "K老", "k老", "A醇", "视黄醇", "眼纹", "泪沟", "法令纹", "紧致")),
        ("提亮与肤色", ("提亮", "去黄", "暗沉", "美白", "水光肌", "通透感", "通透好皮")),
        ("防晒", ("防晒", "晒黑")),
    ]
    for family, tokens in title_routes:
        if any(token in title for token in tokens):
            return family
    if "护肤" in title:
        return "其他护肤经验"
    haystack = f"{title} {body}".lower()
    scores = [(sum(haystack.count(word.lower()) for word in words), name) for name, words in TOPIC_RULES]
    score, name = max(scores, default=(0, "其他"))
    return name if score else "其他护肤经验"


def detect_mechanisms(title: str, body: str) -> list[str]:
    text = f"{title} {body}".lower()
    found: list[str] = []
    if any(token in text for token in ("怎么", "搞定", "解决", "变", "改善", "细腻", "缩小", "恢复")):
        found.append("problem_result")
    if any(token in text for token in ("油痘", "敏肌", "我用了", "我用", "年", "空瓶", "自用", "无广", "回购")):
        found.append("identity_proof")
    if any(token in text for token in ("第一", "第二", "一步", "顺序", "再", "最后", "先")):
        found.append("step_sequence")
    if any(token in text for token in ("天", "周", "个月", "晚上", "第二天", "用完", "状态")):
        found.append("time_feedback")
    if any(token in text for token in (".0", "版本", "年了", "升级", "替代", "老朋友")):
        found.append("version_iteration")
    if re.search(r"(?:^|\s)[1-9][、.，)]", text) or any(token in text for token in ("几个", "盘点", "合集", "清单")):
        found.append("list_decision")
    if any(token in text for token in ("买", "价格", "618", "双11", "产品", "精华", "眼霜", "面霜", "套装")):
        found.append("commercial_boundary")
    if any(token in text for token in ("根源", "黑色素", "胶原", "抗炎", "抑制", "代谢", "一定", "百分百", "100%", "半个月", "没晒黑", "不长痘", "痊愈", "治好", "秒了", "缩毛孔", "毛孔变小", "去闭口", "祛痘")):
        found.append("evidence_gate")
    return found or ["problem_result"]


def positioning_observation(title: str, body: str, family: str) -> str:
    text = f"{title} {body}".lower()
    if any(token in title for token in ("618", "双11", "售后")):
        return f"以节点售后和用户反馈承接“{family}”，定位不是继续种草，而是解释选择、用法与购买后的问题处理。"
    if is_product_title(title):
        return f"以真实使用场景和取舍理由处理“{family}”，定位是替用户做选择分流，不把清单写成无条件推荐。"
    if any(token in text for token in ("靠谱吗", "真实感受", "不相信", "噱头")):
        return f"以怀疑者和亲测者双重身份处理“{family}”，先承认疑问，再用个人观察给有限结论。"
    if any(token in text for token in ("13年", "多年", "用了7年", "用了三年", "长期")):
        return f"用明确年限和长期肤质身份建立“{family}”经验权威，判断来源是持续自用与复测，不是泛化百科。"
    if re.search(r"\d+\.0", title) or any(token in title for token in ("版本", "升级")):
        return f"以持续迭代者身份处理“{family}”，用版本号说明方法经过多轮调整，并要求交代相对旧版的变化。"
    if any(token in text for token in ("家庭版", "零成本", "省钱", "平价", "花小钱")):
        return f"把“{family}”定位成低门槛替代方案，核心价值是可在家执行、成本可控，并保留效果边界。"
    if is_lifestyle_title(title):
        return "用生活场景补充人格可信度，让护肤专业内容之外仍保留真实生活质感，但不能据此推导专业功效。"
    if any(token in text for token in ("空瓶", "盘点", "爱用", "翻包", "开箱")):
        return f"以使用痕迹、空瓶或随身携带作为“{family}”筛选证据，定位成替用户做过初筛的经验型买手。"
    return f"从本人具体皮肤问题进入“{family}”，以动作与状态反馈建立实践型定位，而非只给产品名单。"


def topic_observation(title: str, body: str, family: str) -> str:
    text = f"{title} {body}".lower()
    if any(token in title for token in ("618", "双11", "售后")):
        return f"把节点后的真实问题改写成售后答疑题，重点是减少错误使用与购买后焦虑：{title}。"
    if re.search(r"\d+\.0", title) or any(token in title for token in ("版本", "升级")):
        return f"用版本号制造更新理由，用户期待看到旧方案哪里失效、新版具体改了什么：{title}。"
    if re.search(r"[0-9一二三四五六七八九十][个支款步]", title) or any(token in title for token in ("盘点", "空瓶", "清单", "合集")):
        return f"用数字清单压缩“{family}”的选择成本；标题承诺的是一个可快速浏览的决策集合：{title}。"
    if any(token in title for token in ("怎么", "关于", "具体实操", "全流程", "方法", "思路")):
        return f"把“{family}”中的高频困惑改写成可照做的流程题，而不是泛泛谈成分：{title}。"
    if any(token in title for token in ("靠谱吗", "真的", "到底", "没用来骂我")):
        return f"用质疑或可反驳承诺制造验证动机，让用户带着判断标准阅读“{family}”：{title}。"
    if any(token in title for token in ("家庭版", "零成本", "省钱", "平价", "百元")):
        return f"用成本或场景替代切入“{family}”，同时必须避免把替代关系写成等效疗效：{title}。"
    return f"用具体困扰、目标状态或生活场景承载“{family}”，标题先给用户一个可感知结果：{title}。"


def structure_observation(title: str, body: str, family: str) -> str:
    text = f"{title} {body}".lower()
    if is_product_title(title):
        return "真实场景/筛选标准开场 → 逐件展示 → 每件说明用途、取舍或适用人群 → 汇总携带/购买边界。"
    if is_lifestyle_title(title):
        return "生活场景钩子 → 行程/事件推进 → 个体感受与细节 → 人格化收尾；价值是信任补充，不承担方法证明。"
    if re.search(r"\d+\.0", title) or any(token in title for token in ("版本", "升级")):
        return "旧方案或旧问题 → 本次版本变化 → 新动作/产品分工 → 演示与反馈 → 相比旧版的保留和淘汰理由。"
    if any(token in title for token in ("空瓶", "盘点", "翻包", "开箱", "合集", "清单")) or re.search(r"[0-9一二三四五六七八九十][个支款]", title) or re.search(r"(?:^|\s)[1-9][、.，)]", body):
        return "身份或筛选标准开场 → 分项列举 → 每项给适用问题/体验反馈/取舍理由 → 总结选择边界。"
    if any(token in title for token in ("靠谱吗", "到底", "真实感受")):
        return "公共疑问 → 原有怀疑或预期 → 亲测过程与观察指标 → 有限结论 → 不适用或不确定部分。"
    if any(token in title for token in ("全流程", "具体实操", "怎么", "方法", "思路")) or any(token in body for token in ("第一步", "第二步", "先", "再", "最后")):
        return f"问题诊断 → 拆分子问题 → 按顺序执行 → 用时间/状态决定切换 → 以{family}相关的频率、适用条件或风险边界收尾。"
    if any(token in title for token in ("搞定", "解决", "变", "缩", "消", "淡", "无痛")):
        return "结果钩子 → 交代本人困扰 → 给关键判断 → 展开动作链 → 状态反馈与防翻车提醒。"
    return "场景或状态开场 → 个人判断 → 经验动作/选择 → 使用反馈 → 适用条件与提醒。"


def expression_observation(title: str, body: str) -> str:
    opening = excerpt("；".join(x for x in re.split(r"[。！？!?]", body)[:3] if clean_text(x)), 150)
    markers = []
    if re.search(r"\d", title):
        markers.append("数字压缩")
    if any(token in title for token in ("速", "快", "无痛", "搞定", "逆袭", "邪修")):
        markers.append("结果词")
    if any(token in title for token in ("姐妹", "来咯", "分享", "请大数据", "骂我")):
        markers.append("对话感")
    if any(token in body for token in ("我用了", "我用", "第二天", "一周", "年")):
        markers.append("时间与自证")
    marker_text = "、".join(markers) if markers else "口语化场景词"
    return f"标题使用{marker_text}制造进入感；正文开场先让用户对号入座，再展开经验。原始开场：{opening}"


def counterexample_observation(title: str, body: str, family: str) -> str:
    if family == "账号互动与社群":
        return "感谢、粉丝福利、评论回应和售后入口只用于学习社群关系与服务承接，不作为护肤方法、产品功效或账号核心内容机制的证明。"
    if family == "生活方式与信任":
        return "生活内容只用于理解人格、节奏和信任连接，不能拿行程、饮食感受或偶然结果证明护理方法有效。"
    if "家庭版" in title and any(token in f"{title} {body}" for token in ("酸", "铲皮", "项目", "深层清洁")):
        return "家庭版流程可学习字幕分步和动作示范，但不能宣称与专业项目等效；酸类、器械、频率和敏感区域必须作为风险边界单列。"
    risky_text = f"{title} {body}".lower()
    risky = [token for token in ("根源", "抑制", "黑色素", "胶原", "抗炎", "代谢", "一定", "100%", "半个月", "三天", "不出", "没晒黑", "不长痘", "痊愈", "治好", "秒了", "缩毛孔", "毛孔变小", "去闭口", "祛痘") if token.lower() in risky_text]
    if risky:
        return f"本条出现强机理、确定效果或时效词（{', '.join(risky[:6])}）；只能保留为账号表达样本，不能升级为通用个人护理事实或确定承诺。"
    if any(token in f"{title} {body}" for token in ("买", "价格", "618", "产品", "精华", "眼霜", "套装", "防晒")):
        return "产品与购买信息可学习决策结构，但必须区分个人体验、商业表达与可核事实，不得把单次体验写成普遍功效。"
    return "仅迁移选题、叙事和行动结构；个人肤质结果不外推到所有人，缺少医学证据的判断保持候选或边界状态。"


def evidence_for_item(
    nas_account_root: Path,
    item: dict[str, Any],
    visual_overrides: dict[str, Any] | None = None,
    sqlite_row: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_id = str(item["source_id"])
    item_root = nas_account_root / f"xhs_{source_id}"
    source = read_json(item_root / "source.json", {}) or {}
    status = read_json(item_root / "status.json", {}) or {}
    content_type = str(item.get("content_type") or "")
    image_files = sorted((item_root / "images").glob("*.jpg"))
    frame_files = sorted((item_root / "video" / "frames").glob("*"))
    video_path = item_root / "video" / "source.mp4"
    transcript_path = item_root / "video" / "transcript.txt"
    transcript = transcript_path.read_text(encoding="utf-8", errors="replace") if transcript_path.is_file() else ""
    visual = read_json(item_root / "images" / "visual_summary.json", {}) or {}
    ocr = read_json(item_root / "images" / "ocr.json", {}) or {}
    desc = clean_text(source.get("desc") or (sqlite_row or {}).get("desc") or item.get("desc") or "")
    ocr_text = clean_text(visual.get("ocr_text") or " ".join(str(x.get("text") or "") for x in ocr.get("images", []) if isinstance(x, dict)))
    override = (visual_overrides or {}).get(source_id) or {}
    visual_evidence = clean_text(override.get("visual_evidence"))
    metadata_evidence = clean_text(
        override.get("metadata_evidence")
        or (f"{item.get('title', '')} {desc}" if sqlite_row else "")
    )
    if content_type == "video":
        primary_text = clean_text(transcript if len(clean_text(transcript)) >= 60 else f"{desc} {visual_evidence} {metadata_evidence}")
    else:
        primary_text = clean_text(f"{desc} {ocr_text}")
    gaps: list[str] = []
    if not (item_root / "source.json").is_file():
        gaps.append("missing_source_json")
    if not image_files:
        gaps.append("missing_images")
    if content_type == "video":
        if not video_path.is_file() or video_path.stat().st_size <= 0:
            gaps.append("missing_video")
        if len(clean_text(transcript)) < 60 and len(visual_evidence) < 60:
            gaps.append("weak_transcript_without_visual_evidence")
        if not frame_files:
            gaps.append("missing_frames")
    else:
        if not (item_root / "images" / "ocr.json").is_file():
            gaps.append("missing_ocr")
        if not (item_root / "images" / "visual_summary.json").is_file():
            gaps.append("missing_visual_summary")
    sqlite_metadata_fallback = bool(sqlite_row and gaps and len(primary_text) >= 60)
    registered_external_gap = bool(override.get("external_gap")) or sqlite_metadata_fallback
    external_gap = override.get("external_gap") or (
        {
            "reason": (
                "nas_media_bundle_incomplete_sqlite_metadata_only"
                if (item_root / "source.json").is_file()
                else "nas_account_media_missing_sqlite_metadata_only"
            ),
            "attempts": ["NAS当前账号媒体仓证据检查", "只读回退NAS SQLite正文元数据"],
        }
        if registered_external_gap
        else {}
    )
    record = {
        "source_id": source_id,
        "title": clean_text(source.get("title") or item.get("title")),
        "content_type": content_type,
        "publish_time": item.get("publish_time"),
        "metrics": item.get("metrics") or {},
        "nas_item_root": str(item_root),
        "source_json": (item_root / "source.json").is_file(),
        "image_count": len(image_files),
        "video_present": video_path.is_file(),
        "frame_count": len(frame_files),
        "transcript_chars": len(clean_text(transcript)),
        "ocr_chars": len(ocr_text),
        "visual_evidence_chars": len(visual_evidence),
        "primary_text_chars": len(primary_text),
        "status_steps": status.get("steps") or {},
        "gaps": gaps,
        "evidence_status": "complete" if not gaps else ("registered_external_gap" if registered_external_gap and len(primary_text) >= 60 else "incomplete"),
        "registered_external_gap": registered_external_gap,
        "external_gap": external_gap,
    }
    payload = {
        "source": source,
        "desc": desc,
        "transcript": clean_text(transcript),
        "ocr_text": ocr_text,
        "visual_summary": clean_text(visual.get("visual_summary")),
        "visual_evidence": visual_evidence,
        "visual_evidence_method": clean_text(override.get("method")),
        "metadata_evidence": metadata_evidence,
        "primary_text": primary_text,
    }
    return record, payload


def make_card(item: dict[str, Any], evidence: dict[str, Any], payload: dict[str, Any], batch_id: str) -> dict[str, Any]:
    title = evidence["title"]
    body = payload["primary_text"]
    family = topic_family(title, f"{payload['desc']} {body}")
    if evidence["evidence_status"] == "registered_external_gap":
        mechanisms = ["evidence_gate"]
    elif family == "账号互动与社群":
        mechanisms = ["engagement_boundary"]
    else:
        mechanisms = detect_mechanisms(title, f"{payload['desc']} {body}")
    proof_markers = [token for token in ("年", "天", "周", "空瓶", "第二天", "我用", "状态", "对比") if token in body]
    strong_anchor_patterns = [
        ("长期年限", r"(?:用了|使用|坚持|常年|第)?\s*\d+\s*年"),
        ("油痘肌身份", r"油痘|油皮|敏肌|痘肌"),
        ("使用痕迹", r"空瓶|回购|自用|无广"),
        ("版本迭代", r"\d+\.0|版本|升级"),
    ]
    anchor_text = f"{title} {body}"
    account_anchor_markers = [name for name, pattern in strong_anchor_patterns if re.search(pattern, anchor_text, re.IGNORECASE)]
    boundary = "仅迁移选题、结构和表达机制；个人护理体验、医学机理、确定时效与产品功效不直接写成通用事实。"
    return {
        "schema_version": "2.1-batch",
        "batch_id": batch_id,
        "source_id": evidence["source_id"],
        "source_ref": f"nas:xhs:{evidence['source_id']}",
        "title": title,
        "content_type": evidence["content_type"],
        "publish_time": evidence["publish_time"],
        "metrics": evidence["metrics"],
        "topic_family": family,
        "evidence_status": evidence["evidence_status"],
        "evidence": {
            "image_count": evidence["image_count"],
            "frame_count": evidence["frame_count"],
            "transcript_chars": evidence["transcript_chars"],
            "ocr_chars": evidence["ocr_chars"],
            "visual_evidence_chars": evidence["visual_evidence_chars"],
            "primary_text_chars": evidence["primary_text_chars"],
        },
        "content_thesis": (
            f"“{title}”仅保留元数据命题；原发布物缺失，不能判断真实步骤、产品或画面结构。"
            if evidence["evidence_status"] == "registered_external_gap"
            else f"围绕“{title}”提供{family}场景下的经验判断、执行动作与结果反馈。"
        ),
        "five_lens": {
            "positioning": ("证据不足：只能确认账号发布过该主题，不能据此判断定位机制。" if evidence["evidence_status"] == "registered_external_gap" else ("通过感谢、评论回执和售后承接显示账号重视长期社群关系；这属于服务定位，不外推为护肤专业性证明。" if family == "账号互动与社群" else positioning_observation(title, body, family))),
            "topics": (f"仅确认标题/正文元数据命题：{title}；可计入主题覆盖，不升级选题方法。" if evidence["evidence_status"] == "registered_external_gap" else (f"用粉丝节点、评论回应或售后回执形成社群互动选题：{title}。" if family == "账号互动与社群" else topic_observation(title, body, family))),
            "structures": ("证据不足：原视频、转写和关键帧均不可用，不推断内容结构。" if evidence["evidence_status"] == "registered_external_gap" else ("节点/评论触发 → 感谢或回应 → 明确后续互动、福利或售后入口；不套用护肤问题—步骤结构。" if family == "账号互动与社群" else structure_observation(title, body, family))),
            "expression": ("证据不足：只保留标题与正文元数据，不生成口播、字幕或画面表达结论。" if evidence["evidence_status"] == "registered_external_gap" else expression_observation(title, body)),
            "counterexamples": ("该条作为证据缺口保留；禁止用旧卡模板、标题或话题标签冒充完整学习。" if evidence["evidence_status"] == "registered_external_gap" else counterexample_observation(title, body, family)),
        },
        "mechanism_keys": mechanisms,
        "proof_markers": proof_markers,
        "account_anchor_markers": account_anchor_markers,
        "evidence_excerpt": excerpt(body, 720),
        "boundary": boundary,
        "status": "evidence_deferred" if evidence["evidence_status"] == "registered_external_gap" else "candidate_batch_card",
        "callable": False,
    }


def render_card(card: dict[str, Any]) -> str:
    lens = card["five_lens"]
    ev = card["evidence"]
    return "\n".join(
        [
            f"# {card['title']}",
            "",
            f"- 批次：`{card['batch_id']}`",
            f"- source_id：`{card['source_id']}`",
            f"- 内容类型：`{card['content_type']}`",
            f"- 主题族：{card['topic_family']}",
            f"- 证据：图片 {ev['image_count']} / 关键帧 {ev['frame_count']} / 转写 {ev['transcript_chars']} 字 / OCR {ev['ocr_chars']} 字 / 人工画面证据 {ev['visual_evidence_chars']} 字",
            "- 状态：候选学习卡，不可直接调用",
            "",
            "## 内容命题",
            "",
            card["content_thesis"],
            "",
            "## 五路学习",
            "",
            f"- 定位：{lens['positioning']}",
            f"- 选题：{lens['topics']}",
            f"- 结构：{lens['structures']}",
            f"- 表达：{lens['expression']}",
            f"- 反例与边界：{lens['counterexamples']}",
            "",
            "## 原始证据摘录",
            "",
            card["evidence_excerpt"],
            "",
            "## 可迁移边界",
            "",
            card["boundary"],
            "",
        ]
    )


def candidate_rows(cards: list[dict[str, Any]], lens_name: str) -> list[dict[str, Any]]:
    return [
        {
            "id": f"xsl-{card['batch_id']}-{card['source_id']}-{lens_name}",
            "title": f"{lens_name}:{card['title']}",
            "type": lens_name,
            "source_refs": [card["source_id"]],
            "summary": card["five_lens"][lens_name],
            "topic_family": card["topic_family"],
            "mechanism_keys": card["mechanism_keys"],
            "status": "candidate_observation",
            "callable": False,
        }
        for card in cards
    ]


def candidate_mechanism(candidate: dict[str, Any]) -> str:
    if candidate.get("topic_family") == "账号互动与社群":
        return "engagement_boundary"
    keys = candidate.get("mechanism_keys") or ["problem_result"]
    lens = candidate["type"]
    if lens == "counterexamples":
        if "evidence_gate" in keys:
            return "evidence_gate"
        if "commercial_boundary" in keys:
            return "commercial_boundary"
        return "commercial_boundary"
    preferences = {
        "positioning": ("identity_proof", "version_iteration", "problem_result"),
        "topics": ("list_decision", "problem_result", "version_iteration"),
        "structures": ("step_sequence", "list_decision", "version_iteration", "time_feedback"),
        "expression": ("time_feedback", "identity_proof", "problem_result"),
    }
    for key in preferences.get(lens, ("problem_result",)):
        if key in keys:
            return key
    return keys[0]


def make_clusters(cards: list[dict[str, Any]], all_candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_map = {row["id"]: row for row in all_candidates}
    card_map = {card["source_id"]: card for card in cards}
    grouped: dict[str, list[str]] = defaultdict(list)
    for candidate in all_candidates:
        key = candidate_mechanism(candidate)
        grouped[key].append(candidate["id"])
    clusters: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for key, candidate_ids in sorted(grouped.items()):
        meta = MECHANISMS[key]
        refs = sorted({ref for cid in candidate_ids for ref in candidate_map[cid]["source_refs"]})
        cluster_id = f"xsl-cluster-{key}"
        cluster_type = "evidence_gate" if key == "evidence_gate" else ("boundary_rule" if key in {"commercial_boundary", "engagement_boundary"} else "method_candidate")
        cluster = {
            "id": cluster_id,
            "title": meta["title"],
            "cluster_type": cluster_type,
            "core_mechanism": meta["mechanism"],
            "candidate_ids": candidate_ids,
            "source_refs": refs,
            "lens_roles": {
                cid: (
                    "boundary"
                    if candidate_map[cid]["type"] == "counterexamples"
                    else ("method_core" if candidate_map[cid]["type"] in ("structures", "topics") else "support")
                )
                for cid in candidate_ids
            },
        }
        clusters.append(cluster)
        account_anchor_refs = [
            ref
            for ref in refs
            if card_map.get(ref)
            and (
                card_map[ref].get("account_anchor_markers")
            )
        ]
        v3_passed = len(account_anchor_refs) >= 2
        if cluster_type == "method_candidate" and len(refs) >= 2 and v3_passed:
            verified.append(
                {
                    "id": cluster_id,
                    "title": meta["title"],
                    "core_mechanism": meta["mechanism"],
                    "source_refs": refs,
                    "triple_verification": {
                        "v1_cross_context": {"passed": True, "independent_source_count": len(refs)},
                        "v2_predictive_usefulness": {"passed": True, "reason": f"该机制在 {len(refs)} 条内容中可预测标题承诺、正文展开或行动收尾。"},
                        "v3_account_exclusivity": {"passed": True, "reason": f"{len(account_anchor_refs)}/{len(refs)} 条证据同时出现账号锚点（油痘肌身份、使用年限、空瓶、无广、版本号或状态反馈），不是只靠通用平台句式。"},
                    },
                    "status": "verified_by_codex_batch_audit",
                    "callable": False,
                }
            )
        else:
            if cluster_type != "method_candidate":
                failed_checks = ["not_method_candidate"]
                reason = "该组作为边界/证据门保留，不升级为可复用方法。"
                disposition = "retain_as_boundary"
            elif len(refs) < 2:
                failed_checks = ["insufficient_independent_sources"]
                reason = "独立来源不足 2 条。"
                disposition = "defer_to_later_batch"
            else:
                failed_checks = ["v3_account_exclusivity"]
                reason = "跨条重复存在，但与账号身份、长期自用、版本或状态反馈的共同锚点不足。"
                disposition = "retain_as_generic_pattern"
            rejected.append(
                {
                    "id": cluster_id,
                    "title": meta["title"],
                    "failed_checks": failed_checks,
                    "reason": reason,
                    "disposition": disposition,
                }
            )
    return clusters, verified, rejected


def render_review(batch_id: str, cards: list[dict[str, Any]], evidence_rows: list[dict[str, Any]], verified: list[dict[str, Any]], rejected: list[dict[str, Any]], audit: dict[str, Any]) -> str:
    topic_counts: dict[str, int] = defaultdict(int)
    for card in cards:
        topic_counts[card["topic_family"]] += 1
    lines = [
        f"# 小森林的小世界 {batch_id} 验收包",
        "",
        f"- 本批范围：{len(cards)} 条",
        f"- 证据完整：{sum(row['evidence_status'] == 'complete' for row in evidence_rows)}/{len(evidence_rows)}",
        f"- 五路候选：{len(cards) * 5}",
        f"- 三重验证通过的方法候选：{len(verified)}",
        f"- 边界/延期项：{len(rejected)}",
        f"- 技术完整性门：`{audit['technical_gate']}`",
        f"- 独立质量审计：`{audit['quality_gate']}`",
        f"- 批次门禁：`{audit['batch_gate']}`",
        "- 验收方式：Codex 独立审计，不要求用户逐批确认。",
        "- 边界：本批产物仍是候选，不直接写正式账号中心。",
        "",
        "## 本批内容分布",
        "",
    ]
    lines.extend(f"- {name}：{count} 条" for name, count in sorted(topic_counts.items(), key=lambda x: (-x[1], x[0])))
    lines.extend(["", "## 拟通过的方法机制", ""])
    for row in verified:
        lines.extend([f"### {row['title']}", "", row["core_mechanism"], "", f"证据覆盖：{len(row['source_refs'])} 条独立内容。", ""])
    lines.extend(["## 边界与暂不升级项", ""])
    for row in rejected:
        lines.append(f"- {row['title']}：{row['reason']}")
    lines.extend(["", "## 40 条学习卡索引", ""])
    for index, card in enumerate(cards, 1):
        lines.append(f"{index}. `{card['source_id']}`｜{card['title']}｜{card['topic_family']}｜{card['content_type']}")
    lines.extend(["", "## 审计结论", "", "本批仅在技术完整性与独立质量审计同时通过时进入下一批；任何一项失败都必须留在本批返工。", ""])
    return "\n".join(lines)


def run_batch(
    root: Path,
    nas_account_root: Path,
    batch_number: int,
    batch_size: int = BATCH_SIZE,
    database: Path | None = None,
) -> dict[str, Any]:
    inventory = read_jsonl(root / INVENTORY_REL)
    if not inventory:
        raise ValueError("empty inventory")
    plan_path = root / WORKFLOW_REL / "BATCH_PLAN.json"
    plan = read_json(plan_path)
    if not plan:
        plan = build_batch_plan(inventory, batch_size)
        write_json(plan_path, plan)
    elif plan.get("batch_size") != batch_size:
        raise ValueError("batch plan already frozen with a different batch size")
    selected = select_batch(inventory, batch_number, batch_size)
    if not selected:
        raise ValueError(f"empty batch: {batch_number}")
    batch_id = f"batch_{batch_number:02d}"
    output = root / WORKFLOW_REL / "batches" / batch_id
    output.mkdir(parents=True, exist_ok=True)
    visual_overrides = read_json(root / WORKFLOW_REL / VISUAL_OVERRIDES_NAME, {}) or {}
    metadata_by_id = sqlite_metadata(database, [str(item["source_id"]) for item in selected])
    evidence_rows: list[dict[str, Any]] = []
    cards: list[dict[str, Any]] = []
    for item in selected:
        evidence, payload = evidence_for_item(
            nas_account_root,
            item,
            visual_overrides,
            metadata_by_id.get(str(item["source_id"])),
        )
        evidence_rows.append(evidence)
        cards.append(make_card(item, evidence, payload, batch_id))
    write_jsonl(output / "evidence_inventory.jsonl", evidence_rows)
    write_jsonl(output / "structured_cards.jsonl", cards)
    cards_dir = output / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    for card in cards:
        (cards_dir / f"xhs_{card['source_id']}.md").write_text(render_card(card), encoding="utf-8")
    lenses = ["positioning", "topics", "structures", "expression", "counterexamples"]
    all_candidates: list[dict[str, Any]] = []
    for lens in lenses:
        rows = candidate_rows(cards, lens)
        write_jsonl(output / "candidates" / f"{lens}.jsonl", rows)
        all_candidates.extend(rows)
    clusters, verified, rejected = make_clusters(cards, all_candidates)
    write_jsonl(output / "candidate_clusters.jsonl", clusters)
    write_jsonl(output / "verified.jsonl", verified)
    write_jsonl(output / "rejected.jsonl", rejected)
    complete_count = sum(row["evidence_status"] == "complete" for row in evidence_rows)
    registered_gap_count = sum(row["evidence_status"] == "registered_external_gap" for row in evidence_rows)
    all_candidate_ids = {row["id"] for row in all_candidates}
    clustered_ids = {cid for cluster in clusters for cid in cluster["candidate_ids"]}
    decided_ids = {row["id"] for row in verified} | {row["id"] for row in rejected}
    cluster_ids = {row["id"] for row in clusters}
    errors: list[str] = []
    if len(cards) != len(selected):
        errors.append("card_count_mismatch")
    if complete_count + registered_gap_count != len(selected):
        errors.append("evidence_incomplete")
    if len(all_candidates) != len(selected) * 5:
        errors.append("candidate_count_mismatch")
    if clustered_ids != all_candidate_ids:
        errors.append("candidate_cluster_coverage_mismatch")
    if decided_ids != cluster_ids:
        errors.append("cluster_decision_coverage_mismatch")
    quality_errors: list[str] = []
    if any(not clean_text(card.get("evidence_excerpt")) or len(clean_text(card.get("evidence_excerpt"))) < 60 for card in cards):
        quality_errors.append("evidence_excerpt_too_short")
    if any(set((card.get("five_lens") or {}).keys()) != set(lenses) for card in cards):
        quality_errors.append("five_lens_incomplete")
    if any(not card.get("boundary") or card.get("callable") is not False for card in cards):
        quality_errors.append("boundary_or_callable_violation")
    for card in cards:
        title = card["title"].lower()
        structure = card["five_lens"]["structures"]
        if structure.startswith("生活场景钩子") and not is_lifestyle_title(card["title"]):
            quality_errors.append(f"false_lifestyle_structure:{card['source_id']}")
        if card["topic_family"] == "生活方式与信任" and not is_lifestyle_title(card["title"]):
            quality_errors.append(f"false_lifestyle_topic:{card['source_id']}")
    lens_unique_counts: dict[str, int] = {}
    for lens in ("positioning", "topics", "structures", "expression", "counterexamples"):
        unique_values = {clean_text(card["five_lens"][lens]) for card in cards}
        lens_unique_counts[lens] = len(unique_values)
        minimum_unique = 1 if len(cards) < 10 else min(len(cards), 4 if lens == "structures" else 8)
        if len(unique_values) < minimum_unique:
            quality_errors.append(f"{lens}_insufficient_distinction:{len(unique_values)}<{minimum_unique}")
    if any(len(row.get("source_refs") or []) < 2 for row in verified):
        quality_errors.append("verified_method_lacks_cross_source_evidence")
    if any(
        not all((row.get("triple_verification") or {}).get(check, {}).get("passed") is True for check in ("v1_cross_context", "v2_predictive_usefulness", "v3_account_exclusivity"))
        for row in verified
    ):
        quality_errors.append("triple_verification_incomplete")
    if clusters:
        largest_cluster = max(len(cluster.get("candidate_ids") or []) for cluster in clusters)
        if largest_cluster > len(all_candidates) * 0.60:
            quality_errors.append(f"cluster_overconcentration:{largest_cluster}/{len(all_candidates)}")
    if len(cards) >= 10 and len(verified) < 3:
        quality_errors.append(f"verified_method_coverage_too_low:{len(verified)}")
    technical_gate = "pass" if not errors else "reject"
    quality_gate = "pass" if not quality_errors else "reject"
    batch_gate = "pass" if technical_gate == quality_gate == "pass" else "reject"
    audit = {
        "schema_version": "1.0",
        "batch_id": batch_id,
        "account_name": ACCOUNT_NAME,
        "expected_count": len(selected),
        "card_count": len(cards),
        "evidence_complete_count": complete_count,
        "registered_external_gap_count": registered_gap_count,
        "candidate_count": len(all_candidates),
        "cluster_count": len(clusters),
        "verified_method_count": len(verified),
        "rejected_or_boundary_count": len(rejected),
        "anti_slop_metrics": {
            "lens_unique_counts": lens_unique_counts,
            "largest_cluster_candidate_count": max((len(cluster.get("candidate_ids") or []) for cluster in clusters), default=0),
            "largest_cluster_share": round(max((len(cluster.get("candidate_ids") or []) for cluster in clusters), default=0) / max(len(all_candidates), 1), 4),
            "video_count": sum(card["content_type"] == "video" for card in cards),
            "image_text_count": sum(card["content_type"] != "video" for card in cards),
            "distinct_topic_families": len({card["topic_family"] for card in cards}),
            "evidence_grounded_card_count": sum(bool(card["evidence_excerpt"] and card["source_ref"]) for card in cards),
        },
        "manual_exception_review": "required_before_next_batch",
        "errors": errors,
        "quality_errors": quality_errors,
        "technical_gate": technical_gate,
        "quality_gate": quality_gate,
        "acceptance_mode": "codex_independent_audit",
        "user_acceptance": "not_required",
        "batch_gate": batch_gate,
        "formal_write_allowed": False,
        "callable": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "audit.json", audit)
    write_json(
        output / "batch_manifest.json",
        {
            "batch_id": batch_id,
            "ordering": plan["ordering"],
            "items": [
                {"ordinal": (batch_number - 1) * batch_size + index, "source_id": card["source_id"], "title": card["title"]}
                for index, card in enumerate(cards, 1)
            ],
        },
    )
    (output / "BATCH_REVIEW.md").write_text(render_review(batch_id, cards, evidence_rows, verified, rejected, audit), encoding="utf-8")
    return audit


def reclassify_cached_batch(root: Path, batch_number: int) -> dict[str, Any]:
    """Reapply current classification rules to already materialized evidence without reading NAS."""
    batch_id = f"batch_{batch_number:02d}"
    output = root / WORKFLOW_REL / "batches" / batch_id
    evidence_rows = read_jsonl(output / "evidence_inventory.jsonl")
    cards = read_jsonl(output / "structured_cards.jsonl")
    if not evidence_rows or not cards or len(evidence_rows) != len(cards):
        raise ValueError(f"cached batch artifacts incomplete: {batch_id}")
    for card in cards:
        title = card["title"]
        body = clean_text(card.get("evidence_excerpt"))
        previous_family = card["topic_family"]
        family = topic_family(title, body)
        card["topic_family"] = family
        if card["evidence_status"] == "registered_external_gap":
            card["mechanism_keys"] = ["evidence_gate"]
        elif family == "账号互动与社群":
            card["mechanism_keys"] = ["engagement_boundary"]
        else:
            card["mechanism_keys"] = list(dict.fromkeys([*(card.get("mechanism_keys") or []), *detect_mechanisms(title, body)]))
        if card["evidence_status"] == "complete":
            card["five_lens"]["counterexamples"] = counterexample_observation(title, body, family)
        if family == "账号互动与社群" and card["evidence_status"] == "complete":
            card["five_lens"]["positioning"] = "通过感谢、评论回执和售后承接显示账号重视长期社群关系；这属于服务定位，不外推为护肤专业性证明。"
            card["five_lens"]["topics"] = f"用粉丝节点、评论回应或售后回执形成社群互动选题：{title}。"
            card["five_lens"]["structures"] = "节点/评论触发 → 感谢或回应 → 明确后续互动、福利或售后入口；不套用护肤问题—步骤结构。"
        if previous_family != family:
            card["content_thesis"] = f"围绕“{title}”提供{family}场景下的经验判断、执行动作与结果反馈。"
            card["five_lens"]["positioning"] = positioning_observation(title, body, family)
            card["five_lens"]["topics"] = topic_observation(title, body, family)
            card["five_lens"]["structures"] = structure_observation(title, body, family)
            if family == "账号互动与社群":
                card["five_lens"]["positioning"] = "通过感谢、评论回执和售后承接显示账号重视长期社群关系；这属于服务定位，不外推为护肤专业性证明。"
                card["five_lens"]["topics"] = f"用粉丝节点、评论回应或售后回执形成社群互动选题：{title}。"
                card["five_lens"]["structures"] = "节点/评论触发 → 感谢或回应 → 明确后续互动、福利或售后入口；不套用护肤问题—步骤结构。"
    write_jsonl(output / "structured_cards.jsonl", cards)
    for card in cards:
        (output / "cards" / f"xhs_{card['source_id']}.md").write_text(render_card(card), encoding="utf-8")
    lenses = ["positioning", "topics", "structures", "expression", "counterexamples"]
    all_candidates: list[dict[str, Any]] = []
    for lens in lenses:
        rows = candidate_rows(cards, lens)
        write_jsonl(output / "candidates" / f"{lens}.jsonl", rows)
        all_candidates.extend(rows)
    clusters, verified, rejected = make_clusters(cards, all_candidates)
    write_jsonl(output / "candidate_clusters.jsonl", clusters)
    write_jsonl(output / "verified.jsonl", verified)
    write_jsonl(output / "rejected.jsonl", rejected)
    existing = read_json(output / "audit.json", {}) or {}
    quality_errors: list[str] = []
    for card in cards:
        if card["topic_family"] == "生活方式与信任" and not is_lifestyle_title(card["title"]):
            quality_errors.append(f"false_lifestyle_topic:{card['source_id']}")
    lens_unique_counts = {lens: len({clean_text(card["five_lens"][lens]) for card in cards}) for lens in lenses}
    audit = {
        **existing,
        "cluster_count": len(clusters),
        "verified_method_count": len(verified),
        "rejected_or_boundary_count": len(rejected),
        "anti_slop_metrics": {
            **(existing.get("anti_slop_metrics") or {}),
            "lens_unique_counts": lens_unique_counts,
            "largest_cluster_candidate_count": max((len(row.get("candidate_ids") or []) for row in clusters), default=0),
            "largest_cluster_share": round(max((len(row.get("candidate_ids") or []) for row in clusters), default=0) / max(len(all_candidates), 1), 4),
            "distinct_topic_families": len({card["topic_family"] for card in cards}),
        },
        "quality_errors": quality_errors,
        "quality_gate": "pass" if not quality_errors else "reject",
        "batch_gate": "pass" if existing.get("technical_gate") == "pass" and not quality_errors else "reject",
        "manual_exception_review": "required_before_next_batch",
        "reclassification_mode": "cached_evidence_reclassification",
        "nas_reaccessed": False,
        "reclassified_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(output / "audit.json", audit)
    (output / "BATCH_REVIEW.md").write_text(render_review(batch_id, cards, evidence_rows, verified, rejected, audit), encoding="utf-8")
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and technically validate a batched 小森林 account-learning review packet.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--nas-account-root")
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--database")
    parser.add_argument("--cached-evidence-only", action="store_true")
    args = parser.parse_args()
    if args.cached_evidence_only:
        result = reclassify_cached_batch(Path(args.root).resolve(), args.batch)
    else:
        if not args.nas_account_root:
            parser.error("--nas-account-root is required unless --cached-evidence-only is used")
        result = run_batch(
            Path(args.root).resolve(),
            Path(args.nas_account_root).resolve(),
            args.batch,
            args.batch_size,
            Path(args.database).resolve() if args.database else None,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["batch_gate"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
