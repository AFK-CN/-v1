from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full")
V2_CARDS = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/v2_relearning")
FORMAL = Path("10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/李宗恒")
ACCOUNT_INDEX_JSON = Path("10_Knowledge/evidence/index/account_knowledge_index.json")
ACCOUNT_INDEX_MD = Path("10_Knowledge/evidence/index/account_knowledge_index.md")
INGEST_DATE = "2026-07-14"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def source_id_set(path: Path) -> set[str]:
    return {str(item["source_id"]) for item in read_jsonl(path)}


def formalize_natural_card(text: str) -> str:
    text = text.replace("状态：batch_review_passed", "状态：formal_ingested")
    text = text.replace("状态：candidate_learned", "状态：formal_ingested")
    for marker in ("## 10. 方法候选与可复用方法论", "## 10. 方法候选"):
        if marker in text:
            text = text.split(marker, 1)[0].rstrip()
            break
    return (
        text.rstrip()
        + "\n\n## 正式入库状态\n\n"
        + f"- {INGEST_DATE} 经用户确认进入李宗恒正式账号中心。\n"
        + "- 本卡用于单条证据、分类、剧情结构、发布文案和话题回溯；方法调用以账号中心四个正式方法为准。\n"
        + "- 合拍演员仅表示本条作品中的共同演出，不拆分为独立学习账号。\n"
    )


def formalize_ad_card(text: str) -> str:
    old = "- 本卡保持 `callable=false`、`formal_write=false`。"
    new = (
        f"- {INGEST_DATE} 经用户确认进入李宗恒正式账号中心。\n"
        "- 本卡可作为广告植入案例调用，但不得增加自然选题或自然方法的 V1 权重。"
    )
    if old not in text:
        raise ValueError("ad card is missing candidate boundary")
    return text.replace(old, new)


def formalize_platform_card(text: str) -> str:
    old = "- 本卡保持 `callable=false`、`formal_write=false`。"
    new = (
        f"- {INGEST_DATE} 经用户确认进入李宗恒正式账号中心。\n"
        "- 本卡可作为平台项目承载案例调用，但不得增加自然内容发布频次。"
    )
    if old not in text:
        raise ValueError("platform card is missing candidate boundary")
    return text.replace(old, new)


def formalize_method_md(text: str) -> str:
    old = "状态：`verified_candidate`；调用：`false`；账号范围：`李宗恒`"
    new = "状态：`formal_verified`；调用：`true`；账号范围：`李宗恒`"
    if old not in text:
        raise ValueError("method is missing candidate status")
    return text.replace(old, new, 1).replace(
        "证据只支持候选方法，不证明必然带来播放或转化结果。",
        "证据支持正式方法调用，但不证明必然带来播放或转化结果。",
    )


def latest_v2_cards(root: Path) -> dict[str, Path]:
    cards: dict[str, Path] = {}
    for path in sorted((root / V2_CARDS).glob("batch_*/cards/*.md")):
        source_id = path.stem
        if source_id in cards:
            raise ValueError(f"duplicate v2 card: {source_id}")
        cards[source_id] = path
    return cards


def account_index_entry() -> dict[str, Any]:
    base = FORMAL.as_posix()
    directions = [
        ("自然短剧情", 272),
        ("商品广告植入", 140),
        ("平台项目", 18),
    ]
    layers = [
        {"layer": "account_status_overview", "path": f"{base}/账号概述.md", "description": "账号学习状态、资料范围和证据边界。"},
        {"layer": "account_overview", "path": f"{base}/账号方法论总览.md", "description": "四个正式方法及三轨调用入口。"},
        {"layer": "account_summary", "path": f"{base}/账号整体方法论.md", "description": "账号定位、方法编排和边界。"},
        {"layer": "content_usage", "path": f"{base}/内容生产使用说明.md", "description": "内容生产的固定读取顺序。"},
        {"layer": "anti_ai_style", "path": f"{base}/减少AI味输出规则.md", "description": "基于本账号证据的表达约束。"},
        {"layer": "account_content_template", "path": f"{base}/内容输出标准模板.md", "description": "完整内容包模板。"},
        {"layer": "publishing_style", "path": f"{base}/发布文案与话题学习.md", "description": "短发布文案、标题和话题的证据化使用规则。"},
        {"layer": "method_composition", "path": f"{base}/方法组合与交叉验证.md", "description": "方法选择、组合、消融和商业分轨规则。"},
    ]
    direction_entries = []
    for direction, count in directions:
        direction_base = f"{base}/directions/{direction}"
        direction_entries.append(
            {
                "direction": direction,
                "status": "formal_ingested",
                "card_count": count,
                "transcript_file_count": 0,
                "formal_direction_dir": direction_base,
            }
        )
        layers.extend(
            [
                {"layer": "direction_method", "direction": direction, "path": f"{direction_base}/方向方法论总结.md", "description": "方向级方法与调用边界。"},
                {"layer": "single_cards", "direction": direction, "path": f"{direction_base}/cards", "description": "正式单条学习卡。"},
            ]
        )
    return {
        "account_id": "lizongheng",
        "account_name": "李宗恒",
        "platform": "抖音",
        "formal_account_dir": base,
        "directions": direction_entries,
        "knowledge_layers": layers,
    }


def render_account_index_md(payload: dict[str, Any]) -> str:
    lines = [
        "# 账号知识总索引",
        "",
        "| 账号 | 平台 | 正式目录 | 已入库方向 |",
        "|---|---|---|---|",
    ]
    for account in payload.get("accounts", []):
        directions = "、".join(item["direction"] for item in account.get("directions", []))
        lines.append(
            f"| {account['account_name']} | {account['platform']} | {account['formal_account_dir']} | {directions} |"
        )
    return "\n".join(lines) + "\n"


def update_account_indexes(root: Path) -> None:
    path = root / ACCOUNT_INDEX_JSON
    payload = read_json(path)
    accounts = [item for item in payload.get("accounts", []) if item.get("account_id") != "lizongheng"]
    accounts.append(account_index_entry())
    accounts.sort(key=lambda item: item.get("account_name", ""))
    payload["generated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    payload["accounts"] = accounts
    write_json(path, payload)
    write_text(root / ACCOUNT_INDEX_MD, render_account_index_md(payload))


def copy_formal_method(root: Path, method_id: str) -> None:
    source = root / WORKFLOW / "methods" / method_id
    target = root / FORMAL / "methods" / method_id
    write_text(target / "METHOD.md", formalize_method_md((source / "METHOD.md").read_text(encoding="utf-8")))
    payload = read_json(source / "method.json")
    payload["status"] = "formal_verified"
    payload["callable"] = True
    payload["formal_ingested_at"] = INGEST_DATE
    write_json(target / "method.json", payload)
    shutil.copy2(source / "test-prompts.json", target / "test-prompts.json")
    shutil.copy2(source / "test-results.json", target / "test-results.json")


def top_level_files(root: Path) -> dict[str, str]:
    base = FORMAL.as_posix()
    return {
        "账号索引.md": f"""# 李宗恒账号索引

用途：从正式账号中心调用李宗恒的账号方法、发布表达和单条证据，不重新扫描候选区或 NAS。

## 读取顺序

1. `账号概述.md`：确认正式状态、资料范围和证据边界。
2. `账号方法论总览.md`：选择四个正式方法和内容三轨。
3. `方法组合与交叉验证.md`：组合方法前检查主方法、递进方法和消融条件。
4. `发布文案与话题学习.md`：处理短标题、发布文案和话题，不用短文案替代内容分类。
5. `内容生产使用说明.md`、`减少AI味输出规则.md`、`内容输出标准模板.md`：生成内容前必读。
6. `directions/自然短剧情/cards/`：272 张正常内容正式卡。
7. `directions/商品广告植入/cards/`：140 张广告四段式正式卡。
8. `directions/平台项目/cards/`：18 张平台项目正式卡。
9. `methods/`：4 个经三重验证和压力测试的正式方法单元。

## 正式方向

| 方向 | 单卡 | 方法入口 |
|---|---:|---|
| 自然短剧情 | 272 | `{base}/directions/自然短剧情/方向方法论总结.md` |
| 商品广告植入 | 140 | `{base}/directions/商品广告植入/方向方法论总结.md` |
| 平台项目 | 18 | `{base}/directions/平台项目/方向方法论总结.md` |
""",
        "账号概述.md": """# 李宗恒账号概述

- 账号：李宗恒
- 平台：抖音
- 正式状态：formal_ingested
- 账号 ID：63700340656
- 学习范围：NAS 账号目录 430/430 条视频
- 正式单卡：272 条自然短剧情、140 条商品广告、18 条平台项目
- 正式方法：4 个
- 验收：六分层真实验收通过；140/140 广告和 18/18 平台项目完成源证据审计；430/430 表现数据完成描述性关联
- 合拍边界：于洋、刘大悦er、大伟老三等只按共同演出或合作关系记录，不拆为独立账号

## 账号定位

以多人短剧情和角色表演为主，把职场、校园、家庭、恋爱、朋友和消费服务中的常规规则替换为另一套规则，再通过权力反转、语言歧义和连续升级制造笑点。

## 证据边界

- 发布文案通常很短，不能单独决定内容分类；必须结合逐字稿、画面、人物关系和剧情因果。
- 商品广告不增加自然方法频次，但必须学习正常剧情、广告引入、产品角色和广告后收束。
- 平台栏目、挑战赛、舞台和作品宣发独立成轨，不与商品广告混合。
- 点赞、收藏、评论、分享和热度仅用于描述性复核，不证明某方法导致爆款。
""",
        "账号方法论总览.md": """# 李宗恒账号方法论总览

## 四个正式方法

| 方法 | 角色 | 核心判定 |
|---|---|---|
| 整套系统迁移 | 主冲突 | 至少三层系统元素映射，规则持续驱动行动和结算 |
| 评价权与控制权反转 | 主冲突 | 原弱势方持续取得提问、定义、服务或审批权 |
| 字面重释与双语境链 | 主冲突 | 替代解释在语言上自洽并继续驱动行动后果 |
| 固定规则多场景递进 | 递进发动机 | 同一规则多轮兑现，每轮增加关系、信息或后果 |

## 固定调用顺序

`证据与账号归属 -> 正常/广告/平台分流 -> 选择一个主冲突方法 -> 必要时叠加递进方法 -> 标题文案话题包装 -> 再做边界检查`

主方法由冲突因果决定，不因题材词、演员名或场景词自动触发。商品广告另走 B1-B5 植入桥；平台项目只证明任务承载和身份履历。
""",
        "账号整体方法论.md": """# 李宗恒账号整体方法论

## 内容发动机

熟悉关系和场景提供常识；系统迁移、控制权反转或语言重释打破常识；固定规则递进负责放大；身份揭示、关系回收或结算反转负责收束。

## 方法编排

- 正常内容只选一个主要冲突方法，M4 只负责递进。
- M1+M4、M2+M4、M3+M4 是稳定组合；M1+M2 需要两条因果都独立成立。
- M1+M3、M2+M3 谨慎组合；M1+M2+M3 默认禁止，除非逐项消融均造成结构性变化。
- 广告先分析正常剧情，再判断引入桥、产品角色、卖点载荷和广告后收束。
- 平台项目先确认外部项目归属和李宗恒参与角色，再学习任务壳如何承载内容。

## 不能误学的内容

- 合拍演员、同剧演员和合作账号不是独立发布账号。
- 极短发布文案不是完整内容分类证据。
- 广告数量不能证明自然选题偏好。
- 单条高互动案例不能证明方法必然有效。
""",
        "内容生产使用说明.md": """# 李宗恒内容生产使用说明

1. 先确认任务属于自然短剧情、商品广告还是平台项目。
2. 自然短剧情从 M1/M2/M3 中选择一个主冲突；需要多轮升级时再叠加 M4。
3. 商品广告先写可独立成立的正常剧情，再选择 B1-B5 引入桥，明确产品角色和广告后收束。
4. 平台项目先确认项目壳、参与角色和发布任务，不硬套商品卖点。
5. 最后调用发布文案与话题规则完成标题、文案和标签。
6. 输出前执行消融：删除每个被调用方法，若结构没有变化，该方法不应保留。

禁止只换人物、场景、产品或原句；必须迁移冲突因果。需要原始案例时只读取对应正式单卡，不全扫 NAS 或候选区。
""",
        "减少AI味输出规则.md": """# 李宗恒减少AI味输出规则

- 标题先给具体设定、关系或疑问，不用抽象价值判断和总结腔。
- 发布文案可以短，但脚本必须把人物、规则、冲突和收束写完整。
- 台词必须像角色在解决当下问题，不让人物轮流解释方法论。
- 一轮只增加一个新动作、信息或后果；不用同义句反复解释。
- 包袱来自规则兑现、控制权变化或语义后果，不靠堆网络热词。
- 不复制来源演员、品牌、故事事实和原句；保留机制，重建人物动机。
- 广告卖点翻译成角色需求、关键道具或世界规则；低融合集中口播必须明确标为边界方案。
- 收尾优先回到人物关系、固定规则或前段悬念，不额外拔高主题。
""",
        "内容输出标准模板.md": """# 李宗恒内容输出标准模板

## 发布包

- 内容轨道：自然短剧情 / 商品广告 / 平台项目
- 选题：一句可执行的关系与冲突
- 发布标题：具体设定或悬念
- 发布文案：短句，不提前解释完整笑点
- 话题：账号、人物关系、场景、任务或品牌标签分层填写
- 黄金三秒：人物动作 + 异常规则
- 正文脚本：设定、冲突、三轮升级、转折、收束
- 使用方法：一个主冲突方法；可选一个递进方法
- 证据参考：正式方法 ID 和正式单卡 source_id
- 复用边界：明确不能复制的人物、原句、产品和故事事实

## 广告附加字段

- 广告前正常剧情发动机
- 广告引入桥 B1-B5
- 产品在剧情中的角色
- 卖点如何转成角色收益或行动
- 广告后是否回到原剧情
""",
        "发布文案与话题学习.md": """# 李宗恒发布文案与话题学习

## 分类原则

发布文案经常只有一句设定、一个情绪或一个疑问，因此只用于发布层学习，不能独立决定剧情分类。内容分类必须联合逐字稿、画面、人物关系、场景和最终冲突因果。

## 可复用规则

- 标题优先直接命名异常设定，例如“如果……像……”“当……遇到……”“假如有……”。
- 极短文案只承担入口，不在标题中解释完整反转。
- 书名号常用于把视频包装成一则完整短剧；艾特姓名只标记合拍或同框关系。
- 账号标签、人物关系标签、场景标签和活动/品牌标签分层处理，不把品牌词混入自然选题频次。
- 广告标题可先承诺剧情设定，品牌标签后置；是否为广告仍以视频载荷和源证据判断。
- 平台活动标签用于确认外部项目壳，不自动变成账号自然方向。

## 输出检查

标题、文案、话题必须服务同一个冲突；删除所有标签后，脚本仍应能说明人物为何行动、冲突如何升级和结尾如何收束。
""",
    }


def direction_files(root: Path) -> dict[Path, str]:
    workflow = root / WORKFLOW
    ad_methods = (workflow / "ad_integration/AD_INTEGRATION_METHODS.md").read_text(encoding="utf-8")
    platform_methods = (workflow / "ad_integration/PLATFORM_PROJECT_METHODS.md").read_text(encoding="utf-8")
    ad_methods = ad_methods.replace("候选", "正式").replace("`callable=false`、`formal_write=false`", "已正式入库")
    platform_methods = platform_methods.replace("18 条均保持 `callable=false`，正式账号中心写入仍需用户验收。", "18 条均已完成用户确认并进入正式账号中心。")
    natural = """# 自然短剧情方向方法论总结

自然短剧情只用 272 条非商品广告、非平台项目内容证明账号自然方法。

## 正式方法

1. 整套系统迁移：至少三层系统元素映射并影响结算。
2. 评价权与控制权反转：权力变化通过持续动作兑现。
3. 字面重释与双语境链：替代解释必须继续驱动行动。
4. 固定规则多场景递进：作为递进发动机叠加在一个主冲突上。

## 边界

- 短发布文案不单独决定分类。
- 合拍演员不拆成独立账号。
- 广告和平台项目不增加自然方法频次。
- 每次生成只选择一个主冲突方法，组合必须通过消融。
"""
    return {
        Path("directions/自然短剧情/方向方法论总结.md"): natural,
        Path("directions/商品广告植入/方向方法论总结.md"): ad_methods,
        Path("directions/平台项目/方向方法论总结.md"): platform_methods,
    }


def ingest(root: Path) -> dict[str, Any]:
    root = root.resolve()
    workflow = root / WORKFLOW
    acceptance = read_json(workflow / "REAL_ACCEPTANCE_SUMMARY.json")
    if acceptance.get("status") != "passed" or acceptance.get("schema_version") != "2.2":
        raise ValueError("v2.2 acceptance has not passed")
    if acceptance.get("semantic_consistency", {}).get("natural_v1_commercial_pollution"):
        raise ValueError("commercial evidence polluted natural V1")

    ad_ids = source_id_set(workflow / "ad_integration/AD_INTEGRATION_INDEX.jsonl")
    platform_ids = source_id_set(workflow / "ad_integration/PLATFORM_PROJECT_INDEX.jsonl")
    if ad_ids & platform_ids:
        raise ValueError("ad and platform tracks overlap")
    cards = latest_v2_cards(root)
    if len(cards) != 430 or len(ad_ids) != 140 or len(platform_ids) != 18:
        raise ValueError("unexpected source counts")
    natural_ids = set(cards) - ad_ids - platform_ids
    if len(natural_ids) != 272:
        raise ValueError("unexpected natural card count")

    formal = root / FORMAL
    if formal.exists():
        raise FileExistsError(f"formal account already exists: {formal}")

    for name, content in top_level_files(root).items():
        write_text(formal / name, content)
    for path, content in direction_files(root).items():
        write_text(formal / path, content)

    for source_id in sorted(natural_ids):
        content = formalize_natural_card(cards[source_id].read_text(encoding="utf-8"))
        write_text(formal / "directions/自然短剧情/cards" / f"{source_id}.md", content)
    for source_id in sorted(ad_ids):
        source = workflow / "ad_integration/cards" / f"{source_id}.md"
        write_text(formal / "directions/商品广告植入/cards" / source.name, formalize_ad_card(source.read_text(encoding="utf-8")))
    for source_id in sorted(platform_ids):
        source = workflow / "ad_integration/platform_cards" / f"{source_id}.md"
        write_text(formal / "directions/平台项目/cards" / source.name, formalize_platform_card(source.read_text(encoding="utf-8")))

    method_index = read_json(workflow / "METHOD_INDEX.json")
    method_index["methods"] = [dict(item, status="formal_verified", callable=True) for item in method_index["methods"]]
    write_json(formal / "METHOD_INDEX.json", method_index)
    for method in method_index["methods"]:
        copy_formal_method(root, method["id"])

    composition = (workflow / "METHOD_COMPOSITION_DESIGN.md").read_text(encoding="utf-8")
    composition = composition.replace("候选方法组合", "正式方法组合").replace("阶段 2 候选设计，待用户确认", "正式入库方法编排")
    composition = composition.replace("仍是 `verified_candidate_pending_user_confirmation`", "已是 `formal_verified`")
    write_text(formal / "方法组合与交叉验证.md", composition)
    shutil.copy2(workflow / "ad_integration/PERFORMANCE_METHOD_ANALYSIS.md", formal / "效果表现交叉分析.md")
    acceptance_report = (workflow / "REAL_ACCEPTANCE_REPORT_2026-07-14_V2_2.md").read_text(encoding="utf-8")
    acceptance_report = acceptance_report.replace(
        "所有产物仍为候选态，`formal_write=false`、`callable=false`。",
        f"候选产物已于 {INGEST_DATE} 经用户确认正式入库；正式方法可调用，单卡按对应内容轨道和证据边界调用。",
    )
    write_text(formal / "正式入库总验收报告.md", acceptance_report)

    evidence_dir = formal / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in ("AD_SOURCE_AUDIT_INDEX.jsonl", "PLATFORM_SOURCE_AUDIT_INDEX.jsonl", "SOURCE_AUDIT_SUMMARY.json", "MANUAL_VISUAL_COORDINATE_AUDIT.md"):
        shutil.copy2(workflow / "ad_integration" / name, evidence_dir / name)
    write_json(
        formal / "deep_learning_plan.json",
        {
            "schema_version": "2.2",
            "status": "formal_ingested",
            "account_name": "李宗恒",
            "account_id": "63700340656",
            "source_count": 430,
            "natural_card_count": 272,
            "product_ad_card_count": 140,
            "platform_project_card_count": 18,
            "method_count": 4,
            "performance_metric_match_count": 430,
            "formal_ingested_at": INGEST_DATE,
            "source_workflow": WORKFLOW.as_posix(),
        },
    )

    update_account_indexes(root)
    receipt = {
        "ok": True,
        "schema_version": "2.2",
        "account_name": "李宗恒",
        "formal_account_dir": FORMAL.as_posix(),
        "ingested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "counts": {"all_cards": 430, "natural": 272, "product_ads": 140, "platform_projects": 18, "methods": 4},
        "source_acceptance_sha256": hashlib.sha256((workflow / "REAL_ACCEPTANCE_SUMMARY.json").read_bytes()).hexdigest(),
        "user_confirmation": "2026-07-14 explicit formal ingest approval",
    }
    write_json(formal / "FORMAL_INGEST_RECEIPT.json", receipt)
    write_json(workflow / "FORMAL_INGEST_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote the accepted Li Zongheng v2.2 workflow into the formal account center.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    print(json.dumps(ingest(Path(args.root)), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
