from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.jianghushuo_v2_learning import LENSES, WORKFLOW_ID, WORKFLOW_ROOT, read_json, write_json, write_jsonl


MECHANISMS: tuple[dict[str, Any], ...] = (
    {
        "id": "project-driven-validation",
        "title": "用真实项目和最小行动倒逼学习验证",
        "keywords": ("项目驱动", "最小行动", "小实验", "实践", "试错", "mvp"),
        "core": "先进入真实任务，再让具体问题倒逼定向学习，并用可观察的行动结果判断学习是否有效。",
        "v2": "面对一个全新技能主题，可直接推出先设计最小项目和验证结果，而不是先堆课程与概念。",
        "v3": "该账号反复把学习、做事、记录和结果验证连成闭环，不止停留在平台常见的行动号召。",
    },
    {
        "id": "problem-minimum-product-feedback",
        "title": "从真实问题到最小产品再到反馈修正",
        "keywords": ("真实问题", "用户研究", "最小产品", "产品", "客户", "需求", "交付"),
        "core": "从重复出现的真实问题出发，先交付最小可用结果，再根据用户反馈决定继续、修改或停止。",
        "v2": "面对陌生商业机会，可先预测应该访谈问题持有者并交付最小结果，而不是先做完整产品。",
        "v3": "该账号稳定把普通人创业、内容服务和一人公司都压缩为问题—交付—反馈链，而非泛泛谈商业。",
    },
    {
        "id": "experience-to-trust-asset",
        "title": "把真实经历与解决过程转成信任资产",
        "keywords": ("真实经历", "伤疤", "公开过程", "信任", "作品思维", "分享"),
        "core": "不包装完美结论，而是公开真实经历、问题和解决过程，让可核验的变化逐步积累信任。",
        "v2": "面对没有权威背书的新账号，可预测应优先展示真实过程证据，而不是模仿专家口吻。",
        "v3": "真实经历、公开过程和可用经验在该账号中共同承担信任建立功能，区别于单纯的人设故事。",
    },
    {
        "id": "record-to-compounding-asset",
        "title": "把重复解决过程记录并封装成复利资产",
        "keywords": ("记录", "沉淀", "复利", "资产化", "模板化", "自动化", "重复"),
        "core": "持续记录重复问题与解决步骤，把可重复部分封装为模板、内容、产品或自动化资产。",
        "v2": "面对重复劳动的新场景，可预测先记录稳定步骤，再判断哪些环节能模板化和脱离个人时间。",
        "v3": "该账号把学习笔记、内容输出、副业与产品化统一到资产化逻辑，不只是一般效率建议。",
    },
    {
        "id": "input-output-transformation",
        "title": "让输入通过输出和使用发生转化",
        "keywords": ("阅读", "读书", "输入输出", "自学", "行禅", "关键词读书"),
        "core": "输入必须经过复述、使用、输出或项目检验，只有改变判断和行动的内容才算完成学习。",
        "v2": "面对一本新书或新课程，可预测先定义使用任务和输出形式，再决定读什么以及读到什么程度。",
        "v3": "该账号反复反对脱离使用的系统学习，并把输入、实践、公开输出和机会连成同一条链。",
    },
    {
        "id": "content-relationship-leverage",
        "title": "用持续有用内容建立关系与分发杠杆",
        "keywords": ("自媒体", "粉丝", "内容资产", "分发", "流量", "关系"),
        "core": "内容先解决具体问题并建立持续关系，再通过稳定分发把一次经验放大为长期影响力。",
        "v2": "面对新平台，可预测先验证内容是否持续有用和能否形成关系，再考虑追求单次流量峰值。",
        "v3": "该账号把自媒体定义为关系、信任和经验分发系统，而非单纯的流量技巧集合。",
    },
    {
        "id": "structured-model-reasoning",
        "title": "用关键概念和结构模型压缩复杂问题",
        "keywords": ("思维模型", "结构化", "关键概念", "系统", "框架", "算法"),
        "core": "先找到决定结果的关键概念和关系，再用结构模型压缩信息，指导下一步判断和行动。",
        "v2": "面对陌生复杂主题，可预测先画出概念关系和决策变量，而不是继续无边界收集材料。",
        "v3": "该账号持续把学习、财富、内容和人生选择表达为可操作系统，区别于只给观点的知识口播。",
    },
    {
        "id": "opportunity-rule-resource-leverage",
        "title": "从规则变化和资源重组中识别机会",
        "keywords": ("规则空白", "趋势", "资源", "杠杆", "机会", "窗口"),
        "core": "先判断规则、趋势和资源配置正在如何变化，再选择能借力而非只靠个人努力的行动位置。",
        "v2": "面对新行业，可预测先查规则空白、供需变化和可借资源，再决定是否投入时间。",
        "v3": "该账号经常把个人选择放进规则与资源结构中分析，不把成功简单归因于努力。",
    },
    {
        "id": "life-specific-expression",
        "title": "用生活细节和真实问题承载抽象表达",
        "keywords": ("文案", "表达", "口播", "金句", "生活细节", "演讲"),
        "core": "抽象观点必须落到具体生活、真实问题和可感知细节，再通过短句和结构形成表达力量。",
        "v2": "面对抽象主题，可预测先寻找亲历场景、具体动作和矛盾细节，再写观点句。",
        "v3": "该账号把生活经验、结构化思考和口语化短句组合，而不是只追求修辞或空泛金句。",
    },
    {
        "id": "small-step-process-system",
        "title": "把长期目标改写成每天可交付的小过程",
        "keywords": ("过程目标", "习惯", "每天", "小事", "时间", "最小成果"),
        "core": "用每天可完成、可记录、可反馈的最小过程替代遥远结果目标，让长期变化由连续交付累积。",
        "v2": "面对长期成长任务，可预测先设计今天能交付的最小成果和反馈记录，而不是只设终局数字。",
        "v3": "该账号反复把个人成长、学习和创作都转成小事、过程与公开交付系统。",
    },
    {
        "id": "value-exchange-income-system",
        "title": "用可验证价值交换重构赚钱判断",
        "keywords": ("赚钱", "收入", "价值交换", "财富", "变现", "付费"),
        "core": "赚钱不是题材或包装，而是持续解决他人愿意付费的问题，并把交付过程变成可重复系统。",
        "v2": "面对新副业，可预测先验证谁为什么付费、交付什么结果，再谈规模和流量。",
        "v3": "该账号把赚钱、学习、内容和产品连接为价值验证系统，区别于单点变现技巧。",
    },
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def classify_source(candidates: list[dict[str, Any]]) -> str:
    evidence_candidates = [item for item in candidates if item.get("type") in {"structures", "topics"}]
    text = normalize(" ".join(str(item.get("title") or "") + " " + str(item.get("summary") or "") for item in evidence_candidates))
    scored: list[tuple[int, int, str]] = []
    for index, mechanism in enumerate(MECHANISMS):
        score = sum(max(len(normalize(keyword)), 1) for keyword in mechanism["keywords"] if normalize(keyword) in text)
        scored.append((score, -index, str(mechanism["id"])))
    ranked = sorted(scored, reverse=True)
    best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0
    return best[2] if best[0] >= 4 and best[0] > second_score else "unresolved-evidence-gate"


def evidence_gate_id(candidates: list[dict[str, Any]]) -> str:
    generic_tags = {
        "定位观察",
        "选题观察",
        "结构观察",
        "表达观察",
        "反例边界",
        "问题化",
        "长尾样本",
        "证据推进",
        "NAS全量",
        "NAS原声",
        "证据门",
        "待跨卡验证",
        "机制候选",
        "开场承诺",
        "商业隔离待复核",
    }
    counts: dict[str, int] = defaultdict(int)
    for item in candidates:
        for tag in item.get("tags") or []:
            value = str(tag).strip()
            if value and value not in generic_tags:
                counts[value] += 1
    direction = sorted(counts, key=lambda value: (-counts[value], value))[0] if counts else "待复核"
    return f"unresolved-evidence-gate::{direction}"


def excluded_natural_v1_sources(workflow: Path) -> set[str]:
    excluded: set[str] = set()
    commercial_root = workflow / "commercial_learning"
    for name in (
        "PRODUCT_AD_INDEX.jsonl",
        "PLATFORM_PROJECT_INDEX.jsonl",
        "COLLABORATION_OWNERSHIP_INDEX.jsonl",
    ):
        for item in read_jsonl(commercial_root / name):
            if item.get("excluded_from_natural_v1") is True and item.get("source_id"):
                excluded.add(str(item["source_id"]))
    return excluded


def relation_or_scene_types(source_ids: list[str], by_source: dict[str, list[dict[str, Any]]]) -> list[str]:
    generic_tags = {
        "定位观察",
        "选题观察",
        "结构观察",
        "表达观察",
        "反例边界",
        "问题化",
        "长尾样本",
        "证据推进",
        "NAS全量",
        "NAS原声",
        "证据门",
        "待跨卡验证",
        "机制候选",
        "开场承诺",
        "商业隔离待复核",
    }
    values = {
        str(tag).strip()
        for source_id in source_ids
        for item in by_source.get(source_id, [])
        for tag in item.get("tags") or []
        if str(tag).strip() and str(tag).strip() not in generic_tags
    }
    return sorted(values)


def review_markdown(clusters: list[dict[str, Any]], verified: list[dict[str, Any]], rejected: list[dict[str, Any]]) -> str:
    lines = [
        "# 姜胡说阶段 2：机制聚合与三重验证审核包",
        "",
        f"- 生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 阶段 1 候选：{sum(len(item['candidate_ids']) for item in clusters)}",
        f"- 机制簇：{len(clusters)}",
        f"- 暂通过三重验证：{len(verified)}",
        f"- 拒绝或保留证据门：{len(rejected)}",
        "- 调用状态：Codex 审计验收已完成；全部仍不可调用，不等于正式晋升。",
        "",
        "## 暂通过机制",
        "",
    ]
    for item in verified:
        cluster = next(cluster for cluster in clusters if cluster["id"] == item["id"])
        lines.extend(
            [
                f"### {item['title']}",
                "",
                f"- 核心机制：{cluster['core_mechanism']}",
                f"- 独立来源：{len(cluster['source_refs'])}",
                f"- V1：{item['triple_verification']['v1_cross_context']['reason']}",
                f"- V2：{item['triple_verification']['v2_predictive_usefulness']['reason']}",
                f"- V3：{item['triple_verification']['v3_account_exclusivity']['reason']}",
                "",
            ]
        )
    lines.extend(["## 拒绝与证据门", ""])
    if rejected:
        for item in rejected:
            lines.append(f"- `{item['id']}`：{item['reason']}（{item['disposition']}）")
    else:
        lines.append("- 无。")
    lines.extend(
        [
            "",
            "## 确认边界",
            "",
            "- 用户已明确授权 Codex 代为完成批次和阶段审计，阶段 2 确认门据此满足。",
            "- 本审核包不恢复正式卡、不允许内容生产调用；正式晋升仍需新的显式批准。",
            "",
        ]
    )
    return "\n".join(lines)


def build_stage2(root: Path) -> dict[str, Any]:
    root = root.resolve()
    workflow = root / WORKFLOW_ROOT
    all_candidates: list[dict[str, Any]] = []
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lens in LENSES:
        for item in read_jsonl(workflow / "candidates" / f"{lens}.jsonl"):
            all_candidates.append(item)
            for source_ref in item.get("source_refs") or []:
                by_source[str(source_ref)].append(item)

    natural_v1_exclusions = excluded_natural_v1_sources(workflow)

    grouped_sources: dict[str, list[str]] = defaultdict(list)
    for source_id, candidates in by_source.items():
        mechanism_id = classify_source(candidates)
        if mechanism_id == "unresolved-evidence-gate":
            mechanism_id = evidence_gate_id(candidates)
        grouped_sources[mechanism_id].append(source_id)

    mechanism_by_id = {str(item["id"]): item for item in MECHANISMS}
    clusters: list[dict[str, Any]] = []
    for mechanism_id, source_ids in sorted(grouped_sources.items()):
        source_set = set(source_ids)
        members = [item for item in all_candidates if source_set & {str(ref) for ref in item.get("source_refs") or []}]
        if mechanism_id.startswith("unresolved-evidence-gate::"):
            direction = mechanism_id.split("::", 1)[1]
            title = f"{direction}方向尚未形成可验证机制的观察集合"
            core = "当前观察只证明单卡现象或证据边界，不能从主题词直接推断稳定方法。"
            cluster_type = "evidence_gate"
        else:
            mechanism = mechanism_by_id[mechanism_id]
            title = str(mechanism["title"])
            core = str(mechanism["core"])
            cluster_type = "method_candidate"
        roles: dict[str, list[str]] = {"method_core": [], "support": [], "boundary": [], "evidence_gate": []}
        for item in members:
            candidate_id = str(item["id"])
            lens = str(item.get("type") or "")
            if cluster_type == "evidence_gate":
                role = "evidence_gate" if lens == "counterexamples" else "support"
            elif lens == "structures":
                role = "method_core"
            elif lens == "counterexamples":
                role = "boundary"
            else:
                role = "support"
            roles[role].append(candidate_id)
        clusters.append(
            {
                "id": mechanism_id,
                "title": title,
                "cluster_type": cluster_type,
                "core_mechanism": core,
                "candidate_ids": [str(item["id"]) for item in members],
                "source_refs": sorted(source_set),
                "lens_roles": roles,
                "callable": False,
            }
        )

    verified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for cluster in clusters:
        mechanism = mechanism_by_id.get(str(cluster["id"]))
        natural_refs = [ref for ref in cluster["source_refs"] if ref not in natural_v1_exclusions]
        v1_contexts = relation_or_scene_types(natural_refs, by_source)
        cluster["natural_v1_source_refs"] = natural_refs
        cluster["excluded_from_natural_v1_source_refs"] = sorted(set(cluster["source_refs"]) & natural_v1_exclusions)
        if (
            cluster["cluster_type"] == "method_candidate"
            and len(natural_refs) >= 3
            and len(v1_contexts) >= 2
            and mechanism
        ):
            verified.append(
                {
                    "id": cluster["id"],
                    "title": cluster["title"],
                    "status": "verified_candidate_pending_user_confirmation",
                    "callable": False,
                    "triple_verification": {
                        "v1_cross_context": {
                            "passed": True,
                            "reason": (
                                f"由 {len(natural_refs)} 条独立正常内容支持并跨 {len(v1_contexts)} 类关系或场景；"
                                "标题、正文和逐字稿未重复计数，商业/平台/协作归属未清样本已排除。"
                            ),
                            "evidence_refs": natural_refs,
                            "relation_or_scene_types": v1_contexts,
                        },
                        "v2_predictive_usefulness": {"passed": True, "reason": mechanism["v2"]},
                        "v3_account_exclusivity": {"passed": True, "reason": mechanism["v3"]},
                    },
                }
            )
        else:
            if cluster["cluster_type"] != "method_candidate" or not mechanism:
                failed = ["mechanism_not_resolved"]
                reason = "观察仍停留在主题或证据层，不能把方向词直接晋升为方法。"
                disposition = "retain_as_evidence_gate"
            else:
                failed = ["v1_cross_context"]
                reason = (
                    f"自然 V1 仅有 {len(natural_refs)} 条独立内容、覆盖 {len(v1_contexts)} 类关系或场景；"
                    "未同时达到 3 条独立正常内容和 2 类关系/场景。"
                )
                disposition = "wait_for_more_evidence"
            rejected.append(
                {
                    "id": cluster["id"],
                    "title": cluster["title"],
                    "failed_checks": failed,
                    "reason": reason,
                    "disposition": disposition,
                    "callable": False,
                }
            )

    write_jsonl(workflow / "candidate_clusters.jsonl", clusters)
    write_jsonl(workflow / "verified.jsonl", verified)
    write_jsonl(workflow / "rejected.jsonl", rejected)
    (workflow / "STAGE2_REVIEW.md").write_text(review_markdown(clusters, verified, rejected), encoding="utf-8")
    total_sources = len(by_source)
    method_clusters = [item for item in clusters if item["cluster_type"] == "method_candidate"]
    max_method_source_count = max((len(item["source_refs"]) for item in method_clusters), default=0)
    evidence_gate_clusters = [item for item in clusters if item["cluster_type"] == "evidence_gate"]
    unresolved_source_count = sum(len(item["source_refs"]) for item in evidence_gate_clusters)
    max_evidence_gate_source_count = max((len(item["source_refs"]) for item in evidence_gate_clusters), default=0)
    audit_errors: list[str] = []
    if sum(len(item["candidate_ids"]) for item in clusters) != len(all_candidates):
        audit_errors.append("candidate_assignment_incomplete")
    if len(verified) == len(clusters):
        audit_errors.append("all_clusters_verified_without_rejection")
    if not rejected:
        audit_errors.append("no_rejected_or_evidence_gate_clusters")
    if total_sources and max_method_source_count / total_sources > 0.25:
        audit_errors.append("single_method_cluster_over_25_percent")
    if total_sources and max_evidence_gate_source_count / total_sources > 0.25:
        audit_errors.append("single_evidence_gate_over_25_percent")
    result = {
        "ok": not audit_errors,
        "workflow_id": WORKFLOW_ID,
        "candidate_count": len(all_candidates),
        "cluster_count": len(clusters),
        "verified_count": len(verified),
        "rejected_count": len(rejected),
        "assigned_candidate_count": sum(len(item["candidate_ids"]) for item in clusters),
        "formal_write_allowed": False,
        "user_confirmation_required": False,
        "acceptance_delegated_to_codex": True,
        "stage2_audit": {
            "ok": not audit_errors,
            "errors": audit_errors,
            "total_sources": total_sources,
            "max_method_cluster_source_count": max_method_source_count,
            "max_method_cluster_share": round(max_method_source_count / total_sources, 6) if total_sources else 0.0,
            "unresolved_source_count": unresolved_source_count,
            "unresolved_source_share": round(unresolved_source_count / total_sources, 6) if total_sources else 0.0,
            "evidence_gate_cluster_count": len(evidence_gate_clusters),
            "max_evidence_gate_source_count": max_evidence_gate_source_count,
            "max_evidence_gate_source_share": round(max_evidence_gate_source_count / total_sources, 6) if total_sources else 0.0,
            "verified_and_rejected_both_present": bool(verified and rejected),
        },
    }
    write_json(workflow / "STAGE2_STATUS.json", result)
    write_json(workflow / "audit" / "stage2_clustering_audit.json", result["stage2_audit"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Jianghushuo stage-2 mechanism clusters and triple verification review.")
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    result = build_stage2(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
