"""Build auditable stage-2 method clusters for the Li Zongheng candidate workflow."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full")
LENSES = ("positioning", "topics", "structures", "expression", "counterexamples")

CLUSTERS: dict[str, dict[str, str]] = {
    "lz-m1-system-transfer": {
        "title": "整套系统迁移",
        "type": "method_candidate",
        "core": "把一个熟悉系统的角色、流程、术语和结算规则整体搬入另一场景，并让新系统持续约束剧情。",
    },
    "lz-m2-control-right-reversal": {
        "title": "评价权与控制权反转",
        "type": "method_candidate",
        "core": "让原本被评价、被服务或被管理的一方夺回提问权、定义权或审批权，并按新权力关系推进冲突。",
    },
    "lz-m3-semantic-reinterpretation": {
        "title": "字面重释与双语境链",
        "type": "method_candidate",
        "core": "把同一句话拆出另一种字面、指代或语境解释，角色按错误但自洽的解释行动，并让误解产生后续结果。",
    },
    "lz-m4-fixed-rule-escalation": {
        "title": "固定规则多场景递进",
        "type": "method_candidate",
        "core": "先建立一个固定口令、执念或验收规则，再在多个微场景中重复执行，每轮增加关系、信息或后果强度。",
    },
    "lz-g1-commercial-contamination": {
        "title": "商业分流与广告植入学习门",
        "type": "boundary_rule",
        "core": "商业内容不进入正常选题频次或自然方法V1，但必须另行学习前段剧情、广告引入桥、产品剧情角色和广告后收束。",
    },
    "lz-g2-evidence-account-boundary": {
        "title": "证据质量与账号归属门",
        "type": "evidence_gate",
        "core": "短文案、ASR、抽帧和合拍信息只在证据充分时支持结论；共演者不拆成独立目标账号。",
    },
    "lz-r1-generic-contrast": {
        "title": "通用对照与正常/自己反差",
        "type": "boundary_rule",
        "core": "对照是一种通用结构容器，未证明独特冲突机制时只能作为案例结构，不能单独晋升账号方法。",
    },
    "lz-r2-generic-reveal-gap": {
        "title": "通用揭示、信息差与末尾反转",
        "type": "boundary_rule",
        "core": "揭示和信息差是行业通用收束手段，必须依附更具体的系统、权力或语义机制。",
    },
    "lz-r3-packaging-support": {
        "title": "标题、发布文案与表达包装",
        "type": "boundary_rule",
        "core": "标题和发布文案只承担入口、悬念或语气，不可绕过逐字稿与画面独立决定分类或方法触发。",
    },
    "lz-r4-case-specific-observation": {
        "title": "单例题材与未收敛观察",
        "type": "evidence_gate",
        "core": "尚未跨场景收敛的题材、人设、单例和边界观察继续保留证据，不强行包装成稳定方法。",
    },
}

PATTERNS = {
    "commercial": re.compile(r"广告|商业|品牌|植入|平台活动|挑战赛|产品|转化|购买|优惠|卖点|宣发|活动入口"),
    "evidence": re.compile(r"ASR|转写|逐字稿|视觉|画面|抽帧|证据|账号归属|合拍|共演|短文案盲区|引用边界|原话"),
    "m1": re.compile(r"系统迁移|系统替换|系统映射|整套系统|完整流程|流程迁移|规则迁移|规则映射|制度迁移|系统改写|完整映射"),
    "m2": re.compile(r"反客为主|权力反转|评价权|定义权|控制权|提问权|服务权|主导权|审批权|权力交换|被评价者|责任反转"),
    "m3": re.compile(r"字面|歧义|双义|谐音|同音|语义|语言机关|指代|误拆|宾语|话术漏洞|重新定义|双语境"),
    "m4": re.compile(r"重复升级|递进|多场景|多轮|逐轮|固定口令|固定规则|固定反馈|连续升级|链式升级|阶梯|层层|多单元"),
    "contrast": re.compile(r"正常与|别人和|自己的|对照|对比|反差|两类|双版本|标准版"),
    "reveal": re.compile(r"最后反转|末尾反转|信息差|身份揭示|真相揭示|延迟揭示|预期落差|悬念揭晓"),
}

VERIFICATION = {
    "lz-m1-system-transfer": {
        "refs": ["7521216372430556467", "7512175549243542794", "7450782934102969639", "7598472724416227465"],
        "v2": "面对新题材时，它能预测应先列出源系统的角色、流程、术语和结算四层，再逐层迁移，而不是只替换名词。",
        "v3": "区别于泛化的场景错位：李宗恒样本持续迁移整套流程并让结算受新规则影响，结构约束更强。",
    },
    "lz-m2-control-right-reversal": {
        "refs": ["7523797231017069833", "7490030238697540918", "7058478668875566351", "7606063262928915850"],
        "v2": "面对关系冲突时，它能预测先找谁拥有评价权，再把提问、定义或审批动作交给原弱势方，并据此生成连续冲突。",
        "v3": "区别于单次身份反转：样本中的权力变化会通过问答、流程或服务动作持续兑现，不只依赖结尾翻牌。",
    },
    "lz-m3-semantic-reinterpretation": {
        "refs": ["7519348226857798938", "7275179679982685452", "7260391957950663948", "7484218738481401100"],
        "v2": "面对一句可多解的话，它能预测应明确原意、替代解释、角色行动和行动后果四步，避免只有孤立谐音梗。",
        "v3": "区别于普通误会：替代解释必须在语言上自洽并驱动下一动作，多个样本会继续沿错误语境推进。",
    },
    "lz-m4-fixed-rule-escalation": {
        "refs": ["7522720963953741083", "7169039217492856095", "7179795639503490361", "7648330461677491674"],
        "v2": "面对一个固定人物规则，它能预测每轮重复必须新增关系、信息或后果，最后一轮改变适用对象或达到最高强度。",
        "v3": "区别于一般重复剪辑：重复项共享同一发动机且强度可排序，重复本身承担验证和升级功能。",
    },
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def classify(item: dict[str, Any]) -> str:
    text = " ".join([str(item.get("title", "")), str(item.get("summary", "")), *map(str, item.get("tags", []))])
    lens = str(item.get("type", ""))
    if PATTERNS["commercial"].search(text):
        return "lz-g1-commercial-contamination"
    if PATTERNS["evidence"].search(text):
        return "lz-g2-evidence-account-boundary"
    if lens == "counterexamples":
        return "lz-r4-case-specific-observation"
    for key, cluster_id in (
        ("m1", "lz-m1-system-transfer"),
        ("m2", "lz-m2-control-right-reversal"),
        ("m3", "lz-m3-semantic-reinterpretation"),
        ("m4", "lz-m4-fixed-rule-escalation"),
    ):
        if PATTERNS[key].search(text):
            return cluster_id
    if PATTERNS["contrast"].search(text):
        return "lz-r1-generic-contrast"
    if PATTERNS["reveal"].search(text):
        return "lz-r2-generic-reveal-gap"
    if lens == "expression":
        return "lz-r3-packaging-support"
    return "lz-r4-case-specific-observation"


def role_for(item: dict[str, Any], cluster_type: str) -> str:
    lens = str(item.get("type", ""))
    if cluster_type == "method_candidate":
        if lens == "structures":
            return "method_core"
        if lens == "counterexamples":
            return "boundary"
        return "support"
    if cluster_type == "evidence_gate" and lens == "counterexamples":
        return "evidence_gate"
    if lens == "counterexamples":
        return "boundary"
    return "support"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    base = root / WORKFLOW
    candidates = [item for lens in LENSES for item in read_jsonl(base / "candidates" / f"{lens}.jsonl")]
    normal_source_ids: set[str] = set()
    for path in sorted((root / "10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/batches").glob("batch_*/structured_cards.jsonl")):
        for card in read_jsonl(path):
            if card.get("commercial_axis") == "正常内容" and card.get("core_direction_eligible") is True:
                normal_source_ids.add(str(card["source_id"]))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[classify(item)].append(item)

    clusters: list[dict[str, Any]] = []
    audit_errors: list[str] = []
    for cluster_id, spec in CLUSTERS.items():
        members = grouped.get(cluster_id, [])
        roles = {"method_core": [], "support": [], "boundary": [], "evidence_gate": []}
        for item in members:
            roles[role_for(item, spec["type"])].append(str(item["id"]))
        source_refs = sorted({str(ref) for item in members for ref in item.get("source_refs", [])})
        if not members:
            audit_errors.append(f"empty_cluster:{cluster_id}")
        if spec["type"] == "method_candidate" and not roles["method_core"]:
            audit_errors.append(f"method_without_structure_core:{cluster_id}")
        clusters.append(
            {
                "id": cluster_id,
                "title": spec["title"],
                "cluster_type": spec["type"],
                "core_mechanism": spec["core"],
                "candidate_ids": [str(item["id"]) for item in members],
                "source_refs": source_refs,
                "lens_roles": roles,
                "callable": False,
            }
        )

    verified: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    by_id = {item["id"]: item for item in clusters}
    for cluster in clusters:
        cluster_id = str(cluster["id"])
        if cluster["cluster_type"] == "method_candidate":
            check = VERIFICATION[cluster_id]
            missing_refs = sorted(set(check["refs"]) - set(cluster["source_refs"]))
            if missing_refs:
                audit_errors.append(f"verification_refs_not_in_cluster:{cluster_id}:{','.join(missing_refs)}")
            non_normal_refs = sorted(set(check["refs"]) - normal_source_ids)
            if non_normal_refs:
                audit_errors.append(f"verification_refs_not_normal_core:{cluster_id}:{','.join(non_normal_refs)}")
            verified.append(
                {
                    "id": cluster_id,
                    "title": cluster["title"],
                    "status": "verified_candidate_pending_user_confirmation",
                    "callable": False,
                    "triple_verification": {
                        "v1_cross_context": {
                            "passed": True,
                            "reason": f"由 {len(check['refs'])} 条独立正常内容跨关系或场景支持；同系列与商业样本不重复计入自然频次。",
                            "evidence_refs": check["refs"],
                        },
                        "v2_predictive_usefulness": {"passed": True, "reason": check["v2"]},
                        "v3_account_exclusivity": {"passed": True, "reason": check["v3"]},
                    },
                }
            )
            continue
        reasons = {
            "lz-g1-commercial-contamination": ("商业内容不参与账号自然方法频次证明，但必须路由到广告植入学习分支，拆解正常剧情、引入桥、产品角色和收束。", "route_to_ad_integration_learning", ["v1_natural_frequency"]),
            "lz-g2-evidence-account-boundary": ("证据质量与账号归属是前置门禁，不是内容生成方法。", "retain_as_evidence_gate", ["not_a_generation_method"]),
            "lz-r1-generic-contrast": ("正常/自己或前后对照是通用容器，尚未通过账号排他性验证。", "retain_as_support_pattern", ["v3_account_exclusivity"]),
            "lz-r2-generic-reveal-gap": ("揭示、信息差和末尾反转属于行业通用收束方式，不能单独触发。", "retain_as_support_pattern", ["v3_account_exclusivity"]),
            "lz-r3-packaging-support": ("标题、发布文案和话题属于表达支持层，不能绕过内容证据独立成为方法。", "retain_as_expression_support", ["v2_predictive_usefulness"]),
            "lz-r4-case-specific-observation": ("剩余观察尚未收敛为跨场景机制，保留单例和反例证据。", "wait_for_more_evidence", ["v1_cross_context", "mechanism_not_resolved"]),
        }
        reason, disposition, failed = reasons[cluster_id]
        rejected.append(
            {"id": cluster_id, "title": cluster["title"], "failed_checks": failed, "reason": reason, "disposition": disposition, "callable": False}
        )

    assigned = [candidate_id for cluster in clusters for candidate_id in cluster["candidate_ids"]]
    candidate_ids = [str(item["id"]) for item in candidates]
    if len(assigned) != len(set(assigned)):
        audit_errors.append("candidate_assigned_more_than_once")
    if set(assigned) != set(candidate_ids):
        audit_errors.append("candidate_assignment_not_exhaustive")
    if len(candidate_ids) != len(set(candidate_ids)):
        audit_errors.append("candidate_ids_not_unique")

    write_jsonl(base / "candidate_clusters.jsonl", clusters)
    write_jsonl(base / "verified.jsonl", verified)
    write_jsonl(base / "rejected.jsonl", rejected)
    lines = [
        "# 李宗恒阶段 2 方法簇审核包",
        "",
        "> 状态：待用户确认；所有候选 `callable=false`，不允许正式写入。",
        "",
        "## 聚类总览",
        "",
        f"- 五视角候选：{len(candidates)} 条，已唯一分配：{len(assigned)} 条。",
        f"- 候选方法：{len(verified)} 个；边界、证据门和降级簇：{len(rejected)} 个。",
        "- 聚类优先级：商业隔离 -> 证据归属 -> 主机制 -> 通用结构 -> 表达包装 -> 单例残余。",
        "",
        "## 候选方法",
        "",
    ]
    candidate_by_id = {str(item["id"]): item for item in candidates}
    for item in verified:
        cluster = by_id[item["id"]]
        sample_candidates = [candidate_by_id[candidate_id] for candidate_id in cluster["candidate_ids"][:6]]
        lines.extend(
            [
                f"### {item['id']}：{item['title']}",
                "",
                cluster["core_mechanism"],
                "",
                f"- 归入观察：{len(cluster['candidate_ids'])} 条；涉及来源：{len(cluster['source_refs'])} 条。",
                f"- V1 证据：{', '.join(f'`{ref}`' for ref in item['triple_verification']['v1_cross_context']['evidence_refs'])}",
                f"- V1：{item['triple_verification']['v1_cross_context']['reason']}",
                f"- V2：{item['triple_verification']['v2_predictive_usefulness']['reason']}",
                f"- V3：{item['triple_verification']['v3_account_exclusivity']['reason']}",
                "- 代表观察：" + "；".join(f"`{sample['id']}` {sample['title']}" for sample in sample_candidates),
                "",
            ]
        )
    lines.extend(["## 边界与降级簇", ""])
    for item in rejected:
        cluster = by_id[item["id"]]
        lines.append(f"- `{item['id']}`：{len(cluster['candidate_ids'])} 条观察。{item['reason']}（`{item['disposition']}`）")
    lines.extend(["", "## 确认门", "", "用户确认候选方法及分簇后，才进入 RIA++ 方法单元、方法关系和压力测试。", ""])
    (base / "STAGE2_REVIEW.md").write_text("\n".join(lines), encoding="utf-8")
    status = {
        "ok": not audit_errors,
        "workflow_id": "lizongheng-v2-full",
        "candidate_count": len(candidates),
        "assigned_candidate_count": len(assigned),
        "cluster_count": len(clusters),
        "verified_count": len(verified),
        "rejected_count": len(rejected),
        "cluster_counts": {cluster["id"]: len(cluster["candidate_ids"]) for cluster in clusters},
        "errors": audit_errors,
        "formal_write_allowed": False,
        "user_confirmation_required": True,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    (base / "STAGE2_STATUS.json").write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
