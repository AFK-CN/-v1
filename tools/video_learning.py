from __future__ import annotations

import argparse
import html as html_lib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.account_learning_card import CONTRACT_ID, validate_unified_text

VIDEO_LEARNING_REPORTS_DIR = Path("00_System/runtime/reports/video_learning")
VIDEO_LEARNING_CACHE_DIR = Path("00_System/runtime/cache/video_learning")
VIDEO_LEARNING_STATE_DIR = Path("00_System/runtime/state/video_learning")
VIDEO_LEARNING_QUEUE_DIR = Path("90_Temp/scratch/video_learning/queues")
CANDIDATE_LEARNING_DIR = Path("10_Knowledge/candidates/learning_cards")
CANDIDATE_ACCOUNT_ASSETS_DIR = Path("10_Knowledge/candidates/account_assets")


DIRECTION_KEYWORDS = {
    "赚钱": ["赚钱", "财富", "收入", "商业", "商机", "变现", "副业"],
    "创业": ["创业", "一人公司", "产品化", "机会", "项目"],
    "自媒体": ["自媒体", "内容创作", "账号", "流量", "个人ip", "个人IP"],
    "短视频": ["短视频", "视频", "拍摄", "脚本", "口播", "分镜"],
    "剧情短剧": ["剧情", "短剧", "剧本", "编剧", "如果人生有剧本", "集", "第一集", "第二集", "第三集", "第四集"],
    "喜剧反转": ["反转", "社死", "倒霉蛋", "愚人节", "一定要看到最后", "好运", "怎么啦", "扯不扯"],
    "校园大学生": ["大学生", "校园", "宿舍", "同学", "高考", "考生", "上课"],
    "职场关系": ["职场", "员工", "老板", "公司", "事业", "预判型员工", "上班", "下班", "准时下班", "着急下班"],
    "情感关系": ["恋爱", "恋爱脑", "桃花运", "情感"],
    "人际社交观察": ["社恐", "社交", "插队", "同学", "做客", "室友", "亲戚", "查寝", "不熟", "人情世故", "高情商"],
    "代际观察": ["00后", "学生版", "孩子", "年轻人", "新型", "一种很新的"],
    "爱情关系喜剧": ["爱情", "前任", "相亲", "分手", "情侣", "对象", "男女之间", "女人心", "恋爱", "桃花运", "舔狗", "舔🐶", "代吵"],
    "性格标签喜剧": ["社恐", "敏感", "聪明", "小心眼", "自作多情", "心态", "反骨", "霸道", "直男", "钢铁直男", "拿铁直男"],
    "生活荒诞反转": ["扶梯", "一镜到底", "预判", "体面", "生日", "许愿", "编剧", "饭店", "一分", "没花", "说忘就忘", "技高一筹", "证明不了", "普通话考试", "双胞胎", "跑了", "彩蛋"],
    "身份错位短剧": ["老师", "销售", "孩子", "老板", "员工", "教练", "学生", "霸道总裁", "霸总", "面试", "简历", "考试", "饭店", "驾校", "查寝", "上课"],
    "语言表达喜剧": ["中文", "普通话", "说忘就忘", "教学", "十级", "怎么说", "考试", "证明不了"],
    "心理博弈": ["心理战", "举手", "技高一筹", "预判", "反向", "面试", "辩论", "心态"],
    "情绪自洽": ["哄好自己", "走心", "故事", "小心眼", "敏感", "自作多情", "听得进", "痛的领悟"],
    "咖啡生活梗": ["美式", "咖啡", "咖啡文学", "清醒人生"],
    "品牌植入": ["科大讯飞", "宁德时代", "王者荣耀", "亚朵", "去哪儿", "荣耀", "SKII", "飞科", "周黑鸭", "宝骏", "伊利"],
    "作品代表作索引": ["你可能不认识我", "这些都没看过", "代表作", "合集", "名场面"],
    "求助边界拉扯": ["帮我", "不帮我", "求助", "帮一下", "帮忙", "这怎么还"],
    "口号仪式反讽": ["不忘初心", "砥砺前行", "口号", "仪式感", "强的可怕"],
    "部门组织拟人": ["部门", "业务中心", "家庭业务", "失眠部门", "中心"],
    "节日家庭场景": ["过年", "回家", "家庭", "媳妇", "怕媳妇", "亲戚", "春节"],
    "暗示沟通": ["暗示", "明显吗", "你懂", "你猜", "话里有话"],
    "礼貌社交规则": ["礼貌", "最有礼貌", "客气", "规矩", "礼节"],
    "冲突吵架技巧": ["吵架", "对象吵架", "拌嘴", "吵赢", "吵"],
    "金钱边界喜剧": ["AA", "aa", "买单", "请客", "付款", "付钱"],
    "消费体验反差": ["商务座", "第一次坐", "理发", "看小品", "点名", "坐商务"],
    "叛逆反差": ["叛逆", "反骨", "不听话", "听话", "不后悔"],
    "身体状态喜剧": ["睡觉", "困了", "饿了", "脚臭", "着急", "太累", "累了"],
    "朋友熟人关系": ["朋友", "纯友谊", "男闺蜜", "熟人", "对方"],
    "自信夸奖喜剧": ["增强自信", "自信", "夸我", "夸我一天", "总夸我"],
    "心眼疑心拟人": ["心眼子", "疑心病", "妄想症", "综合症"],
    "沟通误解喜剧": ["哪里不对", "这啥理由", "打招呼", "无效沟通", "中译中", "翻译", "拐弯抹角", "什么玩意", "最后怎么了", "这事"],
    "压力崩溃喜剧": ["太难了", "闹心", "着急", "被迫", "太难"],
    "吃饭点菜场景": ["点菜", "吃饭", "这饭", "午餐", "饭吃"],
    "商战利益博弈": ["商战", "免费午餐", "别针换别墅", "利益", "博弈"],
    "家庭身份关系": ["见家长", "一家之主", "家人们", "家长", "家人"],
    "个人成长": ["成长", "逆袭", "行动", "自律", "习惯", "复盘", "学习"],
    "人生策略": ["作弊", "捷径", "方向", "目标", "权利", "强者", "独立思考", "趋势", "改变自己", "跟对", "选择", "复利", "喜欢", "擅长", "朋友还多", "人生算法"],
    "借势杠杆": ["大哥", "梯子", "借势", "杠杆", "buff", "前辈", "洞见", "跑赢"],
    "技能资产": ["技能", "阅读", "写作", "销售", "构建", "演讲", "临摹", "换位思考", "自学", "运营", "数学知识"],
    "表达文案": ["文案", "表达", "作品", "生活状态", "土才是你的优势", "写点什么"],
    "商业机会": ["聚宝盆", "生意", "需求", "产品", "连接", "好用户", "好产品", "交易", "小钱", "挣钱", "挣"],
    "财富策略": ["投资", "财富", "钱", "能力范围", "交给时间", "奢侈"],
    "心智修炼": ["有念", "无念", "念", "思考的时间", "关在笼子", "独立思考", "惯性"],
    "风险避坑": ["炒G", "小心", "风险", "不推荐", "不要浪费", "删"],
    "阅读输入": ["推荐几本书", "推荐三本书", "读好书", "阅读", "书"],
    "机会准备": ["上帝来敲门", "应该在家", "机会", "趋势", "准备"],
    "信息源判断": ["知识的主要来源", "来源", "合适的人", "合适的书", "意见"],
    "高手思考模型": ["高手一样思考", "第一性原理", "剃刀法则", "思考“思考的过程”", "思考的过程", "人生算法", "+-×÷", "深度思考", "重新思考", "原理、法则"],
    "自我进化": ["每天都在进化", "每一天都在进化", "看见.改变.渐变", "姜胡说2.0", "姜胡说 2.0", "见证", "转型之路"],
    "关键知识": ["关键的知识", "知识不用太多", "真正理解", "人生就改变了"],
    "宏观趋势": ["城镇化", "工业化", "消费+互联网", "新能源车", "碳中和", "高精尖"],
    "自知谦逊": ["知道自己不厉害", "不厉害", "无能的人", "脸这个东西"],
    "做事框架": ["做小事", "做好", "做完整", "保持专注", "全情投入", "做事的框架", "认真做好一件事", "对抗熵增", "重复重复再重复", "不可能的事", "解读框架", "重新理解计划"],
    "结构化理解": ["知识、结构", "函数调用", "人生编程", "重构对这个世界的理解", "重新梳理", "重新理解", "估算", "价值"],
    "市场周期理解": ["牛市", "市场", "当下市场", "会议解读", "芬钛计划"],
    "认知升级": ["认知", "思维", "系统", "方法", "心法", "知识体系"],
    "AI": ["AI", "人工智能", "codex", "ChatGPT", "智能体"],
    "减脂餐": ["减脂", "低卡", "低脂", "健身餐", "干净饮食"],
    "一人食": ["一人食", "独居", "一个人也要好好吃饭"],
    "备餐": ["备餐", "备菜", "一周", "菜单", "食谱", "午餐不重样"],
}

KNOWN_DIRECTIONS = set(DIRECTION_KEYWORDS)

ACCOUNT_SCOPED_DIRECTIONS = {
    "李宗恒": {
        "剧情短剧",
        "喜剧反转",
        "校园大学生",
        "职场关系",
        "情感关系",
        "人际社交观察",
        "代际观察",
        "爱情关系喜剧",
        "性格标签喜剧",
        "生活荒诞反转",
        "身份错位短剧",
        "语言表达喜剧",
        "心理博弈",
        "情绪自洽",
        "咖啡生活梗",
        "品牌植入",
        "作品代表作索引",
        "求助边界拉扯",
        "口号仪式反讽",
        "部门组织拟人",
        "节日家庭场景",
        "暗示沟通",
        "礼貌社交规则",
        "冲突吵架技巧",
        "金钱边界喜剧",
        "消费体验反差",
        "叛逆反差",
        "身体状态喜剧",
        "朋友熟人关系",
        "自信夸奖喜剧",
        "心眼疑心拟人",
        "沟通误解喜剧",
        "压力崩溃喜剧",
        "吃饭点菜场景",
        "商战利益博弈",
        "家庭身份关系",
    },
    "姜胡说": {
        "人生策略",
        "借势杠杆",
        "技能资产",
        "表达文案",
        "商业机会",
        "财富策略",
        "心智修炼",
        "风险避坑",
        "阅读输入",
        "机会准备",
        "信息源判断",
        "高手思考模型",
        "自我进化",
        "关键知识",
        "宏观趋势",
        "自知谦逊",
        "做事框架",
        "结构化理解",
        "市场周期理解",
    },
}

DIRECTION_ACCOUNT_SCOPE = {
    direction: account_name
    for account_name, directions in ACCOUNT_SCOPED_DIRECTIONS.items()
    for direction in directions
}


def find_executable(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for directory in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"):
        candidate = Path(directory) / name
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return ""


@dataclass(frozen=True)
class NormalizedRecord:
    platform: str
    source_id: str
    source_file: str
    title: str
    body: str
    author_name: str
    published_at: str
    metrics: dict[str, int]
    tags: list[str]
    url: str
    video_download_url: str
    text_fingerprint: str
    account_name: str = ""
    image_urls: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RankedRecord:
    record: NormalizedRecord
    direction: str
    score: float
    rank: int


def parse_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace(",", "")
    if not text:
        return 0
    match = re.search(r"-?\d+", text)
    return int(match.group(0)) if match else 0


def compact_text(text: str) -> str:
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)
    return text.lower()


def fingerprint(title: str, body: str, author_name: str) -> str:
    raw = compact_text(f"{title}{body}{author_name}")
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def split_tags(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = decode_maybe_json_string(value)
    return [item.strip().strip('"').strip("'") for item in text.split(",") if item.strip().strip('"').strip("'")]


def split_image_urls(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        candidates = [str(item).strip() for item in value]
    else:
        text = decode_maybe_json_string(value)
        candidates = [item.strip().strip('"').strip("'") for item in text.split(",")]
    return [url for url in candidates if url]


def decode_maybe_json_string(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        decoded = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return text
    return str(decoded) if not isinstance(decoded, list) else ",".join(str(item) for item in decoded)


def first_media_url(value: Any) -> str:
    urls = split_image_urls(value)
    return urls[0] if urls else ""


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def hashtag_tags(text: str) -> list[str]:
    tags = []
    for tag in re.findall(r"#([^#\s]+)", text):
        clean = tag.strip("[]# ，,。")
        if clean:
            tags.append(clean)
    return tags


def account_name_from_path(path: Path) -> str:
    parts = list(path.parts)
    if "json" in parts:
        index = parts.index("json")
        if index + 1 < len(parts) - 1:
            return parts[index + 1]
    return ""


def normalize_record(platform: str, row: dict[str, Any], source_file: Path) -> NormalizedRecord:
    if platform == "douyin":
        title = str(row.get("title") or "")
        body = str(row.get("desc") or "")
        tags = hashtag_tags(f"{title} {body}")
        source_id = str(row.get("aweme_id") or "")
        url = str(row.get("aweme_url") or "")
        video_download_url = str(row.get("video_download_url") or "")
        published_at = str(row.get("create_time") or "")
        image_urls = []
    elif platform == "xhs":
        title = str(row.get("title") or "")
        body = str(row.get("desc") or "")
        tags = split_tags(row.get("tag_list"))
        source_id = str(row.get("note_id") or "")
        url = str(row.get("note_url") or "")
        video_download_url = first_media_url(row.get("video_url"))
        published_at = str(row.get("time") or row.get("last_update_time") or "")
        image_urls = split_image_urls(row.get("image_list"))
    else:
        raise ValueError(f"unsupported platform: {platform}")

    author_name = str(row.get("nickname") or "")
    account_name = account_name_from_path(source_file) or author_name
    metrics = {
        "likes": parse_int(row.get("liked_count")),
        "collects": parse_int(row.get("collected_count")),
        "comments": parse_int(row.get("comment_count")),
        "shares": parse_int(row.get("share_count")),
    }
    return NormalizedRecord(
        platform=platform,
        source_id=source_id,
        source_file=str(source_file),
        title=title.strip(),
        body=body.strip(),
        author_name=author_name.strip(),
        published_at=published_at,
        metrics=metrics,
        tags=tags,
        url=url,
        video_download_url=video_download_url,
        text_fingerprint=fingerprint(title, body, author_name),
        account_name=account_name,
        image_urls=image_urls,
    )


SQLITE_ACCOUNT_CANDIDATES_PATH = Path("10_Knowledge/candidates/account_assets/sqlite_imports/latest_account_candidates.json")
SQLITE_INGEST_STATE_PATH = Path("00_System/runtime/state/sqlite_ingest/state.json")
DEFAULT_SQLITE_DATABASE_PATH = Path("数据/sqlite_tables.db")


def latest_sqlite_candidate_records_path(root: Path) -> Path | None:
    path = root / SQLITE_ACCOUNT_CANDIDATES_PATH
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    batch_dir = str(payload.get("source_batch_dir", "")).strip() if isinstance(payload, dict) else ""
    if not batch_dir:
        return None
    records_path = root / batch_dir / "records.jsonl"
    return records_path if records_path.exists() else None


def normalize_sqlite_candidate_record(row: dict[str, Any]) -> NormalizedRecord:
    metrics = row.get("metrics", {}) if isinstance(row.get("metrics"), dict) else {}
    tags = row.get("tags", []) if isinstance(row.get("tags"), list) else []
    suggested = row.get("suggested_directions", []) if isinstance(row.get("suggested_directions"), list) else []
    source_keyword = str(row.get("source_keyword") or "")
    source_id = str(row.get("source_id") or row.get("stable_id") or "")
    title = str(row.get("title") or "")
    body = str(row.get("summary") or "")
    account_name = str(row.get("account_name") or row.get("source_keyword") or "")
    stable_id = str(row.get("stable_id") or f"{row.get('platform', '')}:{source_id}")
    video_download_url = first_media_url(
        first_non_empty(
            row.get("video_url"),
            row.get("video_download_url"),
            row.get("download_url"),
            row.get("play_url"),
        )
    )
    return NormalizedRecord(
        platform=str(row.get("platform") or ""),
        source_id=source_id,
        source_file=stable_id,
        title=title,
        body=body,
        author_name=account_name,
        published_at="",
        metrics={
            "likes": parse_int(metrics.get("likes")),
            "collects": parse_int(metrics.get("collects")),
            "comments": parse_int(metrics.get("comments")),
            "shares": parse_int(metrics.get("shares")),
        },
        tags=list(dict.fromkeys([str(tag) for tag in [*tags, *suggested, source_keyword] if str(tag)])),
        url=str(row.get("url") or ""),
        video_download_url=video_download_url,
        text_fingerprint=stable_id,
        account_name=account_name,
    )


def sqlite_database_path(root: Path) -> Path | None:
    state_path = root / SQLITE_INGEST_STATE_PATH
    configured = ""
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            configured = str(state.get("database") or "").strip() if isinstance(state, dict) else ""
        except (OSError, json.JSONDecodeError):
            configured = ""
    candidate = Path(configured).expanduser() if configured else DEFAULT_SQLITE_DATABASE_PATH
    if not candidate.is_absolute():
        candidate = root / candidate
    return candidate if candidate.is_file() else None


def douyin_video_urls_from_sqlite(root: Path) -> dict[str, str]:
    database = sqlite_database_path(root)
    if database is None:
        return {}
    try:
        with sqlite3.connect(database) as conn:
            columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(douyin_aweme)")}
            if not {"aweme_id", "video_download_url"}.issubset(columns):
                return {}
            rows = conn.execute(
                "SELECT CAST(aweme_id AS TEXT), video_download_url "
                "FROM douyin_aweme WHERE video_download_url IS NOT NULL AND TRIM(video_download_url) != ''"
            ).fetchall()
    except sqlite3.Error:
        return {}
    return {str(source_id): str(url).strip() for source_id, url in rows if str(source_id) and str(url).strip()}


def load_sqlite_candidate_records(root: Path) -> tuple[list[NormalizedRecord], int, list[dict[str, str]]]:
    path = latest_sqlite_candidate_records_path(root)
    if path is None:
        return [], 0, []
    records: list[NormalizedRecord] = []
    failed_rows: list[dict[str, str]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return [], 0, [{"path": str(path.relative_to(root)), "stage": "read", "error_type": type(exc).__name__, "message": str(exc)}]
    douyin_video_urls: dict[str, str] | None = None
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            failed_rows.append(
                {
                    "path": f"{path.relative_to(root)}:{index}",
                    "stage": "jsonl_decode",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
            continue
        if not isinstance(row, dict):
            failed_rows.append(
                {
                    "path": f"{path.relative_to(root)}:{index}",
                    "stage": "record_validation",
                    "error_type": "InvalidRecordType",
                    "message": "expected record to be an object",
                }
            )
            continue
        platform = str(row.get("platform") or "")
        source_id = str(row.get("source_id") or row.get("stable_id") or "")
        if platform not in {"douyin", "xhs"} or not source_id:
            continue
        if platform == "douyin" and not first_non_empty(
            row.get("video_url"), row.get("video_download_url"), row.get("download_url"), row.get("play_url")
        ):
            if douyin_video_urls is None:
                douyin_video_urls = douyin_video_urls_from_sqlite(root)
            hydrated_url = douyin_video_urls.get(source_id, "")
            if hydrated_url:
                row = {**row, "video_download_url": hydrated_url}
        records.append(normalize_sqlite_candidate_record(row))
    return records, len(records), failed_rows


def classify_json(path: Path, rows: list[dict[str, Any]]) -> str:
    name = path.name.lower()
    sample = rows[0] if rows else {}
    if "comment_id" in sample or "comments" in name:
        return "douyin_comments"
    if "aweme_id" in sample:
        return "douyin_contents"
    if "note_id" in sample:
        return "xhs_contents"
    if "user_id" in sample and ("creators" in name or "sec_uid" in sample):
        return "creators"
    return "unknown"


def load_records_detailed(root: Path) -> tuple[list[NormalizedRecord], dict[str, int], list[dict[str, str]]]:
    raw_counts = {
        "douyin_contents": 0,
        "xhs_contents": 0,
        "douyin_comments": 0,
        "creators": 0,
        "unknown": 0,
        "sqlite_candidates": 0,
    }
    records: list[NormalizedRecord] = []
    failed_files: list[dict[str, str]] = []
    search_roots = [root / "数据", root / "00_Inbox"]
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*.json")):
            relative_path = str(path.relative_to(root))
            if path.name == "manifest.json" and "sqlite_imports" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                failed_files.append(
                    {
                        "path": relative_path,
                        "stage": "read",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                continue
            try:
                rows = json.loads(content)
            except json.JSONDecodeError as exc:
                failed_files.append(
                    {
                        "path": relative_path,
                        "stage": "json_decode",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
                continue
            if not isinstance(rows, list):
                raw_counts["unknown"] += 1
                failed_files.append(
                    {
                        "path": relative_path,
                        "stage": "top_level_validation",
                        "error_type": "InvalidTopLevelType",
                        "message": f"expected list, got {type(rows).__name__}",
                    }
                )
                continue
            if any(not isinstance(row, dict) for row in rows):
                raw_counts["unknown"] += len(rows)
                failed_files.append(
                    {
                        "path": relative_path,
                        "stage": "record_validation",
                        "error_type": "InvalidRecordType",
                        "message": "expected every record to be an object",
                    }
                )
                continue
            kind = classify_json(path, rows)
            raw_counts[kind] = raw_counts.get(kind, 0) + len(rows)
            if kind == "douyin_contents":
                records.extend(normalize_record("douyin", row, path.relative_to(root)) for row in rows)
            elif kind == "xhs_contents":
                records.extend(normalize_record("xhs", row, path.relative_to(root)) for row in rows)
    sqlite_records, sqlite_count, sqlite_failed = load_sqlite_candidate_records(root)
    records.extend(sqlite_records)
    raw_counts["sqlite_candidates"] = sqlite_count
    failed_files.extend(sqlite_failed)
    return records, raw_counts, failed_files


def load_records(root: Path) -> tuple[list[NormalizedRecord], dict[str, int]]:
    records, raw_counts, _ = load_records_detailed(root)
    return records, raw_counts


def better_record(left: NormalizedRecord, right: NormalizedRecord) -> NormalizedRecord:
    left_total = sum(left.metrics.values())
    right_total = sum(right.metrics.values())
    left_text = len(left.title) + len(left.body)
    right_text = len(right.title) + len(right.body)
    return right if (right_total, right_text) > (left_total, left_text) else left


def deduplicate_records(records: list[NormalizedRecord]) -> tuple[list[NormalizedRecord], dict[str, int]]:
    by_source: dict[tuple[str, str], NormalizedRecord] = {}
    duplicate_source_id = 0
    for record in records:
        key = (record.platform, record.source_id)
        if key in by_source:
            duplicate_source_id += 1
            by_source[key] = better_record(by_source[key], record)
        else:
            by_source[key] = record

    by_fingerprint: dict[str, NormalizedRecord] = {}
    duplicate_text = 0
    for record in by_source.values():
        if record.text_fingerprint in by_fingerprint:
            duplicate_text += 1
            by_fingerprint[record.text_fingerprint] = better_record(by_fingerprint[record.text_fingerprint], record)
        else:
            by_fingerprint[record.text_fingerprint] = record

    return list(by_fingerprint.values()), {
        "duplicate_source_id": duplicate_source_id,
        "duplicate_text": duplicate_text,
        "unique_records": len(by_fingerprint),
    }


def detect_directions(record: NormalizedRecord) -> list[str]:
    text = f"{record.title} {record.body} {' '.join(record.tags)}"
    lowered = text.lower()
    directions = []
    for direction, keywords in DIRECTION_KEYWORDS.items():
        scoped_account = DIRECTION_ACCOUNT_SCOPE.get(direction)
        if scoped_account and scoped_account not in {record.account_name, record.author_name}:
            continue
        for keyword in keywords:
            if keyword.lower() in lowered:
                directions.append(direction)
                break
    return directions or ["未归类"]


def heat_score(record: NormalizedRecord) -> float:
    likes = record.metrics["likes"]
    collects = record.metrics["collects"]
    comments = record.metrics["comments"]
    shares = record.metrics["shares"]
    if record.platform == "xhs":
        return round(collects * 0.45 + likes * 0.3 + shares * 0.15 + comments * 0.1, 2)
    return round(shares * 0.3 + collects * 0.3 + comments * 0.2 + likes * 0.2, 2)


def build_direction_rankings(records: list[NormalizedRecord], limit: int = 10) -> dict[str, list[RankedRecord]]:
    buckets: dict[str, list[tuple[NormalizedRecord, float]]] = {}
    for record in records:
        for direction in detect_directions(record):
            buckets.setdefault(direction, []).append((record, heat_score(record)))

    rankings: dict[str, list[RankedRecord]] = {}
    for direction, items in buckets.items():
        sorted_items = sorted(items, key=lambda item: (item[1], sum(item[0].metrics.values())), reverse=True)
        rankings[direction] = [
            RankedRecord(record=record, direction=direction, score=score, rank=index + 1)
            for index, (record, score) in enumerate(sorted_items[:limit])
        ]
    return dict(sorted(rankings.items(), key=lambda item: (-len(item[1]), item[0])))


def median(values: list[int]) -> float:
    return round(float(statistics.median(values)), 2) if values else 0.0


def direction_summary(records: list[NormalizedRecord], rankings: dict[str, list[RankedRecord]]) -> list[dict[str, Any]]:
    summary = []
    for direction, ranked in rankings.items():
        direction_records = [item.record for item in ranked]
        summary.append(
            {
                "direction": direction,
                "top_count": len(ranked),
                "likes_median": median([record.metrics["likes"] for record in direction_records]),
                "collects_median": median([record.metrics["collects"] for record in direction_records]),
                "comments_median": median([record.metrics["comments"] for record in direction_records]),
                "shares_median": median([record.metrics["shares"] for record in direction_records]),
            }
        )
    return summary


def account_summary(records: list[NormalizedRecord]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[NormalizedRecord]] = {}
    for record in records:
        grouped.setdefault((record.account_name or "未知账号", record.platform), []).append(record)
    rows = []
    for (account_name, platform), account_records in grouped.items():
        rows.append(
            {
                "account_name": account_name,
                "platform": platform,
                "count": len(account_records),
                "likes_sum": sum(record.metrics["likes"] for record in account_records),
                "collects_sum": sum(record.metrics["collects"] for record in account_records),
                "comments_sum": sum(record.metrics["comments"] for record in account_records),
                "shares_sum": sum(record.metrics["shares"] for record in account_records),
            }
        )
    return sorted(rows, key=lambda row: (row["platform"], row["account_name"]))


def account_direction_summary(records: list[NormalizedRecord], limit: int = 8) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[NormalizedRecord]] = {}
    for record in records:
        for direction in detect_directions(record):
            grouped.setdefault((record.account_name or "未知账号", record.platform, direction), []).append(record)

    rows = []
    for (account_name, platform, direction), direction_records in grouped.items():
        top_record = max(direction_records, key=heat_score)
        rows.append(
            {
                "account_name": account_name,
                "platform": platform,
                "direction": direction,
                "count": len(direction_records),
                "top_source_id": top_record.source_id,
                "top_title": top_record.title,
                "top_score": heat_score(top_record),
            }
        )
    rows.sort(key=lambda row: (row["account_name"], row["platform"], -row["count"], -row["top_score"], row["direction"]))
    per_account: dict[tuple[str, str], int] = {}
    limited = []
    for row in rows:
        key = (row["account_name"], row["platform"])
        count = per_account.get(key, 0)
        if count < limit:
            limited.append(row)
            per_account[key] = count + 1
    return limited


def first_sentence(text: str, length: int = 80) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned[:length] if cleaned else "未提供正文"


def infer_audience(direction: str, record: NormalizedRecord) -> str:
    if direction in {"减脂餐", "一人食", "备餐"}:
        return "想低成本、可执行地安排饮食的人"
    if direction in {"赚钱", "创业", "自媒体", "短视频"}:
        return "想通过内容或项目获得增长的普通人"
    return "想提升行动质量和认知效率的普通人"


def reusable_template(direction: str, record: NormalizedRecord) -> str:
    if record.platform == "xhs":
        return "{人群/场景} + {周期/清单/步骤} + {明确收益}"
    return "强观点开头 -> 解释为什么 -> 给具体动作 -> 金句或行动号召"


def golden_3s_hook(record: NormalizedRecord) -> str:
    source = record.title or first_sentence(record.body, 80)
    hook = first_sentence(source, 42)
    return f"{hook}。"


def ending_quote_or_interaction(record: NormalizedRecord) -> str:
    text = first_sentence(record.body or record.title, 180)
    if any(marker in text for marker in ["评论", "留言", "想一想", "思考", "行动", "试试", "记住"]):
        return text
    return "未明确"


def first_non_unknown(directions: list[str]) -> str:
    for direction in directions:
        if direction != "未归类":
            return direction
    return directions[0] if directions else "未归类"


def candidate_topic_angle(direction: str, record: NormalizedRecord) -> str:
    if direction in {"赚钱", "创业", "自媒体", "短视频", "个人成长", "人生策略", "做事框架", "高手思考模型", "认知升级", "结构化理解", "商业机会", "财富策略"}:
        return f"围绕{direction}拆成一个可执行的方法或行动模板"
    if direction in {"剧情短剧", "喜剧反转", "身份错位短剧", "生活荒诞反转", "爱情关系喜剧", "性格标签喜剧", "人际社交观察", "职场关系"}:
        return f"围绕{direction}拆成角色关系、场景冲突和反转结构"
    if record.platform == "xhs":
        return f"围绕{direction}做成步骤清单、周期清单或结果清单"
    return f"围绕{direction}提炼可复用表达结构"


def candidate_content_format(record: NormalizedRecord) -> str:
    return "图文清单/教程" if record.platform == "xhs" else "口播短视频/图文改写"


def candidate_topic_rows(rankings: dict[str, list[RankedRecord]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for direction, ranked_items in rankings.items():
        for item in ranked_items:
            record = item.record
            rows.append(
                {
                    "topic_id": f"candidate-{record.platform}-{direction}-{record.source_id}",
                    "platform": record.platform,
                    "account_name": record.account_name or record.author_name,
                    "direction": direction,
                    "rank": item.rank,
                    "score": item.score,
                    "source_id": record.source_id,
                    "source_url": record.url,
                    "title": record.title,
                    "topic_angle": candidate_topic_angle(direction, record),
                    "content_format": candidate_content_format(record),
                    "audience": infer_audience(direction, record),
                    "template": reusable_template(direction, record),
                    "metrics": record.metrics,
                    "published_at": record.published_at,
                    "status": "candidate",
                }
            )
    return rows


def content_inventory_rows(records: list[NormalizedRecord], rankings: dict[str, list[RankedRecord]]) -> list[dict[str, Any]]:
    best_rankings: dict[tuple[str, str], dict[str, Any]] = {}
    for direction, ranked_items in rankings.items():
        for item in ranked_items:
            key = (item.record.platform, item.record.source_id)
            current = best_rankings.get(key)
            if current is None or item.score > current["score"] or (item.score == current["score"] and item.rank < current["rank"]):
                best_rankings[key] = {"direction": direction, "rank": item.rank, "score": item.score}

    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: (item.account_name or item.author_name, item.platform, item.source_id)):
        directions = detect_directions(record)
        primary_direction = first_non_unknown(directions)
        best = best_rankings.get((record.platform, record.source_id), {})
        best_rank = int(best["rank"]) if best.get("rank") else 999
        rows.append(
            {
                "platform": record.platform,
                "account_name": record.account_name or record.author_name,
                "source_id": record.source_id,
                "source_url": record.url,
                "published_at": record.published_at,
                "title": record.title,
                "body_snippet": first_sentence(record.body or record.title, 120),
                "directions": directions,
                "primary_direction": primary_direction,
                "direction_count": len([direction for direction in directions if direction != "未归类"]),
                "heat_score": heat_score(record),
                "metrics": record.metrics,
                "best_direction": best.get("direction", primary_direction),
                "best_direction_rank": best.get("rank", ""),
                "best_direction_score": best.get("score", ""),
                "content_hint": candidate_topic_angle(primary_direction, record),
                "content_format": candidate_content_format(record),
                "learning_priority": "high" if best_rank <= 3 else "medium" if heat_score(record) >= 20 else "low",
            }
        )
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def render_content_inventory_md(rows: list[dict[str, Any]], account_name: str, records: list[NormalizedRecord], raw_counts: dict[str, int], dedupe_stats: dict[str, int]) -> str:
    lines = [
        "# 初扫知识池：内容清单",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"账号过滤：{account_name or '未启用'}",
        f"清洗后内容数：{len(rows)}",
        "",
        "## 数据概览",
        "",
        f"- 抖音内容：{raw_counts.get('douyin_contents', 0)}",
        f"- 小红书内容：{raw_counts.get('xhs_contents', 0)}",
        f"- 抖音评论：{raw_counts.get('douyin_comments', 0)}",
        f"- 去重后内容：{dedupe_stats.get('unique_records', len(records))}",
        "",
        "## 账号与方向",
        "",
        "| 账号 | 平台 | 内容数 | 点赞合计 | 收藏合计 | 评论合计 | 转发合计 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in account_summary(records):
        lines.append(
            f"| {row['account_name']} | {row['platform']} | {row['count']} | {row['likes_sum']} | {row['collects_sum']} | {row['comments_sum']} | {row['shares_sum']} |"
        )
    lines.extend([
        "",
        "| 账号 | 平台 | 方向 | 内容数 | Top内容 | Top分数 |",
        "| --- | --- | --- | ---: | --- | ---: |",
    ])
    for row in account_direction_summary(records):
        lines.append(
            f"| {row['account_name']} | {row['platform']} | {row['direction']} | {row['count']} | {row['top_title'].replace(chr(10), ' ')[:40]} | {row['top_score']} |"
        )
    lines.extend([
        "",
        "## 内容清单 Top50",
        "",
        "| 账号 | 平台 | 标题 | 主方向 | 热度分 | 建议 | 原链接 |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ])
    top_rows = sorted(rows, key=lambda row: (float(row["heat_score"]), float(row["best_direction_score"] or 0)), reverse=True)[:50]
    for row in top_rows:
        title = str(row["title"]).replace("\n", " ")[:60]
        lines.append(
            f"| {row['account_name']} | {row['platform']} | {title} | {row['primary_direction']} | {row['heat_score']} | {row['learning_priority']} | {row['source_url']} |"
        )
    return "\n".join(lines) + "\n"


def render_topic_pool_md(rows: list[dict[str, Any]], account_name: str) -> str:
    lines = [
        "# 初扫知识池：代选选题池",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"账号过滤：{account_name or '未启用'}",
        "",
        "全部内容均为候选，不等于正式知识。",
        "",
        "| 方向 | 排名 | 账号 | 平台 | 原标题 | 候选选题角度 | 热度分 | 证据 |",
        "| --- | ---: | --- | --- | --- | --- | ---: | --- |",
    ]
    for row in sorted(rows, key=lambda item: (item["direction"], item["rank"], -float(item["score"]))):
        title = str(row["title"]).replace("\n", " ")[:48]
        angle = str(row["topic_angle"]).replace("\n", " ")[:48]
        lines.append(
            f"| {row['direction']} | {row['rank']} | {row['account_name']} | {row['platform']} | {title} | {angle} | {row['score']} | {row['source_url']} |"
        )
    return "\n".join(lines) + "\n"


def render_direction_matrix_md(rankings: dict[str, list[RankedRecord]], account_name: str) -> str:
    lines = [
        "# 初扫知识池：方向矩阵",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"账号过滤：{account_name or '未启用'}",
        "",
        "每个方向按数据热度取 Top10 代表视频。",
        "",
    ]
    for direction, ranked_items in rankings.items():
        lines.extend(
            [
                f"## {direction}",
                "",
                "| 排名 | 账号 | 平台 | 标题 | 热度分 | 点赞 | 收藏 | 评论 | 转发 | 证据 |",
                "| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for item in ranked_items:
            record = item.record
            metrics = record.metrics
            title = record.title.replace("\n", " ")[:60]
            lines.append(
                f"| {item.rank} | {record.account_name or record.author_name} | {record.platform} | {title} | {item.score} | {metrics['likes']} | {metrics['collects']} | {metrics['comments']} | {metrics['shares']} | {record.url} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def write_initial_knowledge_outputs(
    root: Path,
    account_name: str,
    records: list[NormalizedRecord],
    raw_counts: dict[str, int],
    dedupe_stats: dict[str, int],
    rankings: dict[str, list[RankedRecord]],
) -> dict[str, str]:
    output_dir = video_learning_dir(root) / "initial_knowledge"
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_rows = content_inventory_rows(records, rankings)
    topic_rows = candidate_topic_rows(rankings)
    write_jsonl(output_dir / "latest_content_inventory.jsonl", inventory_rows)
    (output_dir / "latest_content_inventory.md").write_text(
        render_content_inventory_md(inventory_rows, account_name, records, raw_counts, dedupe_stats),
        encoding="utf-8",
    )
    write_jsonl(output_dir / "latest_topic_pool.jsonl", topic_rows)
    (output_dir / "latest_topic_pool.md").write_text(render_topic_pool_md(topic_rows, account_name), encoding="utf-8")
    (output_dir / "latest_direction_matrix.md").write_text(render_direction_matrix_md(rankings, account_name), encoding="utf-8")
    return {
        "initial_knowledge_dir": str(output_dir.relative_to(root)),
        "content_inventory": str((output_dir / "latest_content_inventory.md").relative_to(root)),
        "topic_pool": str((output_dir / "latest_topic_pool.md").relative_to(root)),
        "direction_matrix": str((output_dir / "latest_direction_matrix.md").relative_to(root)),
    }


def high_confidence(item: RankedRecord) -> bool:
    record = item.record
    if item.direction == "未归类":
        return False
    if not record.source_id or len(record.title + record.body) < 20:
        return False
    if item.rank > 3:
        return False
    return item.score >= 20


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.UNICODE).strip("_")
    return cleaned or "unknown"


def media_duration_seconds(path: Path) -> float:
    ffprobe = find_executable("ffprobe")
    if not ffprobe or not path.exists():
        return 0.0
    try:
        probe = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(json.loads(probe.stdout).get("format", {}).get("duration") or 0.0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        return 0.0


def media_has_stream(path: Path, stream_selector: str) -> bool:
    ffprobe = find_executable("ffprobe")
    if not ffprobe or not path.exists():
        return True
    try:
        probe = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                stream_selector,
                "-show_entries",
                "stream=codec_type",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        streams = json.loads(probe.stdout).get("streams") or []
        return bool(streams)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, subprocess.SubprocessError):
        return False


def transcript_covers_video(video_path: Path, transcript_json_path: Path) -> bool:
    duration = media_duration_seconds(video_path)
    if duration <= 0 or not transcript_json_path.exists() or transcript_json_path.stat().st_size <= 0:
        return False
    try:
        transcript = json.loads(transcript_json_path.read_text(encoding="utf-8"))
        segments = transcript.get("segments") or []
        transcript_end = max((float(segment.get("end") or 0.0) for segment in segments), default=0.0)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False
    allowed_tail_gap = max(10.0, duration * 0.05)
    return transcript_end >= duration - allowed_tail_gap


def transcript_tail_gap_seconds(video_path: Path, segments: list[dict[str, Any]]) -> float:
    duration = media_duration_seconds(video_path)
    transcript_end = max((float(segment.get("end") or 0.0) for segment in segments), default=0.0)
    return max(duration - transcript_end, 0.0)


def append_no_speech_tail_marker(video_path: Path, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    duration = media_duration_seconds(video_path)
    if duration <= 0:
        return segments
    last_end = max((float(segment.get("end") or 0.0) for segment in segments), default=0.0)
    allowed_tail_gap = max(10.0, duration * 0.05)
    if segments and duration - last_end > allowed_tail_gap:
        segments = [
            *segments,
            {
                "index": len(segments) + 1,
                "start": round(last_end, 2),
                "end": round(duration, 2),
                "text": "[尾部无可识别语音/音乐或环境声]",
            },
        ]
    return segments


def write_transcript_artifacts(
    transcript_json_path: Path,
    transcript_srt_path: Path,
    language: str,
    duration: Any,
    segments: list[dict[str, Any]],
) -> None:
    transcript_json_path.write_text(
        json.dumps(
            {
                "language": language,
                "duration": duration,
                "segments": segments,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    transcript_srt_path.write_text(srt_from_segments(segments), encoding="utf-8")


PIPELINE_STEPS = ["download", "validate_video", "extract_audio", "transcribe", "scene_detect", "write_card"]


def pipeline_state_path(artifact_dir: Path) -> Path:
    return artifact_dir / "_pipeline_state.json"


def load_pipeline_state(artifact_dir: Path, record: NormalizedRecord | None = None) -> dict[str, Any]:
    path = pipeline_state_path(artifact_dir)
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                state.setdefault("steps", {})
                return state
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "platform": record.platform if record else "",
        "source_id": record.source_id if record else "",
        "account_name": (record.account_name or record.author_name) if record else "",
        "current_step": "pending",
        "steps": {},
    }


def save_pipeline_state(artifact_dir: Path, state: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json_file(pipeline_state_path(artifact_dir), state)


def mark_pipeline_step(
    artifact_dir: Path,
    state: dict[str, Any],
    step: str,
    status: str,
    validation: str = "",
    reason: str = "",
    error: str = "",
) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    entry = state.setdefault("steps", {}).setdefault(step, {})
    entry["status"] = status
    if validation:
        entry["validation"] = validation
    if reason:
        entry["reason"] = reason
    elif "reason" in entry and validation == "valid":
        entry.pop("reason", None)
    if error:
        entry["last_error"] = error
        entry["failed_at"] = now
    elif status == "completed":
        entry.pop("last_error", None)
        entry["completed_at"] = now
    elif status == "running":
        entry["started_at"] = now
    state["current_step"] = step if status != "completed" else state.get("current_step", step)
    save_pipeline_state(artifact_dir, state)


def mark_pipeline_bundle_complete(artifact_dir: Path, state: dict[str, Any]) -> None:
    for step in ["download", "validate_video", "extract_audio", "transcribe", "scene_detect"]:
        mark_pipeline_step(artifact_dir, state, step, "completed", "valid")
    state["current_step"] = "completed"
    save_pipeline_state(artifact_dir, state)


def valid_keyframe_files(artifact_dir: Path) -> list[Path]:
    image_files = sorted(artifact_dir.glob("*.jpg")) + sorted(artifact_dir.glob("*.png"))
    keyframes_dir = artifact_dir / "keyframes"
    if keyframes_dir.is_dir():
        image_files.extend(sorted(keyframes_dir.glob("*.jpg")) + sorted(keyframes_dir.glob("*.png")))
    valid: list[Path] = []
    for path in image_files:
        if not path.is_file() or path.stat().st_size <= 0:
            continue
        try:
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
            valid.append(path)
        except Exception:
            continue
    return valid


def validate_video_artifact(video_path: Path) -> dict[str, str]:
    if not video_path.exists() or video_path.stat().st_size <= 0:
        return {"validation": "missing", "reason": "video_missing"}
    if not media_file_is_readable(video_path):
        return {"validation": "corrupt", "reason": "ffprobe_failed"}
    if not media_file_decodes(video_path):
        return {"validation": "corrupt", "reason": "ffmpeg_decode_failed"}
    if not media_has_stream(video_path, "v:0"):
        return {"validation": "corrupt", "reason": "video_stream_missing"}
    duration = media_duration_seconds(video_path)
    if duration <= 1.0:
        return {"validation": "corrupt", "reason": "duration_too_short"}
    return {"validation": "valid", "reason": ""}


def validate_audio_artifact(video_path: Path, audio_path: Path) -> dict[str, str]:
    if not audio_path.exists() or audio_path.stat().st_size <= 0:
        return {"validation": "missing", "reason": "audio_missing"}
    if video_path.exists() and audio_path.stat().st_mtime < video_path.stat().st_mtime:
        return {"validation": "stale", "reason": "audio_older_than_video"}
    duration = media_duration_seconds(audio_path)
    if duration <= 0:
        return {"validation": "corrupt", "reason": "audio_duration_missing"}
    if not media_has_stream(audio_path, "a:0"):
        return {"validation": "corrupt", "reason": "audio_stream_missing"}
    video_duration = media_duration_seconds(video_path)
    if video_duration > 0 and abs(duration - video_duration) > max(10.0, video_duration * 0.1):
        return {"validation": "partial", "reason": "audio_duration_mismatch"}
    return {"validation": "valid", "reason": ""}


def validate_transcript_artifact(video_path: Path, audio_path: Path, transcript_json_path: Path, transcript_srt_path: Path) -> dict[str, str]:
    if not transcript_json_path.exists() or transcript_json_path.stat().st_size <= 0:
        return {"validation": "missing", "reason": "transcript_json_missing"}
    if not transcript_srt_path.exists() or transcript_srt_path.stat().st_size <= 0:
        return {"validation": "missing", "reason": "transcript_srt_missing"}
    upstream_mtime = max(path.stat().st_mtime for path in [video_path, audio_path] if path.exists())
    if transcript_json_path.stat().st_mtime < upstream_mtime or transcript_srt_path.stat().st_mtime < upstream_mtime:
        return {"validation": "stale", "reason": "transcript_older_than_upstream"}
    try:
        transcript = json.loads(transcript_json_path.read_text(encoding="utf-8"))
        segments = transcript.get("segments") or []
        if not segments:
            return {"validation": "partial", "reason": "transcript_segments_empty"}
        for segment in segments:
            if segment.get("start") is None or segment.get("end") is None or not str(segment.get("text") or "").strip():
                return {"validation": "partial", "reason": "transcript_segment_invalid"}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {"validation": "corrupt", "reason": "transcript_json_invalid"}
    if not transcript_covers_video(video_path, transcript_json_path):
        return {"validation": "partial", "reason": "transcript_end_before_video_end"}
    return {"validation": "valid", "reason": ""}


def validate_scene_artifacts(video_path: Path, artifact_dir: Path) -> dict[str, str]:
    scene_files = sorted(artifact_dir.glob("*Scenes.csv")) + sorted(artifact_dir.glob("scenes.csv"))
    if not scene_files:
        return {"validation": "missing", "reason": "scenes_missing"}
    if any(not path.is_file() or path.stat().st_size <= 0 for path in scene_files):
        return {"validation": "corrupt", "reason": "scenes_empty"}
    if video_path.exists() and any(path.stat().st_mtime < video_path.stat().st_mtime for path in scene_files):
        return {"validation": "stale", "reason": "scenes_older_than_video"}
    keyframes = valid_keyframe_files(artifact_dir)
    if not keyframes:
        return {"validation": "missing", "reason": "keyframes_missing_or_corrupt"}
    if video_path.exists() and any(path.stat().st_mtime < video_path.stat().st_mtime for path in keyframes):
        return {"validation": "stale", "reason": "keyframes_older_than_video"}
    return {"validation": "valid", "reason": ""}


def validate_learning_card(root: Path, manifest_entry: dict[str, Any]) -> dict[str, str]:
    if manifest_entry.get("status") != "completed":
        return {"validation": "missing", "reason": "manifest_not_completed"}
    card_path_text = str(manifest_entry.get("card_path") or "")
    if not card_path_text:
        return {"validation": "missing", "reason": "card_path_missing"}
    card_path = root / card_path_text
    if not card_path.exists() or card_path.stat().st_size <= 0:
        return {"validation": "missing", "reason": "card_missing"}
    try:
        text = card_path.read_text(encoding="utf-8")
    except OSError:
        return {"validation": "corrupt", "reason": "card_unreadable"}
    if "video_analysis_status: degraded" in text or "video_analysis_status: degraded_video_failed" in text:
        return {"validation": "corrupt", "reason": "card_video_analysis_failed"}
    return {"validation": "valid", "reason": ""}


def existing_video_bundle_is_complete(
    video_path: Path,
    audio_path: Path,
    metadata_path: Path,
    transcript_json_path: Path,
    transcript_srt_path: Path,
    scene_files: list[Path],
) -> bool:
    derived_paths = [audio_path, metadata_path, transcript_json_path, transcript_srt_path, *scene_files]
    if not video_path.exists() or not scene_files or any(not path.exists() or path.stat().st_size <= 0 for path in derived_paths):
        return False
    if not media_file_is_usable(video_path):
        return False
    video_mtime = video_path.stat().st_mtime
    if any(path.stat().st_mtime < video_mtime for path in derived_paths):
        return False
    if not valid_keyframe_files(video_path.parent):
        return False
    return transcript_covers_video(video_path, transcript_json_path)


def video_status(
    root: Path,
    record: NormalizedRecord,
    analyze_video: bool,
    artifacts_dir: Path | None = None,
    artifact_layout: str = "flat",
) -> dict[str, Any]:
    status: dict[str, Any] = {
        "requested": analyze_video,
        "has_video_url": bool(record.video_download_url),
        "resolved_video_url": "",
        "ffmpeg": find_executable("ffmpeg"),
        "faster_whisper": False,
        "scenedetect": False,
        "status": "metadata_only",
        "artifacts": {},
        "warnings": [],
        "errors": [],
    }
    artifact_dir = resolved_video_artifact_dir(root, record, artifacts_dir, artifact_layout)
    video_path = artifact_dir / "source.mp4"
    audio_path = artifact_dir / "audio.wav"
    metadata_path = artifact_dir / "ffprobe.json"
    transcript_json_path = artifact_dir / "transcript.json"
    transcript_srt_path = artifact_dir / "transcript.srt"
    existing_scene_files = sorted(artifact_dir.glob("*Scenes.csv"))
    pipeline_state = load_pipeline_state(artifact_dir, record)
    if existing_video_bundle_is_complete(
        video_path,
        audio_path,
        metadata_path,
        transcript_json_path,
        transcript_srt_path,
        existing_scene_files,
    ):
        mark_pipeline_bundle_complete(artifact_dir, pipeline_state)
        status["status"] = "video_transcribed_and_scenes_detected"
        status["artifacts"] = {
            "video": path_for_report(video_path, root),
            "audio": path_for_report(audio_path, root),
            "metadata": path_for_report(metadata_path, root),
            "transcript_json": path_for_report(transcript_json_path, root),
            "transcript_srt": path_for_report(transcript_srt_path, root),
            "scenes_csv": path_for_report(existing_scene_files[0], root),
        }
        image_files = sorted(artifact_dir.glob("*.jpg")) + sorted(artifact_dir.glob("*.png"))
        if image_files:
            status["artifacts"]["keyframes"] = [path_for_report(path, root) for path in image_files[:10]]
        return status

    if not analyze_video:
        return status
    try:
        download_url, resolve_warnings = resolved_record_video_url(record)
    except Exception as exc:
        status["status"] = "missing_video_url"
        status["errors"].append(f"xhs_video_url_resolve_failed: {exc}")
        return status
    if not download_url:
        status["status"] = "missing_video_url"
        return status
    status["has_video_url"] = True
    status["resolved_video_url"] = download_url
    status["warnings"].extend(resolve_warnings)
    try:
        import faster_whisper  # type: ignore # noqa: F401

        status["faster_whisper"] = True
    except Exception:
        status["faster_whisper"] = False
    try:
        import scenedetect  # type: ignore # noqa: F401

        status["scenedetect"] = True
    except Exception:
        status["scenedetect"] = False

    if not status["ffmpeg"] or not status["faster_whisper"] or not status["scenedetect"]:
        status["status"] = "degraded_missing_tools"
        return status

    artifact_dir.mkdir(parents=True, exist_ok=True)

    video_validation = validate_video_artifact(video_path)
    try:
        if video_validation["validation"] != "valid":
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "download",
                "running",
                video_validation["validation"],
                video_validation["reason"],
            )
            status["errors"].extend(
                ensure_video_file(
                    download_url,
                    video_path,
                    force_download=video_validation["validation"] in {"corrupt", "partial", "stale"},
                )
            )
            video_validation = validate_video_artifact(video_path)
        if video_validation["validation"] != "valid":
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "download",
                "failed",
                video_validation["validation"],
                video_validation["reason"],
            )
            raise RuntimeError(f"video_validation_failed: {video_validation['reason']}")
        mark_pipeline_step(artifact_dir, pipeline_state, "download", "completed", "valid")
        mark_pipeline_step(artifact_dir, pipeline_state, "validate_video", "completed", "valid")
        probe = subprocess.run(
            [find_executable("ffprobe"), "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(video_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata_path.write_text(probe.stdout, encoding="utf-8")
        status["artifacts"]["video"] = path_for_report(video_path, root)
        status["artifacts"]["metadata"] = path_for_report(metadata_path, root)
    except Exception as exc:
        status["status"] = "degraded_video_failed"
        status["errors"].append(str(exc))
        return status

    try:
        audio_validation = validate_audio_artifact(video_path, audio_path)
        if audio_validation["validation"] != "valid":
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "extract_audio",
                "running",
                audio_validation["validation"],
                audio_validation["reason"],
            )
            subprocess.run(
                [status["ffmpeg"], "-y", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            audio_validation = validate_audio_artifact(video_path, audio_path)
        if audio_validation["validation"] != "valid":
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "extract_audio",
                "failed",
                audio_validation["validation"],
                audio_validation["reason"],
            )
            raise RuntimeError(f"audio_validation_failed: {audio_validation['reason']}")
        mark_pipeline_step(artifact_dir, pipeline_state, "extract_audio", "completed", "valid")
        status["status"] = "video_downloaded_audio_extracted"
        status["artifacts"]["audio"] = path_for_report(audio_path, root)
    except Exception as exc:
        status["status"] = "degraded_video_failed"
        status["errors"].append(str(exc))
        return status

    try:
        transcript_validation = validate_transcript_artifact(video_path, audio_path, transcript_json_path, transcript_srt_path)
        if transcript_validation["validation"] != "valid":
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "transcribe",
                "running",
                transcript_validation["validation"],
                transcript_validation["reason"],
            )
            from faster_whisper import WhisperModel  # type: ignore

            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, info = model.transcribe(str(audio_path), language="zh", vad_filter=True)
            transcript_segments = []
            for index, segment in enumerate(segments, start=1):
                transcript_segments.append(
                    {
                        "index": index,
                        "start": float(segment.start),
                        "end": float(segment.end),
                        "text": segment.text.strip(),
                    }
                )
            write_transcript_artifacts(
                transcript_json_path,
                transcript_srt_path,
                getattr(info, "language", "zh"),
                getattr(info, "duration", None),
                transcript_segments,
            )
            transcript_validation = validate_transcript_artifact(video_path, audio_path, transcript_json_path, transcript_srt_path)
            if transcript_validation["validation"] != "valid":
                segments, info = model.transcribe(str(audio_path), language="zh", vad_filter=False, condition_on_previous_text=False)
                transcript_segments = []
                for index, segment in enumerate(segments, start=1):
                    text = segment.text.strip()
                    if not text:
                        continue
                    transcript_segments.append(
                        {
                            "index": len(transcript_segments) + 1,
                            "start": float(segment.start),
                            "end": float(segment.end),
                            "text": text,
                        }
                    )
                transcript_segments = append_no_speech_tail_marker(video_path, transcript_segments)
                write_transcript_artifacts(
                    transcript_json_path,
                    transcript_srt_path,
                    getattr(info, "language", "zh"),
                    getattr(info, "duration", None),
                    transcript_segments,
                )
                transcript_validation = validate_transcript_artifact(video_path, audio_path, transcript_json_path, transcript_srt_path)
        if transcript_validation["validation"] == "valid":
            mark_pipeline_step(artifact_dir, pipeline_state, "transcribe", "completed", "valid")
            status["artifacts"]["transcript_json"] = path_for_report(transcript_json_path, root)
            status["artifacts"]["transcript_srt"] = path_for_report(transcript_srt_path, root)
        else:
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "transcribe",
                "failed",
                transcript_validation["validation"],
                transcript_validation["reason"],
            )
            status["errors"].append(f"transcription_validation_failed: {transcript_validation['reason']}")
    except Exception as exc:
        mark_pipeline_step(artifact_dir, pipeline_state, "transcribe", "failed", error=str(exc))
        status["errors"].append(f"transcription_failed: {exc}")

    try:
        scene_validation = validate_scene_artifacts(video_path, artifact_dir)
        if scene_validation["validation"] != "valid":
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "scene_detect",
                "running",
                scene_validation["validation"],
                scene_validation["reason"],
            )
            scenedetect_bin = Path(sys.executable).parent / "scenedetect"
            if not scenedetect_bin.exists():
                scenedetect_bin = Path(shutil.which("scenedetect") or "")
            if not scenedetect_bin:
                raise RuntimeError("scenedetect command not found")
            subprocess.run(
                [
                    str(scenedetect_bin),
                    "-i",
                    str(video_path),
                    "-o",
                    str(artifact_dir),
                    "detect-content",
                    "list-scenes",
                    "save-images",
                    "--num-images",
                    "1",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            scene_validation = validate_scene_artifacts(video_path, artifact_dir)
        scene_files = sorted(artifact_dir.glob("*Scenes.csv"))
        image_files = sorted(artifact_dir.glob("*.jpg")) + sorted(artifact_dir.glob("*.png"))
        if scene_validation["validation"] == "valid":
            mark_pipeline_step(artifact_dir, pipeline_state, "scene_detect", "completed", "valid")
        else:
            mark_pipeline_step(
                artifact_dir,
                pipeline_state,
                "scene_detect",
                "failed",
                scene_validation["validation"],
                scene_validation["reason"],
            )
            status["errors"].append(f"scene_validation_failed: {scene_validation['reason']}")
        if scene_validation["validation"] == "valid" and scene_files:
            status["artifacts"]["scenes_csv"] = path_for_report(scene_files[0], root)
        if scene_validation["validation"] == "valid" and image_files:
            status["artifacts"]["keyframes"] = [path_for_report(path, root) for path in image_files[:10]]
    except Exception as exc:
        mark_pipeline_step(artifact_dir, pipeline_state, "scene_detect", "failed", error=str(exc))
        status["errors"].append(f"scene_detection_failed: {exc}")

    if status["artifacts"].get("transcript_json") and status["artifacts"].get("scenes_csv"):
        status["status"] = "video_transcribed_and_scenes_detected"
    elif status["artifacts"].get("transcript_json"):
        status["status"] = "video_transcribed_scene_failed"
    elif status["artifacts"].get("scenes_csv"):
        status["status"] = "video_scene_detected_transcription_failed"
    return status


def is_allowed_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    return host == "xhscdn.com" or host.endswith(".xhscdn.com")


def image_extension(url: str, default: str = ".webp") -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return default


def download_image_url(url: str, path: Path) -> None:
    def fetch(candidate_url: str) -> bytes:
        request = urllib.request.Request(
            candidate_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                "Referer": "https://www.xiaohongshu.com/",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read()

    try:
        data = fetch(url)
    except urllib.error.HTTPError as exc:
        if exc.code != 403 or not url.startswith("http://"):
            raise
        data = fetch("https://" + url[len("http://") :])
    path.write_bytes(data)


XHS_PAGE_HOSTS = {"www.xiaohongshu.com", "xiaohongshu.com", "xhslink.com"}
XHS_VIDEO_HOST_MARKERS = ("xhscdn.com", "xiaohongshu.com")
BUNDLED_NODE = Path("/Users/lao_wu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
BUNDLED_NODE_MODULES = Path("/Users/lao_wu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules")


def is_xhs_page_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (host in XHS_PAGE_HOSTS or host.endswith(".xiaohongshu.com"))


def xhs_request_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
        "Referer": "https://www.xiaohongshu.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def fetch_xhs_page_html(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers=xhs_request_headers())
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def decoded_url_text_variants(text: str) -> list[str]:
    variants = [text, html_lib.unescape(text)]
    slash_decoded = html_lib.unescape(text).replace("\\u002F", "/").replace("\\/", "/")
    variants.append(slash_decoded)
    try:
        variants.append(slash_decoded.encode("utf-8").decode("unicode_escape"))
    except UnicodeError:
        pass
    unique: list[str] = []
    for variant in variants:
        if variant not in unique:
            unique.append(variant)
    return unique


def normalize_embedded_url(url: str) -> str:
    text = html_lib.unescape(url).replace("\\u002F", "/").replace("\\/", "/")
    text = text.replace("\\u0026", "&").replace("\\&", "&")
    return text.rstrip("\\").strip()


def extract_xhs_video_urls_from_html(html: str) -> list[str]:
    candidates: list[str] = []
    patterns = [
        r"https?:\\?/\\?/[^\"'<>\s]+?(?:\.mp4|/video/|sns-video)[^\"'<>\s]*",
        r"https?://[^\"'<>\s]+?(?:\.mp4|/video/|sns-video)[^\"'<>\s]*",
    ]
    for text in decoded_url_text_variants(html):
        for pattern in patterns:
            for match in re.findall(pattern, text):
                url = normalize_embedded_url(match)
                host = (urlparse(url).hostname or "").lower()
                if any(marker in host for marker in XHS_VIDEO_HOST_MARKERS) and url not in candidates:
                    candidates.append(url)
    return candidates


def resolve_xhs_video_url(page_url: str) -> tuple[str, list[str]]:
    html = fetch_xhs_page_html(page_url)
    candidates = extract_xhs_video_urls_from_html(html)
    if not candidates and xhs_browser_resolve_enabled():
        browser_candidates = resolve_xhs_video_urls_with_browser(page_url)
        candidates.extend(url for url in browser_candidates if url not in candidates)
    if not candidates:
        raise RuntimeError("xhs_video_url_not_found_in_page")
    return candidates[0], candidates


def xhs_browser_resolve_enabled() -> bool:
    return str(os.environ.get("XHS_BROWSER_RESOLVE", "")).lower() in {"1", "true", "yes", "on"}


def node_executable_for_xhs_browser_resolve() -> str:
    configured = str(os.environ.get("XHS_NODE") or "").strip()
    if configured:
        return configured
    if BUNDLED_NODE.exists():
        return str(BUNDLED_NODE)
    return find_executable("node")


def node_path_for_xhs_browser_resolve() -> str:
    paths = []
    configured = str(os.environ.get("NODE_PATH") or "").strip()
    if configured:
        paths.append(configured)
    xhs_node_path = str(os.environ.get("XHS_NODE_PATH") or "").strip()
    if xhs_node_path:
        paths.append(xhs_node_path)
    if BUNDLED_NODE_MODULES.exists():
        paths.append(str(BUNDLED_NODE_MODULES))
    return os.pathsep.join(paths)


def resolve_xhs_video_urls_with_browser(page_url: str) -> list[str]:
    node = node_executable_for_xhs_browser_resolve()
    if not node:
        raise RuntimeError("xhs_browser_resolve_node_not_found")
    script = Path(__file__).with_name("xhs_video_capture.cjs")
    env = dict(os.environ)
    node_path = node_path_for_xhs_browser_resolve()
    if node_path:
        env["NODE_PATH"] = node_path
    timeout_seconds = int(int(env.get("XHS_BROWSER_TIMEOUT_MS", "20000")) / 1000) + 10
    completed = subprocess.run(
        [node, str(script), page_url],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=env,
    )
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"xhs_browser_resolve_bad_output: {exc}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"xhs_browser_resolve_failed: {payload.get('error') or completed.stderr.strip()}")
    urls = payload.get("video_urls", [])
    return [str(url) for url in urls if str(url).strip()]


def resolved_record_video_url(record: NormalizedRecord) -> tuple[str, list[str]]:
    if record.video_download_url:
        return record.video_download_url, []
    if record.platform == "xhs" and record.url and is_xhs_page_url(record.url):
        resolved_url, candidates = resolve_xhs_video_url(record.url)
        return resolved_url, [f"resolved_xhs_page_video_url candidates={len(candidates)}"]
    return "", []


def can_attempt_record_video(record: NormalizedRecord) -> bool:
    return bool(record.video_download_url) or (record.platform == "xhs" and bool(record.url) and is_xhs_page_url(record.url))


VIDEO_DOWNLOAD_TIMEOUT_SECONDS = 300
VIDEO_RESUME_TIMEOUT_SECONDS = 1800
VIDEO_CONNECT_TIMEOUT_SECONDS = 20


def referer_for_download_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if "xhscdn.com" in host or "xiaohongshu.com" in host:
        return "https://www.xiaohongshu.com/"
    return "https://www.douyin.com/"


def download_binary_url(url: str, path: Path, timeout: int = VIDEO_DOWNLOAD_TIMEOUT_SECONDS) -> None:
    curl = find_executable("curl")
    if curl:
        resuming = path.exists() and path.stat().st_size > 0
        resume_args = ["--continue-at", "-"] if resuming else []
        retry_count = "0" if resuming else "3"
        effective_timeout = max(timeout, VIDEO_RESUME_TIMEOUT_SECONDS) if resuming else timeout
        subprocess.run(
            [
                curl,
                "--location",
                "--fail",
                "--silent",
                "--show-error",
                "--connect-timeout",
                str(VIDEO_CONNECT_TIMEOUT_SECONDS),
                "--max-time",
                str(effective_timeout),
                "--retry",
                retry_count,
                "--retry-delay",
                "2",
                "--retry-all-errors",
                "--speed-limit",
                "1024",
                "--speed-time",
                "60",
                *resume_args,
                "-A",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                "-H",
                f"Referer: {referer_for_download_url(url)}",
                "-H",
                "Accept: */*",
                "-o",
                str(path),
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=effective_timeout + 30,
        )
        return
    path.unlink(missing_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Referer": referer_for_download_url(url),
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        path.write_bytes(response.read())


def media_file_is_readable(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    ffprobe = find_executable("ffprobe")
    if not ffprobe:
        return True
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-print_format", "json", str(path)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    return probe.returncode == 0


def media_file_decodes(path: Path) -> bool:
    if not path.exists() or path.stat().st_size <= 0:
        return False
    ffmpeg = find_executable("ffmpeg")
    if not ffmpeg:
        return media_file_is_readable(path)
    probe = subprocess.run(
        [ffmpeg, "-xerror", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=300,
    )
    return probe.returncode == 0


def media_file_is_usable(path: Path) -> bool:
    return media_file_is_readable(path) and media_file_decodes(path)


def ensure_video_file(url: str, path: Path, force_download: bool = False) -> list[str]:
    if not force_download and media_file_is_usable(path):
        return ["using_existing_video_file"]
    path.parent.mkdir(parents=True, exist_ok=True)
    download_path = path.with_name(f"{path.name}.download")
    try:
        download_binary_url(url, download_path)
    except Exception as exc:
        if media_file_is_usable(download_path):
            download_path.replace(path)
            return [f"download_reported_error_but_file_is_usable: {exc}"]
        raise
    if not media_file_is_usable(download_path):
        download_path.unlink(missing_ok=True)
        raise RuntimeError(f"downloaded video is not usable: {path}")
    download_path.replace(path)
    return []


def read_image_metadata(path: Path) -> dict[str, Any]:
    from PIL import Image

    with Image.open(path) as image:
        return {
            "width": image.width,
            "height": image.height,
            "format": image.format or "",
            "mode": image.mode,
        }


def ocr_image(path: Path) -> str:
    from PIL import Image
    import pytesseract

    with Image.open(path) as image:
        return pytesseract.image_to_string(image, lang="chi_sim+eng", config="--psm 6").strip()


def image_status(root: Path, record: NormalizedRecord, analyze_images: bool, max_images_per_note: int = 18) -> dict[str, Any]:
    status: dict[str, Any] = {
        "requested": analyze_images,
        "has_image_urls": bool(record.image_urls),
        "status": "metadata_only",
        "original_image_count": len(record.image_urls),
        "downloaded_count": 0,
        "ocr_success_count": 0,
        "truncated": False,
        "artifacts": {},
        "images": [],
        "errors": [],
    }
    if not analyze_images or not record.image_urls:
        return status

    limit = max(max_images_per_note, 0)
    urls = record.image_urls[:limit] if limit else []
    status["truncated"] = len(record.image_urls) > len(urls)
    artifact_dir = image_artifacts_dir(root) / f"{record.platform}_{record.source_id}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    index_path = artifact_dir / "image_index.json"

    for index, url in enumerate(urls, start=1):
        image_info: dict[str, Any] = {
            "index": index,
            "url": url,
            "allowed": is_allowed_image_url(url),
            "status": "pending",
            "local_path": "",
            "file_size": 0,
            "width": 0,
            "height": 0,
            "format": "",
            "ocr_text": "",
            "errors": [],
        }
        if not image_info["allowed"]:
            image_info["status"] = "blocked_url"
            image_info["errors"].append("image url is not an allowed xhscdn.com URL")
            status["images"].append(image_info)
            continue
        local_path = artifact_dir / f"image_{index:02d}{image_extension(url)}"
        try:
            download_image_url(url, local_path)
            metadata = read_image_metadata(local_path)
            image_info.update(metadata)
            image_info["local_path"] = str(local_path.relative_to(root))
            image_info["file_size"] = local_path.stat().st_size
            image_info["status"] = "downloaded"
            status["downloaded_count"] += 1
        except Exception as exc:
            image_info["status"] = "download_failed"
            image_info["errors"].append(str(exc))
            status["errors"].append(f"image_{index}_download_failed: {exc}")
            status["images"].append(image_info)
            continue

        try:
            image_info["ocr_text"] = ocr_image(local_path)
            status["ocr_success_count"] += 1
            image_info["status"] = "downloaded_ocr_completed"
        except Exception as exc:
            image_info["status"] = "downloaded_ocr_failed"
            image_info["errors"].append(str(exc))
            status["errors"].append(f"image_{index}_ocr_failed: {exc}")
        status["images"].append(image_info)

    if status["downloaded_count"] and status["ocr_success_count"]:
        status["status"] = "images_downloaded_ocr_completed"
    elif status["downloaded_count"]:
        status["status"] = "images_downloaded_ocr_failed"
    else:
        status["status"] = "degraded_image_failed"
    status["artifacts"]["image_index"] = str(index_path.relative_to(root))
    index_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return status


def srt_timestamp(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def srt_from_segments(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for segment in segments:
        blocks.append(
            f"{segment['index']}\n"
            f"{srt_timestamp(segment['start'])} --> {srt_timestamp(segment['end'])}\n"
            f"{segment['text']}\n"
        )
    return "\n".join(blocks)


def image_learning_section(record: NormalizedRecord, image: dict[str, Any]) -> str:
    if record.platform != "xhs":
        return ""
    image_lines = []
    for item in image.get("images", []):
        ocr_text = first_sentence(item.get("ocr_text", ""), 120)
        image_lines.append(
            f"- 图{item.get('index')}: {item.get('width')}x{item.get('height')} / "
            f"{item.get('status')} / OCR：{ocr_text}"
        )
    if not image_lines:
        image_lines.append("- 未执行图片下载或没有可用图片。")
    return f"""

## 图片层学习

- 原始图片数：{image.get("original_image_count", len(record.image_urls))}
- 已下载图片数：{image.get("downloaded_count", 0)}
- OCR 成功数：{image.get("ocr_success_count", 0)}
- 是否截断：{"是" if image.get("truncated") else "否"}

### 图片索引与OCR

{chr(10).join(image_lines)}

### 图文结构判断

- 首图作用：优先判断是否承担标题承诺、成果展示或收藏理由。
- 多图顺序：按封面、结果、步骤、清单、细节补充来拆解。
- 收藏价值：重点看菜单、步骤、食材、周期、成本、减脂承诺是否可照抄执行。
- 可复用图文模板：{reusable_template("减脂餐" if "减脂餐" in detect_directions(record) else "一人食", record)}
"""


def card_markdown(item: RankedRecord, video: dict[str, Any], image: dict[str, Any] | None = None) -> str:
    record = item.record
    metrics = record.metrics
    image = image or {
        "requested": False,
        "has_image_urls": bool(record.image_urls),
        "status": "metadata_only",
        "images": [],
        "errors": [],
    }
    return f"""# 深度学习卡：{record.platform} {record.source_id}

```yaml
source_id: {record.source_id}
platform: {record.platform}
account_name: {record.account_name or "未知账号"}
direction: {item.direction}
rank: {item.rank}
heat_score: {item.score}
title: {record.title}
url: {record.url}
original_video_url: {record.url}
metrics:
  likes: {metrics["likes"]}
  collects: {metrics["collects"]}
  comments: {metrics["comments"]}
  shares: {metrics["shares"]}
video_analysis_status: {video["status"]}
image_analysis_status: {image["status"]}
decision: {"keep" if high_confidence(item) else "review"}
```

原视频链接：{record.url}

## 为什么入选

- 账号：{record.account_name or "未知账号"}。
- 属于 `{item.direction}` 方向 Top{item.rank}。
- 平台加权热度分为 `{item.score}`。
- 指标证据：点赞 {metrics["likes"]}，收藏 {metrics["collects"]}，评论 {metrics["comments"]}，转发 {metrics["shares"]}。

## 内容结构

- 黄金 3 秒钩子：{golden_3s_hook(record)}
- 开头：{first_sentence(record.title, 60)}
- 痛点：{infer_audience(item.direction, record)}需要更低门槛、更可复用的方法。
- 展开：{first_sentence(record.body, 120)}
- 结尾：适合收束为一个可复述的行动建议或清单承诺。
- 结尾金句/互动引导：{ending_quote_or_interaction(record)}

## 可复用价值

- 可复用标题结构：{reusable_template(item.direction, record)}
- 可复用脚本结构：{reusable_template(item.direction, record)}
- 可生成选题：围绕 `{item.direction}` 做同主题变体、步骤化教程、标题/正文/话题组合。
- 评论边界：不学习评论正文，不从评论区提炼观点、痛点或话术；评论数量只作为互动指标。
- 可改写平台：{"小红书图文/清单" if record.platform == "xhs" else "抖音口播/小红书图文"}

## 视频层状态

```json
{json.dumps(video, ensure_ascii=False, indent=2)}
```

## 图片层状态

```json
{json.dumps(image, ensure_ascii=False, indent=2)}
```
{image_learning_section(record, image)}
"""


def formal_method_entry(item: RankedRecord) -> str:
    record = item.record
    metrics = record.metrics
    method_id = f"auto-{record.platform}-{item.direction}-{record.source_id}"
    return f"""

## 自动学习方法：{item.direction} / {record.source_id}

<!-- video-learning:auto-method:{record.platform}:{record.source_id}:{item.direction} -->

```yaml
method_id: {method_id}
platform: {record.platform}
适用领域: {item.direction}
适用人群: {infer_audience(item.direction, record)}
适用场景: 从高表现内容中提炼可复用结构
核心机制: 用明确场景和可执行承诺降低理解成本
内容结构: {reusable_template(item.direction, record)}
标题结构: {reusable_template(item.direction, record)}
正文/脚本结构: {reusable_template(item.direction, record)}
可复用模板: {reusable_template(item.direction, record)}
证据案例: {record.platform}:{record.source_id} {record.url}
指标表现: {metrics["likes"]}赞/{metrics["collects"]}藏/{metrics["comments"]}评/{metrics["shares"]}转
适合生成的选题: 围绕 {item.direction} 做步骤、清单、强观点或行动模板
不适合: 指标不足、主题不明确或仅有情绪无方法的内容
风险: 自动提炼可能过度概括，需要后续复盘校准
```
"""


def formal_topic_entry(item: RankedRecord) -> str:
    record = item.record
    topic_id = f"auto-{record.platform}-{item.direction}-{record.source_id}"
    form = "图文清单/教程" if record.platform == "xhs" else "口播短视频/图文改写"
    return f"""

## 自动学习选题：{item.direction} / {record.source_id}

<!-- video-learning:auto-topic:{record.platform}:{record.source_id}:{item.direction} -->

```yaml
topic_id: {topic_id}
platform: {record.platform}
领域: {item.direction}
人群: {infer_audience(item.direction, record)}
场景: 看到同方向高表现案例后需要可复用选题
痛点: 不知道如何把 {item.direction} 做成可执行内容
内容承诺: 拆出一个能照着做的 {item.direction} 方法
爆点: 高指标案例证明该方向有传播和收藏价值
形式: {form}
参考方法: {record.platform}:{record.source_id}
可生成标题: {record.title}
正文/脚本方向: {reusable_template(item.direction, record)}
证据: {record.url}
优先级: high
状态: ready
```
"""


def formal_template_entry(items: list[RankedRecord]) -> str:
    if not items:
        return ""
    directions = "、".join(sorted({item.direction for item in items}))
    signature = template_signature(items)
    return f"""

## 自动学习模板更新：{signature}

<!-- video-learning:auto-template:{signature} -->

适用方向：{directions}

```text
1. 先用强场景或强观点标记人群。
2. 立刻给出可执行承诺：步骤、清单、公式或每天动作。
3. 用一个具体案例证明不是空泛观点。
4. 收束为可复述标题、金句或保存理由。
```
"""


def template_signature(items: list[RankedRecord]) -> str:
    directions = "|".join(sorted({item.direction for item in items}))
    return hashlib.sha1(directions.encode("utf-8")).hexdigest()[:12]


def append_once(path: Path, marker: str, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in current:
        return False
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    return True


def write_formal_entries(root: Path, high_items: list[RankedRecord]) -> dict[str, int]:
    counts = {"methods": 0, "topics": 0, "templates": 0}
    for item in high_items:
        method_path = root / "10_Knowledge" / "formal" / "methods" / ("小红书爆款方法论_v1.md" if item.record.platform == "xhs" else "抖音爆款方法论_v1.md")
        topic_path = root / "10_Knowledge" / "formal" / "topics" / "选题灵感库_v1.md"
        method_marker = f"video-learning:auto-method:{item.record.platform}:{item.record.source_id}:{item.direction}"
        topic_marker = f"video-learning:auto-topic:{item.record.platform}:{item.record.source_id}:{item.direction}"
        if append_once(method_path, method_marker, formal_method_entry(item)):
            counts["methods"] += 1
        if append_once(topic_path, topic_marker, formal_topic_entry(item)):
            counts["topics"] += 1

    template_path = root / "10_Knowledge" / "formal" / "content_factory" / "内容生产模板_v1.md"
    signature = template_signature(high_items)
    if append_once(template_path, f"video-learning:auto-template:{signature}", formal_template_entry(high_items)):
        counts["templates"] += 1
    return counts


def account_card_markdown(account_name: str, platform: str, records: list[NormalizedRecord], rankings: dict[str, list[RankedRecord]]) -> str:
    account_records = [record for record in records if (record.account_name or "未知账号") == account_name and record.platform == platform]
    direction_rows = [
        row for row in account_direction_summary(account_records, limit=12)
        if row["account_name"] == account_name and row["platform"] == platform
    ]
    lines = [
        f"# 账号学习卡：{account_name} / {platform}",
        "",
        "## 数据概览",
        "",
        f"- 内容数：{len(account_records)}",
        f"- 点赞合计：{sum(record.metrics['likes'] for record in account_records)}",
        f"- 收藏合计：{sum(record.metrics['collects'] for record in account_records)}",
        f"- 评论合计：{sum(record.metrics['comments'] for record in account_records)}",
        f"- 转发合计：{sum(record.metrics['shares'] for record in account_records)}",
        "",
        "## 学习方向",
        "",
        "| 方向 | 内容数 | Top内容 | Top分数 |",
        "| --- | ---: | --- | ---: |",
    ]
    for row in direction_rows:
        lines.append(f"| {row['direction']} | {row['count']} | {row['top_title'].replace(chr(10), ' ')[:40]} | {row['top_score']} |")

    lines.extend(["", "## 账号内高表现样本", ""])
    top_records = sorted(account_records, key=heat_score, reverse=True)[:10]
    for index, record in enumerate(top_records, start=1):
        directions = "、".join(detect_directions(record))
        lines.append(f"{index}. `{record.source_id}` {record.title.replace(chr(10), ' ')[:80]}｜方向：{directions}｜分数：{heat_score(record)}")
    return "\n".join(lines) + "\n"


def write_account_cards(root: Path, records: list[NormalizedRecord], rankings: dict[str, list[RankedRecord]]) -> int:
    account_dir = account_cards_dir(root)
    account_dir.mkdir(parents=True, exist_ok=True)
    for old_card in account_dir.glob("*.md"):
        old_card.unlink()
    accounts = sorted({(record.account_name or "未知账号", record.platform) for record in records})
    for account_name, platform in accounts:
        path = account_dir / f"{safe_filename(account_name)}_{platform}.md"
        path.write_text(account_card_markdown(account_name, platform, records, rankings), encoding="utf-8")
    return len(accounts)


def write_candidate_subkb(root: Path, rankings: dict[str, list[RankedRecord]]) -> int:
    path = root / "10_Knowledge" / "candidates" / "sub_kbs" / "候选子库_视频深度学习方向.md"
    new_directions = sorted(direction for direction in rankings if direction not in KNOWN_DIRECTIONS and direction != "未归类")
    if not new_directions:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "# 候选子库：视频深度学习方向\n\n"
    for direction in new_directions:
        content += f"- {direction}: {len(rankings[direction])} 条候选内容，需要人工确认是否转正。\n"
    path.write_text(content, encoding="utf-8")
    return len(new_directions)


def write_outputs(
    root: Path,
    raw_counts: dict[str, int],
    dedupe_stats: dict[str, int],
    records: list[NormalizedRecord],
    rankings: dict[str, list[RankedRecord]],
    account_name: str,
    apply: bool,
    analyze_video: bool,
    video_limit: int,
    analyze_images: bool,
    image_limit: int,
    max_images_per_note: int,
    source_ids: set[str] | None,
) -> dict[str, Any]:
    output_dir = video_learning_dir(root)
    cards_dir = deep_cards_dir(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    cards_dir.mkdir(parents=True, exist_ok=True)
    for old_card in cards_dir.glob("*.md"):
        old_card.unlink()
    account_card_count = write_account_cards(root, records, rankings)

    high_items: list[RankedRecord] = []
    analyzed_videos = 0
    analyzed_images = 0
    video_statuses: dict[str, dict[str, Any]] = {}
    for ranked in rankings.values():
        for item in ranked:
            video_key = f"{item.record.platform}:{item.record.source_id}"
            should_analyze_video = (
                analyze_video
                and analyzed_videos < video_limit
                and can_attempt_record_video(item.record)
                and video_key not in video_statuses
                and (source_ids is None or item.record.source_id in source_ids)
            )
            should_analyze_images = (
                analyze_images
                and analyzed_images < image_limit
                and item.record.platform == "xhs"
                and bool(item.record.image_urls)
            )
            if should_analyze_video:
                analyzed_videos += 1
            if should_analyze_images:
                analyzed_images += 1
            if video_key not in video_statuses:
                video_statuses[video_key] = video_status(root, item.record, should_analyze_video)
            video = video_statuses[video_key]
            image = image_status(root, item.record, should_analyze_images, max_images_per_note=max_images_per_note)
            card_path = cards_dir / f"{safe_filename(item.direction)}_{item.record.platform}_{item.record.source_id}.md"
            card_path.write_text(card_markdown(item, video, image), encoding="utf-8")
            if high_confidence(item):
                high_items.append(item)

    initial_knowledge_outputs = write_initial_knowledge_outputs(root, account_name, records, raw_counts, dedupe_stats, rankings)

    ranking_json = {
        direction: [
            {
                "rank": item.rank,
                "platform": item.record.platform,
                "account_name": item.record.account_name,
                "source_id": item.record.source_id,
                "title": item.record.title,
                "score": item.score,
                "metrics": item.record.metrics,
                "url": item.record.url,
                "image_count": len(item.record.image_urls),
                "published_at": item.record.published_at,
                "primary_direction": first_non_unknown(detect_directions(item.record)),
                "topic_angle": candidate_topic_angle(item.direction, item.record),
                "content_format": candidate_content_format(item.record),
            }
            for item in ranked
        ]
        for direction, ranked in rankings.items()
    }
    (output_dir / "latest_direction_rankings.json").write_text(
        json.dumps(ranking_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "latest_video_statuses.json").write_text(
        json.dumps(video_statuses, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = report_markdown(raw_counts, dedupe_stats, records, rankings, high_items, apply, analyze_video, analyze_images, account_name)
    (output_dir / "latest_scan_report.md").write_text(report, encoding="utf-8")

    formal_counts = {"methods": 0, "topics": 0, "templates": 0}
    candidate_count = 0
    if apply:
        formal_counts = write_formal_entries(root, high_items)
        candidate_count = write_candidate_subkb(root, rankings)

    return {
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "directions": len(rankings),
        "deep_cards": sum(len(items) for items in rankings.values()),
        "account_cards": account_card_count,
        "video_analysis_requested": analyzed_videos,
        "image_analysis_requested": analyzed_images,
        "high_confidence": len(high_items),
        "formal_counts": formal_counts,
        "candidate_subkb_directions": candidate_count,
        "initial_knowledge": initial_knowledge_outputs,
        "report": str((output_dir / "latest_scan_report.md").relative_to(root)),
    }


def report_markdown(
    raw_counts: dict[str, int],
    dedupe_stats: dict[str, int],
    records: list[NormalizedRecord],
    rankings: dict[str, list[RankedRecord]],
    high_items: list[RankedRecord],
    apply: bool,
    analyze_video: bool,
    analyze_images: bool,
    account_name: str,
) -> str:
    lines = [
        "# 视频深度学习轻量扫描报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 数据盘点",
        "",
        f"- 抖音内容：{raw_counts.get('douyin_contents', 0)}",
        f"- 小红书内容：{raw_counts.get('xhs_contents', 0)}",
        f"- 抖音评论：{raw_counts.get('douyin_comments', 0)}",
        f"- 创作者：{raw_counts.get('creators', 0)}",
        f"- 账号过滤：{account_name or '未启用'}",
        f"- 输出内容数：{len(records)}",
        f"- 全库去重后内容：{dedupe_stats.get('unique_records', len(records))}",
        f"- ID 重复：{dedupe_stats.get('duplicate_source_id', 0)}",
        f"- 文本重复：{dedupe_stats.get('duplicate_text', 0)}",
        "",
        "## 账号统计",
        "",
        "| 账号 | 平台 | 内容数 | 点赞合计 | 收藏合计 | 评论合计 | 转发合计 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in account_summary(records):
        lines.append(
            f"| {row['account_name']} | {row['platform']} | {row['count']} | "
            f"{row['likes_sum']} | {row['collects_sum']} | {row['comments_sum']} | {row['shares_sum']} |"
        )
    lines.extend([
        "",
        "## 账号方向",
        "",
        "| 账号 | 平台 | 方向 | 内容数 | Top内容 | Top分数 |",
        "| --- | --- | --- | ---: | --- | ---: |",
    ])
    for row in account_direction_summary(records):
        lines.append(
            f"| {row['account_name']} | {row['platform']} | {row['direction']} | {row['count']} | "
            f"{row['top_title'].replace(chr(10), ' ')[:40]} | {row['top_score']} |"
        )
    lines.extend([
        "",
        "## 运行模式",
        "",
        f"- 自动写入正式库：{'是' if apply else '否'}",
        f"- 视频分析：{'尝试启用' if analyze_video else '未启用'}",
        f"- 图片分析：{'尝试启用' if analyze_images else '未启用'}",
        "",
        "## 方向统计",
        "",
        "| 方向 | Top数量 | Top1 | Top1分数 |",
        "| --- | ---: | --- | ---: |",
    ])
    for direction, ranked in rankings.items():
        top = ranked[0] if ranked else None
        title = top.record.title.replace("\n", " ")[:40] if top else ""
        score = top.score if top else 0
        lines.append(f"| {direction} | {len(ranked)} | {title} | {score} |")

    lines.extend(["", "## 高置信自动入库候选", ""])
    if high_items:
        for item in high_items:
            lines.append(f"- {item.direction} / {item.record.platform}:{item.record.source_id} / Top{item.rank} / score={item.score}")
    else:
        lines.append("- 本次没有满足自动入库条件的内容。")
    return "\n".join(lines) + "\n"


def video_learning_dir(root: Path) -> Path:
    return root / VIDEO_LEARNING_REPORTS_DIR


def deep_cards_dir(root: Path) -> Path:
    return root / CANDIDATE_LEARNING_DIR / "deep_cards"


def selected_deep_cards_dir(root: Path) -> Path:
    return root / CANDIDATE_LEARNING_DIR / "selected_deep_cards"


def account_cards_dir(root: Path) -> Path:
    return root / CANDIDATE_ACCOUNT_ASSETS_DIR / "account_cards"


def video_artifacts_dir(root: Path) -> Path:
    return root / VIDEO_LEARNING_CACHE_DIR / "video_artifacts"


def path_for_report(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def artifact_account_name(record: NormalizedRecord) -> str:
    return record.account_name or record.author_name or "unknown_account"


def resolved_video_artifacts_root(root: Path, artifacts_dir: Path | None = None) -> Path:
    return artifacts_dir if artifacts_dir is not None else video_artifacts_dir(root)


def resolved_video_artifact_dir(
    root: Path,
    record: NormalizedRecord,
    artifacts_dir: Path | None = None,
    artifact_layout: str = "flat",
) -> Path:
    base = resolved_video_artifacts_root(root, artifacts_dir)
    if artifact_layout == "account":
        base = base / artifact_account_name(record)
    return base / f"{record.platform}_{record.source_id}"


def image_artifacts_dir(root: Path) -> Path:
    return root / VIDEO_LEARNING_CACHE_DIR / "image_artifacts"


def record_key(record: NormalizedRecord) -> str:
    return f"{record.platform}:{record.source_id}"


def load_unique_records(root: Path) -> tuple[list[NormalizedRecord], dict[str, int], dict[str, int]]:
    records, raw_counts, _ = load_records_detailed(root)
    unique_records, dedupe_stats = deduplicate_records(records)
    return unique_records, raw_counts, dedupe_stats


def load_unique_records_detailed(
    root: Path,
) -> tuple[list[NormalizedRecord], dict[str, int], dict[str, int], list[dict[str, str]]]:
    records, raw_counts, failed_files = load_records_detailed(root)
    unique_records, dedupe_stats = deduplicate_records(records)
    return unique_records, raw_counts, dedupe_stats, failed_files


def records_by_source_id(records: list[NormalizedRecord]) -> dict[str, NormalizedRecord]:
    return {record.source_id: record for record in records if record.source_id}


def read_json_file(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def queue_path(root: Path) -> Path:
    return root / VIDEO_LEARNING_QUEUE_DIR / "pending_deep_learning.json"


def manifest_path(root: Path) -> Path:
    return root / VIDEO_LEARNING_STATE_DIR / "learning_manifest.json"


def load_queue(root: Path) -> dict[str, Any]:
    queue = read_json_file(queue_path(root), {"items": []})
    if not isinstance(queue, dict):
        return {"items": []}
    queue.setdefault("items", [])
    return queue


def save_queue(root: Path, queue: dict[str, Any]) -> None:
    queue["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json_file(queue_path(root), queue)


def load_manifest(root: Path) -> dict[str, Any]:
    manifest = read_json_file(manifest_path(root), {"items": {}})
    if not isinstance(manifest, dict):
        return {"items": {}}
    manifest.setdefault("items", {})
    return manifest


def save_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = datetime.now().isoformat(timespec="seconds")
    write_json_file(manifest_path(root), manifest)


def transcript_excerpt_from_status(root: Path, video: dict[str, Any], limit: int = 220) -> str:
    transcript_path = str((video.get("artifacts") or {}).get("transcript_json") or "")
    if not transcript_path:
        return ""
    path = Path(transcript_path)
    if not path.is_absolute():
        path = root / path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return ""
    text = " ".join(str(item.get("text") or "").strip() for item in payload.get("segments", []) if str(item.get("text") or "").strip())
    return first_sentence(text, limit)


def selected_card_markdown(
    record: NormalizedRecord,
    directions: list[str],
    video: dict[str, Any],
    image: dict[str, Any],
    transcript_excerpt: str = "",
) -> str:
    metrics = record.metrics
    direction_text = "、".join(directions)
    topic_tags = "、".join(record.tags) if record.tags else "未提取到显式话题/标签；按标题与正文语义学习。"
    direction = directions[0] if directions else "未归类"
    story_directions = {
        "剧情短剧", "喜剧反转", "校园大学生", "职场关系", "情感关系", "人际社交观察",
        "爱情关系喜剧", "性格标签喜剧", "生活荒诞反转", "身份错位短剧", "语言表达喜剧",
    }
    content_form = "图文" if record.platform == "xhs" else ("剧情/故事" if any(item in story_directions for item in directions) else "知识/评论")
    source_quote = transcript_excerpt or first_sentence(record.body, 180) or "无可回查原句；当前仅保留标题和媒体状态，不补造原话"
    content_summary = first_sentence(transcript_excerpt or record.body, 180) or first_sentence(record.title, 100)
    structure_template = reusable_template(direction, record)
    if content_form == "剧情/故事":
        structure = (
            f"- 开头设定：{golden_3s_hook(record)}\n"
            f"- 核心冲突：{content_summary}\n"
            "- 升级：通过人物动作、限制条件或信息差持续放大冲突。\n"
            f"- 转折或笑点：{ending_quote_or_interaction(record)}\n"
            "- 收尾：停在关系变化或结果反转，不额外拔高。"
        )
    elif content_form == "图文":
        structure = (
            f"- 封面承诺：{golden_3s_hook(record)}\n"
            "- 分图顺序：封面、问题、步骤、结果、边界。\n"
            f"- 信息层级：{content_summary}\n"
            f"- 行动建议：{structure_template}\n"
            f"- 收尾互动：{ending_quote_or_interaction(record)}"
        )
    else:
        structure = (
            f"- 黄金3秒：{golden_3s_hook(record)}\n"
            f"- 观点提出：{first_sentence(record.title, 100)}\n"
            f"- 证据或案例：{content_summary}\n"
            f"- 推演：{structure_template}\n"
            f"- 收尾：{ending_quote_or_interaction(record)}"
        )
    media_type = "图文" if record.platform == "xhs" else "视频"
    media_status = f"video={video.get('status', 'unknown')}；image={image.get('status', 'unknown')}"
    candidate_status = "待验证；单卡不得直接形成稳定方法"
    evidence_gap = "逐字稿/正文不足，当前观点仅按可见发布层学习。" if not transcript_excerpt and not record.body else "仍需至少一张独立内容支持，才能通过跨卡验证。"
    return f"""# 已确认深度学习卡：{record.platform} {record.source_id}

学习卡契约：{CONTRACT_ID}
source_id：{record.source_id}
原内容链接：{record.url}
账号：{record.account_name or "未知账号"}
平台：{record.platform}
主方向：{direction_text}
学习批次：video-learning-manifest
状态：candidate_learned

## 1. 证据边界

- 主证据：{('逐字稿、原视频' if transcript_excerpt else '发布标题、正文/文案和可用媒体产物')}。
- 辅助证据：指标、话题/标签、图片/OCR和场景状态。
- 证据状态：{media_status}；逐字稿摘录 {'可用' if transcript_excerpt else '缺失或未读取'}。

## 2. 为什么值得学习

- 本条由用户或计划确认进入深度学习队列，方向为 `{direction_text}`。
- 指标证据：点赞 {metrics['likes']}，收藏 {metrics['collects']}，评论 {metrics['comments']}，转发 {metrics['shares']}；指标只作辅助。
- 可学习价值：标题、正文和媒体表现共同承载“{candidate_topic_angle(direction, record)}”。

## 3. 多维分类与商业隔离

- 内容形态：{content_form}
- 平台形态：{candidate_content_format(record)}
- 商业属性：待复核
- 分类依据：标题、正文、标签和媒体状态共同判断为 `{direction_text}`。
- 隔离判断：商业信号尚未完成独立审核，本卡不能直接进入稳定方法或核心方向统计。

## 4. 核心观点

- 内容层观点：{content_summary}
- 表达层观点：{golden_3s_hook(record)}
- 复用判断：{candidate_topic_angle(direction, record)}。

## 5. 内容结构

{structure}

## 6. 发布内容层学习

- 标题：{record.title}
- 正文或文案：{first_sentence(record.body, 180) or '未提取到有效正文/文案。'}
- 话题或标签：{topic_tags}
- 协同判断：标题负责承诺，正文/文案负责展开，话题/标签负责限定场景；缺失项不补造。

## 7. 视频/图文表现层学习

- 媒体类型：{media_type}。
- 分析状态：{media_status}。
- 表现学习：{('按封面、分图、OCR和视觉层级学习' if record.platform == 'xhs' else '按逐字稿、镜头、场景、节奏和停顿学习')}；未完成的媒体分析只保留降级判断。

## 8. 金句与表达素材

- 原文金句：{source_quote}
- 提炼表达（非原话）：{content_summary}
- 可复用句式：{structure_template}

## 9. 可复用选题与案例

- 可复用选题：{candidate_topic_angle(direction, record)}。
- 可复用案例：{record.platform}:{record.source_id}，标题《{record.title}》。
- 复用边界：只复用结构，不复制来源事实、身份、故事和原句。

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。

### R - 原始证据

{source_quote}

### I - 初步解释

本条候选尝试用“{structure_template}”把 `{direction_text}` 转成可识别、可执行的内容结构。

### A1 - 本条案例

{record.platform}:{record.source_id} 以《{record.title}》承载该结构。

### A2 - 未来触发场景

- 触发机制：当新任务需要复用“{structure_template}”的结构因果，而不只是复用 `{direction}` 题材词时调用本候选。
- 适用关系：来源人物关系只作为本条案例；目标关系能够承载同类冲突时可以迁移。
- 可迁移场景：来源场景只作为本条案例；更换场景后核心结构仍成立时可以迁移。
- 不触发条件：只出现来源人物、场景、道具或 `{direction}` 题材词，但没有同类结构因果时不得调用。

### E - 初步执行步骤

1. 先按账号、内容形态和主任务方向建立基础召回范围。
2. 再按结构机制判断是否跨关系、跨场景调用，不因偶然名词触发。
3. 把来源人物和场景替换为目标人物和目标场景，同时保留核心因果。
4. 对齐标题、正文/文案、话题和媒体表现。
5. 回查证据并标出不能确定的部分。

### B - 边界与反例

- {candidate_status}。
- 商业属性未复核时，不进入核心方向规律。

## 11. 可复用模板

```text
路由：先确定【主任务方向】和【内容形态】，再匹配【核心结构机制】。
触发检查：只命中人物、场景、道具或题材词时不调用。
{structure_template}
替换【受众】【人物关系】【场景】【问题】【动作】【边界】，不复制来源事实和原句。
```

## 12. 证据缺口与候选判断

- 证据缺口：{evidence_gap}
- 卡片判断：保留为候选学习卡，等待机器审计和人工复核。
- 跨卡状态：待验证；进入五视角候选池后再决定支持、反驳或边界证据。
"""


def queue_item(record: NormalizedRecord, priority: int = 100) -> dict[str, Any]:
    directions = detect_directions(record)
    return {
        "platform": record.platform,
        "source_id": record.source_id,
        "account_name": record.account_name or record.author_name,
        "title": record.title,
        "directions": directions,
        "priority": priority,
        "status": "pending",
        "queued_at": datetime.now().isoformat(timespec="seconds"),
    }


def select_deep_learning(
    root: Path,
    source_ids: set[str] | None = None,
    account_name: str = "",
    direction: str = "",
    top_n: int = 0,
) -> dict[str, Any]:
    records, raw_counts, dedupe_stats, failed_files = load_unique_records_detailed(root)
    by_id = records_by_source_id(records)
    selected: list[NormalizedRecord] = []
    missing: list[str] = []

    if source_ids:
        for source_id in sorted(source_ids):
            record = by_id.get(source_id)
            if record:
                selected.append(record)
            else:
                missing.append(source_id)
    else:
        candidates = records
        if account_name:
            candidates = [record for record in candidates if account_name in {record.account_name, record.author_name}]
        if direction:
            candidates = [record for record in candidates if direction in detect_directions(record)]
        candidates = sorted(candidates, key=heat_score, reverse=True)
        selected = candidates[: max(top_n, 0)] if top_n else candidates

    queue = load_queue(root)
    existing = {(item.get("platform"), item.get("source_id")): item for item in queue.get("items", [])}
    queued = 0
    for record in selected:
        key = (record.platform, record.source_id)
        item = queue_item(record)
        if key in existing:
            existing[key].update(item)
            if existing[key].get("status") not in {"completed", "failed"}:
                existing[key]["status"] = "pending"
        else:
            queue["items"].append(item)
            queued += 1
    save_queue(root, queue)

    return {
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
        "partial_success": bool(failed_files),
        "requested": len(source_ids or []),
        "selected": len(selected),
        "queued": queued,
        "missing": missing,
        "queue": str(queue_path(root).relative_to(root)),
    }


def selected_ids_from_queue(root: Path) -> set[str]:
    queue = load_queue(root)
    return {str(item.get("source_id")) for item in queue.get("items", []) if item.get("status") == "pending" and item.get("source_id")}


def update_queue_status(root: Path, platform: str, source_id: str, status: str) -> None:
    queue = load_queue(root)
    for item in queue.get("items", []):
        if item.get("platform") == platform and item.get("source_id") == source_id:
            item["status"] = status
            item["updated_at"] = datetime.now().isoformat(timespec="seconds")
    save_queue(root, queue)


def learning_outcome(video: dict[str, Any], image: dict[str, Any], analyze_video: bool, analyze_images: bool) -> str:
    failed_video = analyze_video and str(video.get("status", "")).startswith("degraded")
    failed_image = analyze_images and str(image.get("status", "")).startswith("degraded")
    return "failed" if failed_video or failed_image else "completed"


def selected_report_markdown(result: dict[str, Any], statuses: dict[str, dict[str, Any]], missing: list[str], skipped: list[str]) -> str:
    lines = [
        "# 已确认内容深度学习报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 汇总",
        "",
        f"- 请求数量：{result['requested']}",
        f"- 找到数量：{result['found']}",
        f"- 本次学习：{result['learned']}",
        f"- 跳过数量：{result['skipped']}",
        f"- 未找到数量：{len(missing)}",
        "",
        "## 状态明细",
        "",
        "| 内容ID | 状态 | 学习卡 | 逐字稿 | 失败原因 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for key, status in statuses.items():
        artifacts = status.get("video", {}).get("artifacts", {})
        transcript = artifacts.get("transcript_srt", "")
        errors = status.get("video", {}).get("errors", []) + status.get("image", {}).get("errors", [])
        current_step = status.get("current_step", "")
        display_status = f"{status.get('status', '')} / {current_step}" if current_step else status.get("status", "")
        lines.append(f"| {key} | {display_status} | {status.get('card_path', '')} | {transcript} | " f"{'; '.join(errors)[:120]} |")
    if missing:
        lines.extend(["", "## 未找到", ""])
        lines.extend(f"- {source_id}" for source_id in missing)
    if skipped:
        lines.extend(["", "## 已跳过", ""])
        lines.extend(f"- {source_id}" for source_id in skipped)
    append_source_failures(lines, result.get("failed_files", []))
    return "\n".join(lines) + "\n"


def download_report_markdown(result: dict[str, Any], statuses: dict[str, dict[str, Any]], missing: list[str]) -> str:
    lines = [
        "# 视频批次下载报告",
        "",
        f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 汇总",
        "",
        f"- 请求数量：{result['requested']}",
        f"- 找到数量：{result['found']}",
        f"- 下载完成：{result['downloaded']}",
        f"- 复用本地文件：{result['reused']}",
        f"- 失败数量：{result['failed']}",
        f"- 未找到数量：{len(missing)}",
        "",
        "## 状态明细",
        "",
        "| 内容ID | 状态 | 本地文件 | 失败原因 |",
        "| --- | --- | --- | --- |",
    ]
    for key, item in statuses.items():
        errors = "; ".join(item.get("errors", []))[:120]
        current_step = item.get("current_step", "")
        display_status = f"{item.get('status', '')} / {current_step}" if current_step else item.get("status", "")
        lines.append(f"| {key} | {display_status} | {item.get('video_path', '')} | {errors} |")
    if missing:
        lines.extend(["", "## 未找到", ""])
        lines.extend(f"- {source_id}" for source_id in missing)
    append_source_failures(lines, result.get("failed_files", []))
    return "\n".join(lines) + "\n"


def append_source_failures(lines: list[str], failed_files: list[dict[str, str]]) -> None:
    if not failed_files:
        return
    lines.extend(
        [
            "",
            "## 原始文件读取失败",
            "",
            "| 文件 | 阶段 | 错误类型 | 错误摘要 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for failure in failed_files:
        message = str(failure.get("message", "")).replace("\n", " ")[:160]
        lines.append(
            f"| {failure.get('path', '')} | {failure.get('stage', '')} | "
            f"{failure.get('error_type', '')} | {message} |"
        )


def account_artifact_dir_from_base(artifacts_dir: Path, account_name: str) -> Path:
    return artifacts_dir / (account_name or "unknown_account")


def artifact_bundle_status(artifact_dir: Path) -> dict[str, Any]:
    transcript_files = [artifact_dir / "transcript.srt", artifact_dir / "transcript.json"]
    keyframes = sorted(artifact_dir.glob("*.jpg")) + sorted(artifact_dir.glob("*.png"))
    keyframes_dir = artifact_dir / "keyframes"
    if keyframes_dir.is_dir():
        keyframes.extend(sorted(keyframes_dir.glob("*.jpg")) + sorted(keyframes_dir.glob("*.png")))
    scenes = sorted(artifact_dir.glob("*Scenes.csv")) + sorted(artifact_dir.glob("scenes.csv"))
    return {
        "artifact_dir": str(artifact_dir),
        "has_video": (artifact_dir / "source.mp4").is_file(),
        "has_audio": (artifact_dir / "audio.wav").is_file(),
        "has_metadata": (artifact_dir / "ffprobe.json").is_file(),
        "has_transcript": any(path.is_file() and path.stat().st_size > 0 for path in transcript_files),
        "has_keyframes": any(path.is_file() and path.stat().st_size > 0 for path in keyframes),
        "has_scenes": any(path.is_file() and path.stat().st_size > 0 for path in scenes),
    }


def infer_platform_source_from_artifact_dir(path: Path) -> tuple[str, str]:
    name = path.name
    if "_" not in name:
        return "", name
    platform, source_id = name.split("_", 1)
    return platform, source_id


def scan_account_artifacts(account_dir: Path) -> dict[str, dict[str, Any]]:
    items: dict[str, dict[str, Any]] = {}
    if not account_dir.is_dir():
        return items
    for artifact_dir in sorted(path for path in account_dir.iterdir() if path.is_dir() and not path.name.startswith("_")):
        platform, source_id = infer_platform_source_from_artifact_dir(artifact_dir)
        if not source_id:
            continue
        key = f"{platform}:{source_id}" if platform else source_id
        items[key] = {
            "platform": platform,
            "source_id": source_id,
            **artifact_bundle_status(artifact_dir),
        }
    return items


def pipeline_current_step(artifact_dir: Path) -> str:
    state = load_pipeline_state(artifact_dir)
    return str(state.get("current_step") or "pending")


def nas_mirror_report(account_name: str, plan: dict[str, Any], progress: dict[str, Any], artifact_index: dict[str, Any]) -> str:
    planned = len(plan.get("items", {}))
    progressed = len(progress.get("items", {}))
    indexed = len(artifact_index.get("items", {}))
    lines = [
        f"# NAS 学习进度：{account_name}",
        "",
        f"更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 汇总",
        "",
        f"- 计划条数：{planned}",
        f"- 有进度条数：{progressed}",
        f"- 产物索引条数：{indexed}",
        "",
        "## 最近进度",
        "",
        "| 内容ID | 状态 | 当前步骤 | 产物目录 |",
        "| --- | --- | --- | --- |",
    ]
    for key, item in sorted(progress.get("items", {}).items()):
        lines.append(f"| {key} | {item.get('status', '')} | {item.get('current_step', '')} | {item.get('artifact_dir', '')} |")
    return "\n".join(lines) + "\n"


def write_nas_account_mirror(
    account_dir: Path,
    account_name: str,
    planned_records: list[NormalizedRecord],
    statuses: dict[str, dict[str, Any]] | None = None,
) -> dict[str, str]:
    account_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().isoformat(timespec="seconds")
    artifact_items = scan_account_artifacts(account_dir)

    existing_plan_items = read_json_file(account_dir / "_learning_plan.json", {"items": {}}).get("items", {})
    plan_items: dict[str, dict[str, Any]] = dict(existing_plan_items) if isinstance(existing_plan_items, dict) else {}
    progress_items = read_json_file(account_dir / "_learning_progress.json", {"items": {}}).get("items", {})
    if not isinstance(progress_items, dict):
        progress_items = {}
    statuses = statuses or {}

    for record in planned_records:
        key = record_key(record)
        artifact_dir = account_dir / f"{record.platform}_{record.source_id}"
        artifact_items[key] = {
            "platform": record.platform,
            "source_id": record.source_id,
            **artifact_bundle_status(artifact_dir),
        }
        plan_items[key] = {
            "platform": record.platform,
            "source_id": record.source_id,
            "account_name": record.account_name or record.author_name,
            "title": record.title,
            "artifact_dir": str(artifact_dir),
            "planned_at": now,
        }
        status = statuses.get(key)
        if status:
            video = status.get("video", {})
            progress_items[key] = {
                "platform": record.platform,
                "source_id": record.source_id,
                "account_name": record.account_name or record.author_name,
                "title": record.title,
                "status": status.get("status", ""),
                "current_step": pipeline_current_step(artifact_dir),
                "video_status": video.get("status", ""),
                "card_path": status.get("card_path", ""),
                "artifact_dir": str(artifact_dir),
                "updated_at": now,
            }
        else:
            progress_items.setdefault(
                key,
                {
                    "platform": record.platform,
                    "source_id": record.source_id,
                    "account_name": record.account_name or record.author_name,
                    "title": record.title,
                    "status": "planned",
                    "current_step": pipeline_current_step(artifact_dir),
                    "artifact_dir": str(artifact_dir),
                    "updated_at": now,
                },
            )

    plan = {"account_name": account_name, "updated_at": now, "items": plan_items}
    progress = {"account_name": account_name, "updated_at": now, "items": progress_items}
    artifact_index = {"account_name": account_name, "updated_at": now, "items": artifact_items}

    plan_path = account_dir / "_learning_plan.json"
    progress_path = account_dir / "_learning_progress.json"
    index_path = account_dir / "_artifact_index.json"
    report_path = account_dir / "_latest_report.md"
    write_json_file(plan_path, plan)
    write_json_file(progress_path, progress)
    write_json_file(index_path, artifact_index)
    report_path.write_text(nas_mirror_report(account_name, plan, progress, artifact_index), encoding="utf-8")
    return {
        "plan": str(plan_path),
        "progress": str(progress_path),
        "artifact_index": str(index_path),
        "report": str(report_path),
    }


def run_selected_deep_learning(
    root: Path,
    source_ids: set[str] | None = None,
    analyze_video: bool = False,
    video_limit: int = 1,
    analyze_images: bool = False,
    max_images_per_note: int = 18,
    force: bool = False,
    artifacts_dir: Path | None = None,
    artifact_layout: str = "flat",
    account_name: str = "",
    mirror_nas_state: bool = False,
) -> dict[str, Any]:
    records, raw_counts, dedupe_stats, failed_files = load_unique_records_detailed(root)
    by_id = records_by_source_id(records)
    requested_ids = source_ids or selected_ids_from_queue(root)
    if not requested_ids and account_name:
        requested_ids = {
            record.source_id
            for record in records
            if record.source_id and account_name in {record.account_name, record.author_name}
        }
    if not requested_ids and artifacts_dir is not None and artifact_layout == "account" and account_name:
        account_dir = account_artifact_dir_from_base(artifacts_dir, account_name)
        requested_ids = {str(item.get("source_id")) for item in scan_account_artifacts(account_dir).values() if item.get("source_id")}
    output_dir = video_learning_dir(root)
    cards_dir = selected_deep_cards_dir(root)
    cards_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(root)
    manifest_items = manifest.setdefault("items", {})
    statuses: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    skipped: list[str] = []
    planned_records: list[NormalizedRecord] = []
    learned = 0
    analyzed_videos = 0

    for source_id in sorted(requested_ids):
        record = by_id.get(source_id)
        if not record:
            missing.append(source_id)
            continue
        planned_records.append(record)
        key = record_key(record)
        existing = manifest_items.get(key, {})
        card_validation = validate_learning_card(root, existing)
        if existing.get("status") == "completed" and card_validation["validation"] == "valid" and not force:
            skipped.append(source_id)
            continue
        artifact_dir = resolved_video_artifact_dir(root, record, artifacts_dir, artifact_layout)
        local_video_available = media_file_is_usable(artifact_dir / "source.mp4")
        should_analyze_video = (
            analyze_video
            and analyzed_videos < video_limit
            and (can_attempt_record_video(record) or local_video_available)
        )
        if should_analyze_video:
            analyzed_videos += 1
        if artifacts_dir is None and artifact_layout == "flat":
            video = video_status(root, record, should_analyze_video)
        else:
            video = video_status(root, record, should_analyze_video, artifacts_dir=artifacts_dir, artifact_layout=artifact_layout)
        image = image_status(root, record, analyze_images and record.platform == "xhs", max_images_per_note=max_images_per_note)
        directions = detect_directions(record)
        card_path = cards_dir / f"{record.platform}_{record.source_id}.md"
        pipeline_state = load_pipeline_state(artifact_dir, record)
        mark_pipeline_step(artifact_dir, pipeline_state, "write_card", "running")
        transcript_excerpt = transcript_excerpt_from_status(root, video)
        card_text = selected_card_markdown(record, directions, video, image, transcript_excerpt)
        card_contract = validate_unified_text(card_text)
        card_path.write_text(card_text, encoding="utf-8")
        status = learning_outcome(video, image, analyze_video, analyze_images)
        if not card_contract.valid:
            status = "card_contract_failed"
        if status == "completed":
            mark_pipeline_step(artifact_dir, pipeline_state, "write_card", "completed", "valid")
            pipeline_state["current_step"] = "completed"
            save_pipeline_state(artifact_dir, pipeline_state)
        else:
            mark_pipeline_step(artifact_dir, pipeline_state, "write_card", "failed", "corrupt", "learning_outcome_failed")
        entry = {
            "platform": record.platform,
            "source_id": record.source_id,
            "account_name": record.account_name or record.author_name,
            "title": record.title,
            "directions": directions,
            "status": status,
            "current_step": pipeline_current_step(artifact_dir),
            "card_path": str(card_path.relative_to(root)),
            "video": video,
            "image": image,
            "card_contract": {
                "contract_id": CONTRACT_ID,
                "valid": card_contract.valid,
                "errors": list(card_contract.errors),
            },
            "last_run_at": datetime.now().isoformat(timespec="seconds"),
        }
        manifest_items[key] = entry
        statuses[key] = entry
        update_queue_status(root, record.platform, record.source_id, status)
        learned += 1

    save_manifest(root, manifest)
    nas_mirror: dict[str, str] = {}
    if mirror_nas_state and artifacts_dir is not None and artifact_layout == "account":
        mirror_account_name = account_name or (planned_records[0].account_name or planned_records[0].author_name if planned_records else "")
        if mirror_account_name:
            nas_mirror = write_nas_account_mirror(
                account_artifact_dir_from_base(artifacts_dir, mirror_account_name),
                mirror_account_name,
                planned_records,
                statuses,
            )
    result = {
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
        "partial_success": bool(failed_files),
        "requested": len(requested_ids),
        "found": len(requested_ids) - len(missing),
        "learned": learned,
        "skipped": len(skipped),
        "missing": missing,
        "video_analysis_requested": analyzed_videos,
        "selected_cards_dir": str(cards_dir.relative_to(root)),
        "manifest": str(manifest_path(root).relative_to(root)),
        "report": str((output_dir / "latest_selected_deep_learning_report.md").relative_to(root)),
        "nas_mirror": nas_mirror,
    }
    write_json_file(output_dir / "latest_selected_video_statuses.json", statuses)
    (output_dir / "latest_selected_deep_learning_report.md").write_text(
        selected_report_markdown(result, statuses, missing, skipped),
        encoding="utf-8",
    )
    return result


def download_selected_media(
    root: Path,
    source_ids: set[str] | None = None,
    artifacts_dir: Path | None = None,
    artifact_layout: str = "flat",
    account_name: str = "",
    mirror_nas_state: bool = False,
    direct_video_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    requested_ids = source_ids or selected_ids_from_queue(root)
    records, raw_counts, dedupe_stats, failed_files = load_unique_records_detailed(root)
    by_id = records_by_source_id(records)
    if not requested_ids and account_name:
        requested_ids = {
            record.source_id
            for record in records
            if record.source_id and account_name in {record.account_name, record.author_name}
        }
    output_dir = video_learning_dir(root)
    statuses: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    planned_records: list[NormalizedRecord] = []
    downloaded = 0
    reused = 0
    failed = 0
    direct_video_urls = direct_video_urls or {}

    for source_id in sorted(requested_ids):
        record = by_id.get(source_id)
        if not record:
            missing.append(source_id)
            continue
        planned_records.append(record)
        artifact_dir = resolved_video_artifact_dir(root, record, artifacts_dir, artifact_layout)
        video_path = artifact_dir / "source.mp4"
        pipeline_state = load_pipeline_state(artifact_dir, record)
        entry = {
            "platform": record.platform,
            "source_id": record.source_id,
            "account_name": record.account_name or record.author_name,
            "title": record.title,
            "video_path": path_for_report(video_path, root),
            "status": "pending",
            "warnings": [],
            "errors": [],
        }
        if direct_video_urls.get(source_id):
            download_url = direct_video_urls[source_id]
            resolve_warnings = ["using_direct_video_url_override"]
        else:
            try:
                download_url, resolve_warnings = resolved_record_video_url(record)
            except Exception as exc:
                entry["errors"].append(f"xhs_video_url_resolve_failed: {exc}")
                entry["status"] = "missing_video_url"
                failed += 1
                statuses[source_id] = entry
                continue
        if not download_url:
            entry["status"] = "missing_video_url"
            failed += 1
            statuses[source_id] = entry
            continue
        try:
            video_validation = validate_video_artifact(video_path)
            if video_validation["validation"] != "valid":
                mark_pipeline_step(
                    artifact_dir,
                    pipeline_state,
                    "download",
                    "running",
                    video_validation["validation"],
                    video_validation["reason"],
                )
            warnings = ensure_video_file(
                download_url,
                video_path,
                force_download=video_validation["validation"] in {"corrupt", "partial", "stale"},
            )
            video_validation = validate_video_artifact(video_path)
            if video_validation["validation"] != "valid":
                mark_pipeline_step(
                    artifact_dir,
                    pipeline_state,
                    "download",
                    "failed",
                    video_validation["validation"],
                    video_validation["reason"],
                )
                raise RuntimeError(f"video_validation_failed: {video_validation['reason']}")
            mark_pipeline_step(artifact_dir, pipeline_state, "download", "completed", "valid")
            entry["warnings"] = resolve_warnings + warnings
            if warnings and warnings[0] == "using_existing_video_file":
                entry["status"] = "reused_local_file"
                reused += 1
            else:
                entry["status"] = "downloaded"
                downloaded += 1
            entry["current_step"] = pipeline_current_step(artifact_dir)
        except Exception as exc:
            entry["status"] = "failed"
            entry["errors"].append(str(exc))
            failed += 1
            entry["current_step"] = pipeline_current_step(artifact_dir)
        statuses[source_id] = entry

    nas_mirror: dict[str, str] = {}
    if mirror_nas_state and artifacts_dir is not None and artifact_layout == "account":
        mirror_account_name = account_name or (planned_records[0].account_name or planned_records[0].author_name if planned_records else "")
        if mirror_account_name:
            status_by_key = {f"{item.get('platform')}:{source_id}": {"status": item.get("status"), "video": {}} for source_id, item in statuses.items()}
            nas_mirror = write_nas_account_mirror(
                account_artifact_dir_from_base(artifacts_dir, mirror_account_name),
                mirror_account_name,
                planned_records,
                status_by_key,
            )

    result = {
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
        "partial_success": bool(failed_files),
        "requested": len(requested_ids),
        "found": len(requested_ids) - len(missing),
        "downloaded": downloaded,
        "reused": reused,
        "failed": failed,
        "missing": missing,
        "video_artifacts_dir": path_for_report(resolved_video_artifacts_root(root, artifacts_dir), root),
        "report": str((output_dir / "latest_video_download_report.md").relative_to(root)),
        "nas_mirror": nas_mirror,
    }
    write_json_file(output_dir / "latest_video_download_statuses.json", statuses)
    (output_dir / "latest_video_download_report.md").write_text(
        download_report_markdown(result, statuses, missing),
        encoding="utf-8",
    )
    result["downloaded_files"] = [item["video_path"] for item in statuses.values() if item.get("status") in {"downloaded", "reused_local_file"}]
    return result


def generate_nas_account_index(root: Path, artifacts_dir: Path, account_name: str) -> dict[str, Any]:
    records, raw_counts, dedupe_stats, failed_files = load_unique_records_detailed(root)
    planned_records = [
        record
        for record in records
        if account_name in {record.account_name, record.author_name}
    ]
    account_dir = account_artifact_dir_from_base(artifacts_dir, account_name)
    mirror = write_nas_account_mirror(account_dir, account_name, planned_records, {})
    artifact_index = read_json_file(account_dir / "_artifact_index.json", {"items": {}})
    return {
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "failed_files": failed_files,
        "partial_success": bool(failed_files),
        "account_name": account_name,
        "account_dir": str(account_dir),
        "planned_records": len(planned_records),
        "indexed_artifacts": len(artifact_index.get("items", {})),
        "nas_mirror": mirror,
    }


def learning_status(root: Path) -> dict[str, Any]:
    queue = load_queue(root)
    manifest = load_manifest(root)
    queue_items = queue.get("items", [])
    manifest_items = manifest.get("items", {})
    return {
        "queue_pending": sum(1 for item in queue_items if item.get("status") == "pending"),
        "queue_completed": sum(1 for item in queue_items if item.get("status") == "completed"),
        "queue_failed": sum(1 for item in queue_items if item.get("status") == "failed"),
        "manifest_completed": sum(1 for item in manifest_items.values() if item.get("status") == "completed"),
        "manifest_failed": sum(1 for item in manifest_items.values() if item.get("status") == "failed"),
        "queue": str(queue_path(root).relative_to(root)),
        "manifest": str(manifest_path(root).relative_to(root)),
    }


def run_pipeline(
    root: Path,
    apply: bool = False,
    analyze_video: bool = False,
    video_limit: int = 1,
    analyze_images: bool = False,
    image_limit: int = 1,
    max_images_per_note: int = 18,
    account_name: str = "",
    source_ids: set[str] | None = None,
) -> dict[str, Any]:
    records, raw_counts = load_records(root)
    unique_records, dedupe_stats = deduplicate_records(records)
    if account_name:
        unique_records = [record for record in unique_records if account_name in {record.account_name, record.author_name}]
    rankings = build_direction_rankings(unique_records)
    return write_outputs(
        root,
        raw_counts,
        dedupe_stats,
        unique_records,
        rankings,
        account_name,
        apply,
        analyze_video,
        video_limit,
        analyze_images,
        image_limit,
        max_images_per_note,
        source_ids,
    )


def check_env() -> dict[str, Any]:
    env = {
        "python": sys.executable,
        "ffmpeg": find_executable("ffmpeg"),
        "ffprobe": find_executable("ffprobe"),
        "tesseract": find_executable("tesseract"),
        "faster_whisper": False,
        "scenedetect": False,
        "pillow": False,
        "pytesseract": False,
    }
    try:
        import faster_whisper  # type: ignore # noqa: F401

        env["faster_whisper"] = True
    except Exception:
        env["faster_whisper"] = False
    try:
        import scenedetect  # type: ignore # noqa: F401

        env["scenedetect"] = True
    except Exception:
        env["scenedetect"] = False
    try:
        import PIL  # type: ignore # noqa: F401

        env["pillow"] = True
    except Exception:
        env["pillow"] = False
    try:
        import pytesseract  # type: ignore # noqa: F401

        env["pytesseract"] = True
    except Exception:
        env["pytesseract"] = False
    return env


def parse_source_ids(value: str) -> set[str] | None:
    return {item.strip() for item in value.split(",") if item.strip()} or None


class MacSleepGuard:
    """Keep long video jobs awake on macOS while downloads or analysis run."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.proc: subprocess.Popen[Any] | None = None

    def __enter__(self) -> "MacSleepGuard":
        if not self.enabled or sys.platform != "darwin" or not shutil.which("caffeinate"):
            return self
        self.proc = subprocess.Popen(
            ["caffeinate", "-dimsu", "-w", str(os.getpid())],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()


def should_prevent_sleep(args: argparse.Namespace) -> bool:
    command = getattr(args, "command", "")
    if command == "download":
        return True
    if command in {"scan", "learn"} and bool(getattr(args, "analyze_video", False)):
        return True
    return not command and bool(getattr(args, "analyze_video", False))


def parsed_artifacts_dir(value: str) -> Path | None:
    return Path(value).expanduser().resolve() if value else None


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"scan", "select", "learn", "download", "nas-index", "status"}:
        parser = argparse.ArgumentParser(description="Run video learning workflow for the knowledge base.")
        subparsers = parser.add_subparsers(dest="command", required=True)

        scan_parser = subparsers.add_parser("scan", help="Run full metadata scan and rankings")
        scan_parser.add_argument("--root", default=".", help="Knowledge base root")
        scan_parser.add_argument("--apply", action="store_true", help="Append high-confidence entries to formal knowledge files")
        scan_parser.add_argument("--analyze-video", action="store_true", help="Try video analysis during scan")
        scan_parser.add_argument("--video-limit", type=int, default=1, help="Maximum videos to analyze during scan")
        scan_parser.add_argument("--analyze-images", action="store_true", help="Try image analysis during scan")
        scan_parser.add_argument("--image-limit", type=int, default=1, help="Maximum image posts to analyze during scan")
        scan_parser.add_argument("--max-images-per-note", type=int, default=18, help="Maximum images per post")
        scan_parser.add_argument("--account-name", default="", help="Exact account name filter for scan outputs")
        scan_parser.add_argument("--source-ids", default="", help="Comma-separated source IDs to target during scan video analysis")

        select_parser = subparsers.add_parser("select", help="Queue confirmed content for deep learning")
        select_parser.add_argument("--root", default=".", help="Knowledge base root")
        select_parser.add_argument("--source-ids", default="", help="Comma-separated source IDs to queue")
        select_parser.add_argument("--account-name", default="", help="Optional account name filter")
        select_parser.add_argument("--direction", default="", help="Optional direction filter")
        select_parser.add_argument("--top-n", type=int, default=0, help="Queue top N records after filters")

        learn_parser = subparsers.add_parser("learn", help="Deep learn only queued or selected content")
        learn_parser.add_argument("--root", default=".", help="Knowledge base root")
        learn_parser.add_argument("--source-ids", default="", help="Comma-separated source IDs to learn instead of queue")
        learn_parser.add_argument("--analyze-video", action="store_true", help="Try video download, transcription, and scene detection")
        learn_parser.add_argument("--video-limit", type=int, default=1, help="Maximum videos to analyze")
        learn_parser.add_argument("--analyze-images", action="store_true", help="Try XHS image download and OCR")
        learn_parser.add_argument("--max-images-per-note", type=int, default=18, help="Maximum images per post")
        learn_parser.add_argument("--force", action="store_true", help="Re-learn items already marked completed")
        learn_parser.add_argument("--artifacts-dir", default="", help="Optional external video artifacts root, such as a NAS folder")
        learn_parser.add_argument("--artifact-layout", choices=["flat", "account"], default="flat", help="Artifact directory layout")
        learn_parser.add_argument("--account-name", default="", help="Account folder/name for NAS account layout")
        learn_parser.add_argument("--mirror-nas-state", action="store_true", help="Mirror plan/progress/index files to the NAS account folder")

        download_parser = subparsers.add_parser("download", help="Download queued or selected content without deep learning")
        download_parser.add_argument("--root", default=".", help="Knowledge base root")
        download_parser.add_argument("--source-ids", default="", help="Comma-separated source IDs to download instead of queue")
        download_parser.add_argument("--artifacts-dir", default="", help="Optional external video artifacts root, such as a NAS folder")
        download_parser.add_argument("--artifact-layout", choices=["flat", "account"], default="flat", help="Artifact directory layout")
        download_parser.add_argument("--account-name", default="", help="Account folder/name for NAS account layout")
        download_parser.add_argument("--mirror-nas-state", action="store_true", help="Mirror plan/progress/index files to the NAS account folder")

        nas_index_parser = subparsers.add_parser("nas-index", help="Refresh NAS account artifact index and progress mirror")
        nas_index_parser.add_argument("--root", default=".", help="Knowledge base root")
        nas_index_parser.add_argument("--artifacts-dir", required=True, help="NAS artifacts root")
        nas_index_parser.add_argument("--account-name", required=True, help="Account folder/name to index")

        status_parser = subparsers.add_parser("status", help="Show queue and manifest status")
        status_parser.add_argument("--root", default=".", help="Knowledge base root")

        args = parser.parse_args()
        root = Path(args.root).resolve()
        with MacSleepGuard(should_prevent_sleep(args)):
            if args.command == "scan":
                result = run_pipeline(
                    root,
                    apply=args.apply,
                    analyze_video=args.analyze_video,
                    video_limit=max(args.video_limit, 0),
                    analyze_images=args.analyze_images,
                    image_limit=max(args.image_limit, 0),
                    max_images_per_note=max(args.max_images_per_note, 0),
                    account_name=args.account_name,
                    source_ids=parse_source_ids(args.source_ids),
                )
            elif args.command == "select":
                result = select_deep_learning(
                    root,
                    source_ids=parse_source_ids(args.source_ids),
                    account_name=args.account_name,
                    direction=args.direction,
                    top_n=max(args.top_n, 0),
                )
            elif args.command == "learn":
                result = run_selected_deep_learning(
                    root,
                    source_ids=parse_source_ids(args.source_ids),
                    analyze_video=args.analyze_video,
                    video_limit=max(args.video_limit, 0),
                    analyze_images=args.analyze_images,
                    max_images_per_note=max(args.max_images_per_note, 0),
                    force=args.force,
                    artifacts_dir=parsed_artifacts_dir(args.artifacts_dir),
                    artifact_layout=args.artifact_layout,
                    account_name=args.account_name,
                    mirror_nas_state=args.mirror_nas_state,
                )
            elif args.command == "download":
                result = download_selected_media(
                    root,
                    source_ids=parse_source_ids(args.source_ids),
                    artifacts_dir=parsed_artifacts_dir(args.artifacts_dir),
                    artifact_layout=args.artifact_layout,
                    account_name=args.account_name,
                    mirror_nas_state=args.mirror_nas_state,
                )
            elif args.command == "nas-index":
                result = generate_nas_account_index(root, parsed_artifacts_dir(args.artifacts_dir) or Path(args.artifacts_dir), args.account_name)
            else:
                result = learning_status(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser = argparse.ArgumentParser(description="Run video metadata learning for the knowledge base.")
    parser.add_argument("--root", default=".", help="Knowledge base root")
    parser.add_argument("--apply", action="store_true", help="Append high-confidence entries to formal knowledge files")
    parser.add_argument("--analyze-video", action="store_true", help="Try video download, audio extraction, transcription, and scene detection")
    parser.add_argument("--video-limit", type=int, default=1, help="Maximum videos to analyze in one run")
    parser.add_argument("--analyze-images", action="store_true", help="Try XHS image download, OCR, and image learning")
    parser.add_argument("--image-limit", type=int, default=1, help="Maximum image posts to analyze in one run")
    parser.add_argument("--max-images-per-note", type=int, default=18, help="Maximum images to download per image post")
    parser.add_argument("--account-name", default="", help="Exact account name filter for scan outputs")
    parser.add_argument("--source-ids", default="", help="Comma-separated source IDs to target for video analysis")
    parser.add_argument("--check-env", action="store_true", help="Print tool availability and exit")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.check_env:
        print(json.dumps(check_env(), ensure_ascii=False, indent=2))
        return 0
    with MacSleepGuard(should_prevent_sleep(args)):
        result = run_pipeline(
            root,
            apply=args.apply,
            analyze_video=args.analyze_video,
            video_limit=max(args.video_limit, 0),
            analyze_images=args.analyze_images,
            image_limit=max(args.image_limit, 0),
            max_images_per_note=max(args.max_images_per_note, 0),
            account_name=args.account_name,
            source_ids=parse_source_ids(args.source_ids),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
