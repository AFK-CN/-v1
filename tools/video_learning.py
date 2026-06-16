from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
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
    return [item.strip() for item in str(value).split(",") if item.strip()]


def split_image_urls(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        candidates = [str(item).strip() for item in value]
    else:
        candidates = [item.strip() for item in str(value).split(",")]
    return [url for url in candidates if url]


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
        video_download_url = str(row.get("video_url") or "")
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


def load_records(root: Path) -> tuple[list[NormalizedRecord], dict[str, int]]:
    raw_counts = {
        "douyin_contents": 0,
        "xhs_contents": 0,
        "douyin_comments": 0,
        "creators": 0,
        "unknown": 0,
    }
    records: list[NormalizedRecord] = []
    search_roots = [root / "数据", root / "00_Inbox"]
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in sorted(search_root.rglob("*.json")):
            rows = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(rows, list):
                raw_counts["unknown"] += 1
                continue
            kind = classify_json(path, rows)
            raw_counts[kind] = raw_counts.get(kind, 0) + len(rows)
            if kind == "douyin_contents":
                records.extend(normalize_record("douyin", row, path.relative_to(root)) for row in rows)
            elif kind == "xhs_contents":
                records.extend(normalize_record("xhs", row, path.relative_to(root)) for row in rows)
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


def video_status(root: Path, record: NormalizedRecord, analyze_video: bool) -> dict[str, Any]:
    status: dict[str, Any] = {
        "requested": analyze_video,
        "has_video_url": bool(record.video_download_url),
        "ffmpeg": find_executable("ffmpeg"),
        "faster_whisper": False,
        "scenedetect": False,
        "status": "metadata_only",
        "artifacts": {},
        "errors": [],
    }
    artifact_dir = root / "01_Case_Cleaning" / "video_learning" / "video_artifacts" / f"{record.platform}_{record.source_id}"
    video_path = artifact_dir / "source.mp4"
    audio_path = artifact_dir / "audio.wav"
    metadata_path = artifact_dir / "ffprobe.json"
    transcript_json_path = artifact_dir / "transcript.json"
    transcript_srt_path = artifact_dir / "transcript.srt"
    existing_scene_files = sorted(artifact_dir.glob("*Scenes.csv"))
    if video_path.exists() and audio_path.exists() and metadata_path.exists() and transcript_json_path.exists() and transcript_srt_path.exists() and existing_scene_files:
        status["status"] = "video_transcribed_and_scenes_detected"
        status["artifacts"] = {
            "video": str(video_path.relative_to(root)),
            "audio": str(audio_path.relative_to(root)),
            "metadata": str(metadata_path.relative_to(root)),
            "transcript_json": str(transcript_json_path.relative_to(root)),
            "transcript_srt": str(transcript_srt_path.relative_to(root)),
            "scenes_csv": str(existing_scene_files[0].relative_to(root)),
        }
        image_files = sorted(artifact_dir.glob("*.jpg")) + sorted(artifact_dir.glob("*.png"))
        if image_files:
            status["artifacts"]["keyframes"] = [str(path.relative_to(root)) for path in image_files[:10]]
        return status

    if not analyze_video or not record.video_download_url:
        return status
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

    try:
        status["errors"].extend(ensure_video_file(record.video_download_url, video_path))
        subprocess.run(
            [status["ffmpeg"], "-y", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", str(audio_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        probe = subprocess.run(
            [find_executable("ffprobe"), "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(video_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        metadata_path.write_text(probe.stdout, encoding="utf-8")
        status["status"] = "video_downloaded_audio_extracted"
        status["artifacts"] = {
            "video": str(video_path.relative_to(root)),
            "audio": str(audio_path.relative_to(root)),
            "metadata": str(metadata_path.relative_to(root)),
        }
    except Exception as exc:
        status["status"] = "degraded_video_failed"
        status["errors"].append(str(exc))
        return status

    try:
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
        transcript_json_path.write_text(
            json.dumps(
                {
                    "language": getattr(info, "language", "zh"),
                    "duration": getattr(info, "duration", None),
                    "segments": transcript_segments,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        transcript_srt_path.write_text(srt_from_segments(transcript_segments), encoding="utf-8")
        status["artifacts"]["transcript_json"] = str(transcript_json_path.relative_to(root))
        status["artifacts"]["transcript_srt"] = str(transcript_srt_path.relative_to(root))
    except Exception as exc:
        status["errors"].append(f"transcription_failed: {exc}")

    try:
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
        scene_files = sorted(artifact_dir.glob("*Scenes.csv"))
        image_files = sorted(artifact_dir.glob("*.jpg")) + sorted(artifact_dir.glob("*.png"))
        if scene_files:
            status["artifacts"]["scenes_csv"] = str(scene_files[0].relative_to(root))
        if image_files:
            status["artifacts"]["keyframes"] = [str(path.relative_to(root)) for path in image_files[:10]]
    except Exception as exc:
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


VIDEO_DOWNLOAD_TIMEOUT_SECONDS = 300
VIDEO_CONNECT_TIMEOUT_SECONDS = 20


def download_binary_url(url: str, path: Path, timeout: int = VIDEO_DOWNLOAD_TIMEOUT_SECONDS) -> None:
    curl = find_executable("curl")
    if curl:
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
                str(timeout),
                "--retry",
                "3",
                "--retry-delay",
                "2",
                "--retry-all-errors",
                "--speed-limit",
                "1024",
                "--speed-time",
                "60",
                "-A",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
                "-H",
                "Referer: https://www.douyin.com/",
                "-H",
                "Accept: */*",
                "-o",
                str(path),
                url,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout + 30,
        )
        return
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
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


def ensure_video_file(url: str, path: Path) -> list[str]:
    if media_file_is_readable(path):
        return ["using_existing_video_file"]
    try:
        download_binary_url(url, path)
    except Exception as exc:
        if media_file_is_readable(path):
            return [f"download_reported_error_but_file_is_readable: {exc}"]
        raise
    if not media_file_is_readable(path):
        raise RuntimeError(f"downloaded video is not readable: {path}")
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
    artifact_dir = root / "01_Case_Cleaning" / "video_learning" / "image_artifacts" / f"{record.platform}_{record.source_id}"
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
metrics:
  likes: {metrics["likes"]}
  collects: {metrics["collects"]}
  comments: {metrics["comments"]}
  shares: {metrics["shares"]}
video_analysis_status: {video["status"]}
image_analysis_status: {image["status"]}
decision: {"keep" if high_confidence(item) else "review"}
```

## 为什么入选

- 账号：{record.account_name or "未知账号"}。
- 属于 `{item.direction}` 方向 Top{item.rank}。
- 平台加权热度分为 `{item.score}`。
- 指标证据：点赞 {metrics["likes"]}，收藏 {metrics["collects"]}，评论 {metrics["comments"]}，转发 {metrics["shares"]}。

## 内容结构

- 开头：{first_sentence(record.title, 60)}
- 痛点：{infer_audience(item.direction, record)}需要更低门槛、更可复用的方法。
- 展开：{first_sentence(record.body, 120)}
- 结尾：适合收束为一个可复述的行动建议或清单承诺。

## 可复用价值

- 可复用标题结构：{reusable_template(item.direction, record)}
- 可复用脚本结构：{reusable_template(item.direction, record)}
- 可生成选题：围绕 `{item.direction}` 做同主题变体、步骤化教程、评论区问题回答。
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
    current = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in current:
        return False
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)
    return True


def write_formal_entries(root: Path, high_items: list[RankedRecord]) -> dict[str, int]:
    counts = {"methods": 0, "topics": 0, "templates": 0}
    for item in high_items:
        method_path = root / "02_Viral_Methods" / ("小红书爆款方法论_v1.md" if item.record.platform == "xhs" else "抖音爆款方法论_v1.md")
        topic_path = root / "03_Topic_Ideas" / "选题灵感库_v1.md"
        method_marker = f"video-learning:auto-method:{item.record.platform}:{item.record.source_id}:{item.direction}"
        topic_marker = f"video-learning:auto-topic:{item.record.platform}:{item.record.source_id}:{item.direction}"
        if append_once(method_path, method_marker, formal_method_entry(item)):
            counts["methods"] += 1
        if append_once(topic_path, topic_marker, formal_topic_entry(item)):
            counts["topics"] += 1

    template_path = root / "08_Content_Factory" / "内容生产模板_v1.md"
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
    account_dir = root / "01_Case_Cleaning" / "video_learning" / "account_cards"
    account_dir.mkdir(parents=True, exist_ok=True)
    for old_card in account_dir.glob("*.md"):
        old_card.unlink()
    accounts = sorted({(record.account_name or "未知账号", record.platform) for record in records})
    for account_name, platform in accounts:
        path = account_dir / f"{safe_filename(account_name)}_{platform}.md"
        path.write_text(account_card_markdown(account_name, platform, records, rankings), encoding="utf-8")
    return len(accounts)


def write_candidate_subkb(root: Path, rankings: dict[str, list[RankedRecord]]) -> int:
    path = root / "05_Sub_KB_Candidates" / "候选子库_视频深度学习方向.md"
    new_directions = sorted(direction for direction in rankings if direction not in KNOWN_DIRECTIONS and direction != "未归类")
    if not new_directions:
        return 0
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
    apply: bool,
    analyze_video: bool,
    video_limit: int,
    analyze_images: bool,
    image_limit: int,
    max_images_per_note: int,
    source_ids: set[str] | None,
) -> dict[str, Any]:
    output_dir = root / "01_Case_Cleaning" / "video_learning"
    cards_dir = output_dir / "deep_cards"
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
                and bool(item.record.video_download_url)
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

    report = report_markdown(raw_counts, dedupe_stats, records, rankings, high_items, apply, analyze_video, analyze_images)
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
        f"- 去重后内容：{dedupe_stats.get('unique_records', len(records))}",
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
    return root / "01_Case_Cleaning" / "video_learning"


def record_key(record: NormalizedRecord) -> str:
    return f"{record.platform}:{record.source_id}"


def load_unique_records(root: Path) -> tuple[list[NormalizedRecord], dict[str, int], dict[str, int]]:
    records, raw_counts = load_records(root)
    unique_records, dedupe_stats = deduplicate_records(records)
    return unique_records, raw_counts, dedupe_stats


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
    return video_learning_dir(root) / "queues" / "pending_deep_learning.json"


def manifest_path(root: Path) -> Path:
    return video_learning_dir(root) / "state" / "learning_manifest.json"


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


def selected_card_markdown(record: NormalizedRecord, directions: list[str], video: dict[str, Any], image: dict[str, Any]) -> str:
    metrics = record.metrics
    direction_text = "、".join(directions)
    return f"""# 已确认深度学习卡：{record.platform} {record.source_id}

```yaml
source_id: {record.source_id}
platform: {record.platform}
account_name: {record.account_name or "未知账号"}
directions: {direction_text}
heat_score: {heat_score(record)}
title: {record.title}
url: {record.url}
metrics:
  likes: {metrics["likes"]}
  collects: {metrics["collects"]}
  comments: {metrics["comments"]}
  shares: {metrics["shares"]}
video_analysis_status: {video["status"]}
image_analysis_status: {image["status"]}
decision: review
```

## 为什么学习

- 这是人工确认进入深度学习队列的内容。
- 账号：{record.account_name or "未知账号"}。
- 方向：{direction_text}。
- 指标证据：点赞 {metrics["likes"]}，收藏 {metrics["collects"]}，评论 {metrics["comments"]}，转发 {metrics["shares"]}。

## 内容结构

- 开头：{first_sentence(record.title, 80)}
- 目标人群：{infer_audience(directions[0], record)}
- 展开：{first_sentence(record.body, 160)}
- 可复用结构：{reusable_template(directions[0], record)}

## 视频层状态

```json
{json.dumps(video, ensure_ascii=False, indent=2)}
```

## 图片层状态

```json
{json.dumps(image, ensure_ascii=False, indent=2)}
```

## 下一步建议

- 若视频或图片层完成：进入人工复核，判断是否沉淀到正式方法论/选题库。
- 若状态为降级失败：保留文本学习结果，等待刷新下载链接或补充素材后再重跑。
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
    records, raw_counts, dedupe_stats = load_unique_records(root)
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
        lines.append(
            f"| {key} | {status.get('status', '')} | {status.get('card_path', '')} | {transcript} | "
            f"{'; '.join(errors)[:120]} |"
        )
    if missing:
        lines.extend(["", "## 未找到", ""])
        lines.extend(f"- {source_id}" for source_id in missing)
    if skipped:
        lines.extend(["", "## 已跳过", ""])
        lines.extend(f"- {source_id}" for source_id in skipped)
    return "\n".join(lines) + "\n"


def run_selected_deep_learning(
    root: Path,
    source_ids: set[str] | None = None,
    analyze_video: bool = False,
    video_limit: int = 1,
    analyze_images: bool = False,
    max_images_per_note: int = 18,
    force: bool = False,
) -> dict[str, Any]:
    requested_ids = source_ids or selected_ids_from_queue(root)
    records, raw_counts, dedupe_stats = load_unique_records(root)
    by_id = records_by_source_id(records)
    output_dir = video_learning_dir(root)
    cards_dir = output_dir / "selected_deep_cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(root)
    manifest_items = manifest.setdefault("items", {})
    statuses: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    skipped: list[str] = []
    learned = 0
    analyzed_videos = 0

    for source_id in sorted(requested_ids):
        record = by_id.get(source_id)
        if not record:
            missing.append(source_id)
            continue
        key = record_key(record)
        existing = manifest_items.get(key, {})
        if existing.get("status") == "completed" and not force:
            skipped.append(source_id)
            continue
        should_analyze_video = analyze_video and analyzed_videos < video_limit and bool(record.video_download_url)
        if should_analyze_video:
            analyzed_videos += 1
        video = video_status(root, record, should_analyze_video)
        image = image_status(root, record, analyze_images and record.platform == "xhs", max_images_per_note=max_images_per_note)
        directions = detect_directions(record)
        card_path = cards_dir / f"{record.platform}_{record.source_id}.md"
        card_path.write_text(selected_card_markdown(record, directions, video, image), encoding="utf-8")
        status = learning_outcome(video, image, analyze_video, analyze_images)
        entry = {
            "platform": record.platform,
            "source_id": record.source_id,
            "account_name": record.account_name or record.author_name,
            "title": record.title,
            "directions": directions,
            "status": status,
            "card_path": str(card_path.relative_to(root)),
            "video": video,
            "image": image,
            "last_run_at": datetime.now().isoformat(timespec="seconds"),
        }
        manifest_items[key] = entry
        statuses[key] = entry
        update_queue_status(root, record.platform, record.source_id, status)
        learned += 1

    save_manifest(root, manifest)
    result = {
        "raw_counts": raw_counts,
        "dedupe_stats": dedupe_stats,
        "requested": len(requested_ids),
        "found": len(requested_ids) - len(missing),
        "learned": learned,
        "skipped": len(skipped),
        "missing": missing,
        "video_analysis_requested": analyzed_videos,
        "selected_cards_dir": str(cards_dir.relative_to(root)),
        "manifest": str(manifest_path(root).relative_to(root)),
        "report": str((output_dir / "latest_selected_deep_learning_report.md").relative_to(root)),
    }
    write_json_file(output_dir / "latest_selected_video_statuses.json", statuses)
    (output_dir / "latest_selected_deep_learning_report.md").write_text(
        selected_report_markdown(result, statuses, missing, skipped),
        encoding="utf-8",
    )
    return result


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
    source_ids: set[str] | None = None,
) -> dict[str, Any]:
    records, raw_counts = load_records(root)
    unique_records, dedupe_stats = deduplicate_records(records)
    rankings = build_direction_rankings(unique_records)
    return write_outputs(
        root,
        raw_counts,
        dedupe_stats,
        unique_records,
        rankings,
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


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"scan", "select", "learn", "status"}:
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

        status_parser = subparsers.add_parser("status", help="Show queue and manifest status")
        status_parser.add_argument("--root", default=".", help="Knowledge base root")

        args = parser.parse_args()
        root = Path(args.root).resolve()
        if args.command == "scan":
            result = run_pipeline(
                root,
                apply=args.apply,
                analyze_video=args.analyze_video,
                video_limit=max(args.video_limit, 0),
                analyze_images=args.analyze_images,
                image_limit=max(args.image_limit, 0),
                max_images_per_note=max(args.max_images_per_note, 0),
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
            )
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
    parser.add_argument("--source-ids", default="", help="Comma-separated source IDs to target for video analysis")
    parser.add_argument("--check-env", action="store_true", help="Print tool availability and exit")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if args.check_env:
        print(json.dumps(check_env(), ensure_ascii=False, indent=2))
        return 0
    result = run_pipeline(
        root,
        apply=args.apply,
        analyze_video=args.analyze_video,
        video_limit=max(args.video_limit, 0),
        analyze_images=args.analyze_images,
        image_limit=max(args.image_limit, 0),
        max_images_per_note=max(args.max_images_per_note, 0),
        source_ids=parse_source_ids(args.source_ids),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
