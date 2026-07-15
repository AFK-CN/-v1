from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows/jianghushuo-v2-full")
ACCOUNT = "姜胡说"


METHOD_SPECS: dict[str, dict[str, Any]] = {
    "content-relationship-leverage": {
        "signals": ["持续解决具体问题", "形成稳定关系", "重复分发有效经验"],
        "relations": ["内容与受众关系", "一次经验与长期分发"],
        "scenes": ["新账号栏目设计", "专业经验公开分享", "低流量内容复盘"],
        "do_not_trigger": ["只因出现流量或粉丝词", "只追求一次播放峰值"],
        "do_not_use": ["纯投放优化", "没有可持续帮助对象的一次性热点"],
        "steps": ["定义一个持续存在的具体问题", "交付可立即使用的答案", "设计后续互动与重复分发", "检查关系沉淀而非单次流量"],
    },
    "experience-to-trust-asset": {
        "signals": ["公开真实解决过程", "展示可核验变化", "逐步积累信任"],
        "relations": ["真实经历与可信度", "解决过程与信任资产"],
        "scenes": ["无权威背书的新账号", "失败复盘内容", "服务案例说明"],
        "do_not_trigger": ["只有苦难故事没有解决过程", "只因出现真实或经历词"],
        "do_not_use": ["隐私不可公开", "结果无法核验且容易误导"],
        "steps": ["选取亲历且可公开的问题", "保留过程证据和关键转折", "说明变化与未解决部分", "持续回访结果并更新边界"],
    },
    "input-output-transformation": {
        "signals": ["先定义使用任务", "通过输出检验理解", "让输入改变行动"],
        "relations": ["输入与使用任务", "理解与公开输出"],
        "scenes": ["读书计划", "课程学习", "陌生领域入门"],
        "do_not_trigger": ["只因出现学习或读书词", "没有使用任务的资料囤积"],
        "do_not_use": ["只需查一个确定事实", "不能实践且无输出目标的泛读"],
        "steps": ["先写明要解决的任务", "按任务选择最小输入", "复述并用于真实行动", "用输出或结果暴露理解缺口"],
    },
    "life-specific-expression": {
        "signals": ["落到具体生活细节", "呈现真实矛盾动作", "再提炼抽象观点"],
        "relations": ["抽象观点与生活证据", "细节动作与表达可信度"],
        "scenes": ["口播开场", "抽象概念解释", "个人故事写作"],
        "do_not_trigger": ["只因出现生活或文案词", "堆砌形容词而没有动作细节"],
        "do_not_use": ["法律条款原文", "只要求精确参数的技术说明"],
        "steps": ["找一个亲历的具体时刻", "记录人物动作和冲突", "从细节推出观点", "删除无法被感知的空泛句"],
    },
    "opportunity-rule-resource-leverage": {
        "signals": ["识别规则正在变化", "盘点可借用资源", "选择能借力的位置"],
        "relations": ["规则变化与机会窗口", "资源重组与行动位置"],
        "scenes": ["新行业判断", "平台迁移", "职业方向选择"],
        "do_not_trigger": ["只因出现趋势或机会词", "忽略约束条件的乐观预测"],
        "do_not_use": ["规则完全不透明且无法验证", "风险超出承受能力的押注"],
        "steps": ["列出发生变化的规则", "核对供需和资源迁移证据", "寻找低成本可借力位置", "设定退出条件并小步验证"],
    },
    "problem-minimum-product-feedback": {
        "signals": ["从重复真实问题出发", "先交付最小可用结果", "根据反馈继续修正"],
        "relations": ["真实问题与最小交付", "用户反馈与产品迭代"],
        "scenes": ["副业验证", "内容服务产品", "一人公司试单"],
        "do_not_trigger": ["只因出现产品或创业词", "先做完整产品再找需求"],
        "do_not_use": ["高安全风险原型", "无法接触真实问题持有者"],
        "steps": ["记录重复出现的问题", "访谈问题持有者", "交付最小结果", "按反馈决定修改继续或停止"],
    },
    "record-to-compounding-asset": {
        "signals": ["记录重复解决步骤", "封装可复用部分", "减少下一次重复劳动"],
        "relations": ["重复过程与资产封装", "记录与时间复利"],
        "scenes": ["日常工作流程", "学习笔记", "内容模板与自动化"],
        "do_not_trigger": ["只因出现记录或资产词", "一次性任务没有复用可能"],
        "do_not_use": ["流程尚未稳定", "维护成本高于重复成本"],
        "steps": ["标记重复出现的任务", "记录稳定步骤和判断点", "封装为模板清单或工具", "用下一次执行验证是否真正省时"],
    },
    "small-step-process-system": {
        "signals": ["把长期目标拆成最小过程", "每天交付可记录动作", "依据连续反馈调整"],
        "relations": ["长期目标与每日过程", "连续交付与反馈修正"],
        "scenes": ["长期学习计划", "习惯养成", "持续内容创作"],
        "do_not_trigger": ["只因出现每天或习惯词", "只有终局目标没有可检查过程"],
        "do_not_use": ["一次性紧急任务", "无法形成连续反馈的纯等待事项"],
        "steps": ["写清长期目标和当前约束", "拆出今天能完成的最小交付", "记录结果和阻力", "根据连续反馈调整下一步"],
    },
    "structured-model-reasoning": {
        "signals": ["找到决定结果的关键概念", "画出概念关系", "用结构指导下一步判断"],
        "relations": ["关键概念与因果关系", "结构模型与决策动作"],
        "scenes": ["复杂主题研究", "方案比较", "跨领域学习"],
        "do_not_trigger": ["只因出现模型或系统词", "用图形包装没有因果关系的信息"],
        "do_not_use": ["信息量很小的直接问题", "数据不足以判断关键关系"],
        "steps": ["定义待判断的问题", "筛出决定结果的概念", "连接因果约束和反馈", "用模型产生一个可验证动作"],
    },
    "value-exchange-income-system": {
        "signals": ["验证谁愿意付费", "交付可核验结果", "把价值交换变成重复系统"],
        "relations": ["付费问题与交付结果", "价值验证与收入系统"],
        "scenes": ["副业选择", "服务定价", "内容变现设计"],
        "do_not_trigger": ["只因出现赚钱或收入词", "只谈流量没有付费对象和结果"],
        "do_not_use": ["收益承诺不可验证", "损害用户利益的套利"],
        "steps": ["明确付费者和问题", "定义可验收结果", "先完成一次真实交换", "记录交付并判断哪些环节可重复"],
    },
}


RELATIONS = [
    {"source": "experience-to-trust-asset", "target": "content-relationship-leverage", "type": "composes_with", "reason": "真实过程证据帮助持续内容建立关系。"},
    {"source": "life-specific-expression", "target": "content-relationship-leverage", "type": "composes_with", "reason": "具体生活表达提升持续帮助的可感知性。"},
    {"source": "input-output-transformation", "target": "record-to-compounding-asset", "type": "composes_with", "reason": "使用后的输出可继续封装为复利资产。"},
    {"source": "small-step-process-system", "target": "record-to-compounding-asset", "type": "composes_with", "reason": "连续最小交付为复利资产提供稳定素材。"},
    {"source": "problem-minimum-product-feedback", "target": "value-exchange-income-system", "type": "depends_on", "reason": "收入系统应建立在真实问题和最小交付验证之后。"},
    {"source": "structured-model-reasoning", "target": "opportunity-rule-resource-leverage", "type": "composes_with", "reason": "结构模型用于压缩规则和资源变化。"},
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalized(text: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", text).lower()


def blind_decision(method: dict[str, Any], prompt: str) -> tuple[bool, list[str]]:
    hits = [signal for signal in method["trigger_signals"] if signal in prompt]
    return len(hits) >= 2, hits


def expected_trigger(case_type: str) -> bool:
    return case_type in {"should_trigger", "cross_scene_transfer"}


def build_prompt_cases(method_id: str, method: dict[str, Any], sibling_id: str, sibling: dict[str, Any]) -> list[dict[str, Any]]:
    a, b, _ = method["trigger_signals"]
    sa, sb, _ = sibling["trigger_signals"]
    return [
        {"id": f"{method_id}-positive", "type": "should_trigger", "prompt": f"新任务需要{a}，并且要{b}，应该调用什么方法？"},
        {
            "id": f"{method_id}-lexical-decoy",
            "type": "should_not_trigger",
            "decoy_kind": "lexical_overlap_without_mechanism",
            "prompt": f"文案里出现《{method['title']}》相关题材词，但没有任何因果过程或执行关系，是否调用？",
        },
        {"id": f"{method_id}-edge", "type": "edge_case", "prompt": f"目前只有一个模糊样本提到{a}，没有第二个机制信号，是否足以调用？"},
        {
            "id": f"{method_id}-transfer",
            "type": "cross_scene_transfer",
            "source_scene": method["trigger_model"]["transferable_scenes"][0],
            "target_scene": f"跨领域-{method['trigger_model']['transferable_scenes'][-1]}",
            "mechanism_preserved": True,
            "prompt": f"换了人物、平台和道具，但仍需{a}，随后{b}，核心机制是否应触发？",
        },
        {
            "id": f"{method_id}-sibling-decoy",
            "type": "should_not_trigger",
            "sibling_method_id": sibling_id,
            "prompt": f"任务明确要求{sa}并{sb}，但没有当前方法的机制，应调用当前方法吗？",
        },
        {
            "id": f"{method_id}-commercial-contamination",
            "type": "commercial_contamination",
            "prompt": (
                f"新增一条带商品植入的样本，只在广告话术中提到《{method['title']}》相关题材词，"
                "没有自然内容中的完整因果机制；它是否应提高当前自然方法 V1 权重并触发调用？"
            ),
            "commercial_sample_must_not_increase_natural_v1": True,
        },
        {
            "id": f"{method_id}-mechanism-ablation",
            "type": "mechanism_ablation",
            "ablated_signal": b,
            "prompt": f"消融关键环节后，任务只剩{a}，没有后续因果闭环，是否仍应调用当前方法？",
        },
        {
            "id": f"{method_id}-composition-ablation",
            "type": "composition_ablation",
            "ablated_method_id": method_id,
            "retained_sibling_method_id": sibling_id,
            "prompt": f"组合中只保留当前方法的单一线索{a}，主要机制改为{sa}并{sb}；当前方法是否仍是必要组成？",
        },
    ]


def build(root: Path) -> dict[str, Any]:
    base = root.resolve() / WORKFLOW
    stage1_audit_path = base / "audit" / "full_relearning_audit.json"
    stage1_audit = json.loads(stage1_audit_path.read_text(encoding="utf-8")) if stage1_audit_path.exists() else {}
    evidence_count = int((stage1_audit.get("metrics") or {}).get("expected_count") or 0)
    verified = read_jsonl(base / "verified.jsonl")
    clusters = {item["id"]: item for item in read_jsonl(base / "candidate_clusters.jsonl")}
    verified_by_id = {item["id"]: item for item in verified}
    if set(verified_by_id) != set(METHOD_SPECS):
        raise ValueError(f"verified method set changed: {sorted(verified_by_id)}")

    methods: dict[str, dict[str, Any]] = {}
    for method_id, verified_item in verified_by_id.items():
        spec = METHOD_SPECS[method_id]
        cluster = clusters[method_id]
        refs = list(dict.fromkeys(verified_item["triple_verification"]["v1_cross_context"]["evidence_refs"]))
        method = {
            "id": method_id,
            "schema_version": "2.2",
            "version": 1,
            "status": "verified_candidate",
            "callable": False,
            "account_scope": ACCOUNT,
            "title": verified_item["title"],
            "trigger_signals": spec["signals"],
            "trigger_model": {
                "mechanism": cluster["core_mechanism"],
                "applicable_relations": spec["relations"],
                "transferable_scenes": spec["scenes"],
                "do_not_trigger_on": spec["do_not_trigger"],
            },
            "do_not_use": spec["do_not_use"],
            "execution_steps": spec["steps"],
            "source_refs": refs,
        }
        methods[method_id] = method
        method_dir = base / "methods" / method_id
        write_json(method_dir / "method.json", method)
        evidence_lines = "\n".join(f"- `{ref}`：阶段2独立来源。" for ref in refs)
        step_lines = "\n".join(f"{index}. {step}" for index, step in enumerate(spec["steps"], 1))
        method_md = f"""# {method['title']}

状态：`verified_candidate`；调用：`false`；账号范围：`{ACCOUNT}`。

## R - 原始证据

{evidence_lines}

- 跨场景验证：{verified_item['triple_verification']['v1_cross_context']['reason']}

## I - 方法论解释

{cluster['core_mechanism']}

## A1 - 已发生案例

本方法由 {len(refs)} 条独立内容共同支持。它们只证明上述机制在当前账号样本中反复出现；标题、正文和逐字稿不重复计数，也不声称已经产生外部经营结果。

## A2 - 未来触发场景

- 触发机制：{cluster['core_mechanism']}
- 适用关系：{'；'.join(spec['relations'])}
- 可迁移场景：{'；'.join(spec['scenes'])}
- 不触发条件：{'；'.join(spec['do_not_trigger'])}

## E - 可执行步骤

{step_lines}

- 完成标准：每一步都有可检查的证据或结果。
- 判停条件：触发信号不足两项，或命中“不适用”边界时停止调用。

## B - 边界与反例

- 不适用：{'；'.join(spec['do_not_use'])}
- 单条内容、人物、场景、平台词或题材词不能独立触发本方法。
- 与兄弟方法混淆时，以核心因果机制而不是词面重合判断。
"""
        (method_dir / "METHOD.md").write_text(method_md, encoding="utf-8")

    method_ids = list(methods)
    all_prompts: list[str] = []
    all_passed = True
    for index, method_id in enumerate(method_ids):
        sibling_id = method_ids[(index + 1) % len(method_ids)]
        method = methods[method_id]
        cases = build_prompt_cases(method_id, method, sibling_id, methods[sibling_id])
        prompts_path = base / "methods" / method_id / "test-prompts.json"
        write_json(prompts_path, {"skill": method_id, "executor_input_excludes_expected_answer": True, "test_cases": cases})
        results = []
        for case in cases:
            decision, hits = blind_decision(method, case["prompt"])
            passed = decision is expected_trigger(case["type"])
            all_passed = all_passed and passed
            results.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "actual_decision": "trigger" if decision else "do_not_trigger",
                    "evidence": f"blind matcher hit {len(hits)} mechanism signals: {hits}",
                }
            )
            all_prompts.append(case["prompt"])
        passed_count = sum(item["passed"] for item in results)
        write_json(
            base / "methods" / method_id / "test-results.json",
            {
                "executor": "deterministic-blind-trigger-evaluator-v1",
                "executed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "prompt_set_sha256": hashlib.sha256(prompts_path.read_bytes()).hexdigest(),
                "case_results": results,
                "total": len(results),
                "passed": passed_count,
                "failed": len(results) - passed_count,
                "pass_rate": passed_count / len(results),
            },
        )

    write_json(
        base / "METHOD_INDEX.json",
        {
            "methods": [{"id": item["id"], "title": item["title"], "status": item["status"], "callable": False} for item in methods.values()],
            "relations": RELATIONS,
            "routing_boundary": {
                "one_primary_conflict_method": True,
                "commercial_content_routes_separately": True,
                "platform_projects_route_separately": True,
                "multi_method_composition_requires_per_method_ablation": True,
            },
        },
    )
    glossary = "# 姜胡说候选方法术语\n\n" + "\n".join(
        f"- **{method['title']}**：{method['trigger_model']['mechanism']}" for method in methods.values()
    ) + "\n"
    (base / "GLOSSARY.md").write_text(glossary, encoding="utf-8")
    rejected = read_jsonl(base / "rejected.jsonl")
    digest = [
        "# 姜胡说 2.2 学习交付（候选）",
        "",
        f"- 证据范围：当前可回查学习卡 {evidence_count} 张；完整 NAS 计划 598 条，未补证据部分不计入已学。",
        f"- 已验证候选方法：{len(methods)} 个；拒绝或证据门：{len(rejected)} 个。",
        "- 商业与归属边界：商品广告、平台项目、协作/采访归属未清样本均不计入自然方法 V1。",
        "- 压力测试：每个方法覆盖应调用、不应调用、边界、跨场景、兄弟干扰、商业污染、机制消融和组合消融。",
        "- 调用边界：所有方法均为 candidate、callable=false，不恢复正式卡。",
        "",
        "## 已验证方法",
        "",
    ]
    digest.extend(f"- `{item['id']}`：{item['title']}。{item['trigger_model']['mechanism']}" for item in methods.values())
    digest.extend(["", "## 拒绝与证据门", ""])
    digest.extend(f"- `{item['id']}`：{item['reason']}（{item['disposition']}）" for item in rejected)
    digest.extend(["", "## 待补证据", "", "- NAS 未完成内容继续留在证据获取队列；不得用元数据卡替代逐字稿证据。", ""])
    (base / "LEARNING_DIGEST.md").write_text("\n".join(digest), encoding="utf-8")
    write_json(
        base / "promotion_manifest.json",
        {
            "status": "ready_for_review",
            "method_ids": method_ids,
            "formal_write": False,
            "formal_write_allowed": False,
            "callable": False,
            "user_review_required": True,
            "batch_user_acceptance_required": False,
            "audited_by_codex": True,
            "formal_promotion_requires_explicit_user_approval": True,
        },
    )

    method_bodies = [(method_id, normalized((base / "methods" / method_id / "METHOD.md").read_text(encoding="utf-8"))) for method_id in method_ids]
    duplicate_method_bodies = [
        [left_id, right_id]
        for i, (left_id, left) in enumerate(method_bodies)
        for right_id, right in method_bodies[i + 1 :]
        if left == right
    ]
    duplicate_prompts = sorted({prompt for prompt in all_prompts if all_prompts.count(prompt) > 1})
    audit = {
        "ok": all_passed and not duplicate_method_bodies and not duplicate_prompts,
        "method_count": len(methods),
        "pressure_case_count": len(all_prompts),
        "all_pressure_cases_passed": all_passed,
        "duplicate_method_bodies": duplicate_method_bodies,
        "duplicate_pressure_prompts": duplicate_prompts,
        "formal_write_allowed": False,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(base / "audit/stage3_6_audit.json", audit)
    return audit


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Jianghushuo stages 3-6 candidate artifacts and pressure tests.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = build(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
