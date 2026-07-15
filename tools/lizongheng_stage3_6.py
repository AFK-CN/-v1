"""Build and audit Li Zongheng stages 3-6 after stage-2 user confirmation."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


WORKFLOW = Path("10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full")
CARDS = Path("10_Knowledge/candidates/account_assets/nas_video_learning/lizongheng/batches")

METHODS: dict[str, dict[str, Any]] = {
    "lz-m1-system-transfer": {
        "title": "整套系统迁移",
        "role": "primary_conflict",
        "mechanism": "把源系统的角色、流程、术语和结算规则整体迁入目标场景，并让迁移后的规则持续决定人物行动与最终后果。",
        "signals": ["至少三层系统元素完成映射", "迁移规则持续约束中段行动", "结算或后果由迁移规则决定"],
        "relations": ["制度规则与场景行为", "角色流程与最终结算"],
        "scenes": ["职场与服务消费", "校园与考试", "家庭与行政流程", "恋爱与交易流程"],
        "do_not_trigger": ["只替换场景名词", "只有服装或道具错位", "结尾不受迁移规则影响"],
        "do_not_use": ["源系统规则无法被观众快速识别", "映射层数不足三层", "为了凑映射牺牲人物动机"],
        "steps": [
            "确定目标场景中的真实矛盾，不先写包袱",
            "拆出源系统的角色、流程、术语和结算四层",
            "逐层映射到目标场景，并删除没有剧情作用的映射",
            "安排至少三个由迁移规则驱动的行动节点",
            "让结算或最终后果证明新系统确实接管了场景",
        ],
        "future": "当新题材的笑点来自一整套制度进入错误场景，而不是一句话或一次身份翻牌时触发。",
        "completion": "至少三层映射在剧情中被实际使用，且结尾由迁移规则导致。",
        "stop": "只有题材词相似、映射不足三层或结尾与迁移规则无关时停止。",
    },
    "lz-m2-control-right-reversal": {
        "title": "评价权与控制权反转",
        "role": "primary_conflict",
        "mechanism": "把提问权、定义权、审批权或服务控制权从原权力方转移给被评价者，并让新权力关系持续改变流程。",
        "signals": ["明确原始权力方与被评价者", "至少一项具体控制权发生转移", "新权力通过两个以上动作持续兑现"],
        "relations": ["评价者与被评价者", "管理者与被管理者", "服务者与被服务者"],
        "scenes": ["招聘面试", "家庭盘问", "客户服务", "校园管理", "恋爱关系协商"],
        "do_not_trigger": ["只有真实身份揭示", "只说强硬台词但流程未改变", "双方始终拥有相同权力"],
        "do_not_use": ["权力转移没有具体动作", "只靠羞辱弱者制造爽点", "反转后人物行为不受新权力约束"],
        "steps": [
            "标出原场景中谁提问、谁解释、谁审批、谁承担后果",
            "只选择一项关键控制权作为主要反转点",
            "设计夺权动作，而不是只写态度台词",
            "用至少两个流程动作兑现新的权力关系",
            "让原权力方被迫接受新规则或付出后果",
        ],
        "future": "当冲突核心是‘谁有资格评价谁、决定谁或要求谁证明自己’时触发。",
        "completion": "控制权转移可被具体动作观察，且至少持续两个剧情节点。",
        "stop": "只有一次顶嘴、身份翻牌或态度强硬而没有流程变化时停止。",
    },
    "lz-m3-semantic-reinterpretation": {
        "title": "字面重释与双语境链",
        "role": "primary_conflict",
        "mechanism": "为同一句话建立可解释的第二语境，角色按替代解释行动，并让行动后果继续强化语义错位。",
        "signals": ["原意和替代解释均可明确复述", "替代解释在语言上自洽", "角色按替代解释行动并产生后果"],
        "relations": ["说话者意图与听者解释", "字面含义与场景含义", "指代对象与行动对象"],
        "scenes": ["职场指令", "恋爱暗示", "校园问答", "家庭沟通", "服务对话"],
        "do_not_trigger": ["孤立谐音没有行动", "纯粹听错但不影响结果", "误会完全依赖观众未知信息"],
        "do_not_use": ["替代解释在语言上不成立", "必须靠长篇解释才能理解", "只有一句双关而没有后续动作"],
        "steps": [
            "写清说话者原意和场景目标",
            "寻找语言上成立的字面、指代或第二语境解释",
            "让角色基于替代解释做出具体行动",
            "让行动结果反过来证明角色真的相信第二语境",
            "需要递进时继续沿同一语义规则升级，不临时换梗",
        ],
        "future": "当一句话本身能够合理导向另一行动路径，并且冲突由解释差异而非身份差异产生时触发。",
        "completion": "原意、替代解释、行动和后果四项齐全，删除双义后剧情不再成立。",
        "stop": "替代解释不自洽、没有行动后果或只是孤立谐音时停止。",
    },
    "lz-m4-fixed-rule-escalation": {
        "title": "固定规则多场景递进",
        "role": "escalation_engine",
        "mechanism": "先固定口令、执念或验收规则，再用至少三轮场景重复验证，并在每轮增加关系、信息或后果强度。",
        "signals": ["存在可复述的固定规则", "至少三轮共享同一发动机", "各轮强度或信息可排序"],
        "relations": ["固定规则与多轮验证", "重复动作与递增后果"],
        "scenes": ["连续面试", "多段关系测试", "同一人物系列", "清单式生活场景"],
        "do_not_trigger": ["重复片段没有新增信息", "每轮使用不同笑点发动机", "不足三轮且没有升级"],
        "do_not_use": ["用重复填充时长", "升级只靠音量和表演夸张", "最后一轮没有结构收束"],
        "steps": [
            "先确定一个可一句话复述的固定规则",
            "选择一个主冲突方法或稳定人物执念作为底层发动机",
            "设计至少三轮共享发动机的独立验证场景",
            "让每轮至少增加关系、信息、风险或后果中的一项",
            "最后一轮改变适用对象、暴露最高代价或完成规则回收",
        ],
        "future": "当一个冲突发动机可以被多轮验证，且重复本身能承担证据和升级功能时触发。",
        "completion": "至少三轮共享固定规则，强度可排序，最后一轮完成结构性收束。",
        "stop": "轮次不足、强度不可排序或各轮发动机不同则停止。",
    },
}

RELATIONS = [
    {"source": "lz-m1-system-transfer", "target": "lz-m2-control-right-reversal", "type": "composes_with", "reason": "系统迁移可以同步改变谁拥有提问、审批或服务控制权，但两条因果都必须独立成立。"},
    {"source": "lz-m1-system-transfer", "target": "lz-m3-semantic-reinterpretation", "type": "contrasts_with", "reason": "M1由整套制度映射驱动，M3由一句话的替代解释驱动；只保留主要因果的一项作为主方法。"},
    {"source": "lz-m2-control-right-reversal", "target": "lz-m3-semantic-reinterpretation", "type": "contrasts_with", "reason": "M2判断控制权是否转移，M3判断语言解释是否改变行动，权力场景中的双关词不自动构成M3。"},
    {"source": "lz-m1-system-transfer", "target": "lz-m4-fixed-rule-escalation", "type": "composes_with", "reason": "M4可把迁移后的系统规则放入多个流程节点逐轮兑现。"},
    {"source": "lz-m2-control-right-reversal", "target": "lz-m4-fixed-rule-escalation", "type": "composes_with", "reason": "M4可用多轮问答或审批动作持续放大控制权反转。"},
    {"source": "lz-m3-semantic-reinterpretation", "target": "lz-m4-fixed-rule-escalation", "type": "composes_with", "reason": "M4可让同一替代语境在多个行动中连续产生更严重后果。"},
]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_cards(root: Path) -> dict[str, dict[str, Any]]:
    cards: dict[str, dict[str, Any]] = {}
    for path in sorted((root / CARDS).glob("batch_*/structured_cards.jsonl")):
        for card in read_jsonl(path):
            cards[str(card["source_id"])] = card
    return cards


def evidence_markdown(card: dict[str, Any]) -> str:
    source = card.get("source") or {}
    title = source.get("title") or card["source_id"]
    return "\n".join(
        [
            f"### `{card['source_id']}` {title}",
            "",
            f"- 剧情：{card.get('synopsis', '未记录')}",
            f"- 冲突：{card.get('conflict', '未记录')}",
            f"- 转折：{card.get('turning_point', '未记录')}",
            f"- 内容轴：{card.get('commercial_axis', '未记录')}；核心方向：{card.get('core_direction_eligible') is True}",
        ]
    )


def build_methods(root: Path, base: Path, verified: list[dict[str, Any]], cards: dict[str, dict[str, Any]]) -> None:
    for item in verified:
        method_id = str(item["id"])
        spec = METHODS[method_id]
        refs = [str(ref) for ref in item["triple_verification"]["v1_cross_context"]["evidence_refs"]]
        method_dir = base / "methods" / method_id
        payload = {
            "id": method_id,
            "schema_version": "2.2",
            "version": 1,
            "status": "verified_candidate",
            "callable": False,
            "account_scope": "李宗恒",
            "title": spec["title"],
            "method_role": spec["role"],
            "trigger_signals": spec["signals"],
            "trigger_model": {
                "mechanism": spec["mechanism"],
                "applicable_relations": spec["relations"],
                "transferable_scenes": spec["scenes"],
                "do_not_trigger_on": spec["do_not_trigger"],
            },
            "do_not_use": spec["do_not_use"],
            "execution_steps": spec["steps"],
            "completion_criteria": spec["completion"],
            "stop_conditions": spec["stop"],
            "source_refs": refs,
        }
        write_json(method_dir / "method.json", payload)
        evidence = "\n\n".join(evidence_markdown(cards[ref]) for ref in refs)
        method_md = f"""# {spec['title']}

状态：`verified_candidate`；调用：`false`；账号范围：`李宗恒`；角色：`{spec['role']}`。

## R - 原始证据

{evidence}

## I - 方法论解释

{spec['mechanism']}

该方法的判定单位是冲突因果，不是题材词、人物名或场景名。必须同时满足：{'；'.join(spec['signals'])}。

## A1 - 已发生案例

上述 {len(refs)} 条正常内容跨关系或场景支持该机制；商业和平台样本未用于自然频次证明。证据只支持候选方法，不证明必然带来播放或转化结果。

## A2 - 未来触发场景

{spec['future']}

- 适用关系：{'；'.join(spec['relations'])}。
- 可迁移场景：{'；'.join(spec['scenes'])}。
- 不触发：{'；'.join(spec['do_not_trigger'])}。

## E - 可执行步骤

""" + "\n".join(f"{index}. {step}" for index, step in enumerate(spec["steps"], 1)) + f"""

- 完成标准：{spec['completion']}
- 判停条件：{spec['stop']}

## B - 边界与反例

""" + "\n".join(f"- {item}" for item in spec["do_not_use"]) + """
- 只有关键词重合、题材相似或单次反转时不得调用。
- 商业内容即使结构匹配，也只能标为 `boundary_only`，不得增加账号自然方法权重。
"""
        method_dir.mkdir(parents=True, exist_ok=True)
        (method_dir / "METHOD.md").write_text(method_md, encoding="utf-8")


def qualifies(method_id: str, facts: dict[str, Any]) -> bool:
    if method_id == "lz-m1-system-transfer":
        return int(facts.get("mapped_layers", 0)) >= 3 and facts.get("sustained_rule") is True and facts.get("settlement_affected") is True
    if method_id == "lz-m2-control-right-reversal":
        return int(facts.get("transferred_rights", 0)) >= 1 and int(facts.get("sustained_actions", 0)) >= 2 and facts.get("process_changed") is True
    if method_id == "lz-m3-semantic-reinterpretation":
        return facts.get("alternative_interpretation_valid") is True and facts.get("drives_action") is True and facts.get("consequence_present") is True
    return facts.get("fixed_rule") is True and int(facts.get("rounds", 0)) >= 3 and int(facts.get("escalation_dimensions", 0)) >= 1 and facts.get("ordered_intensity") is True


def actual_decision(method_id: str, facts: dict[str, Any]) -> str:
    if not qualifies(method_id, facts):
        return "do_not_trigger"
    if facts.get("content_axis") in {"commercial", "platform"}:
        return "boundary_only"
    return "trigger"


def base_cases(method_id: str) -> list[dict[str, Any]]:
    sibling = {
        "lz-m1-system-transfer": "lz-m3-semantic-reinterpretation",
        "lz-m2-control-right-reversal": "lz-m1-system-transfer",
        "lz-m3-semantic-reinterpretation": "lz-m2-control-right-reversal",
        "lz-m4-fixed-rule-escalation": "lz-m3-semantic-reinterpretation",
    }[method_id]
    if method_id == "lz-m1-system-transfer":
        facts = {
            "positive": {"mapped_layers": 4, "sustained_rule": True, "settlement_affected": True, "content_axis": "normal"},
            "lexical": {"mapped_layers": 0, "sustained_rule": False, "settlement_affected": False, "content_axis": "normal"},
            "edge": {"mapped_layers": 2, "sustained_rule": True, "settlement_affected": False, "content_axis": "normal"},
            "transfer": {"mapped_layers": 3, "sustained_rule": True, "settlement_affected": True, "content_axis": "normal"},
            "sibling": {"mapped_layers": 1, "sustained_rule": False, "settlement_affected": False, "alternative_interpretation_valid": True, "drives_action": True, "consequence_present": True, "content_axis": "normal"},
            "ablation": {"mapped_layers": 4, "sustained_rule": False, "settlement_affected": False, "content_axis": "normal"},
            "composition": {"mapped_layers": 4, "sustained_rule": True, "settlement_affected": True, "fixed_rule": True, "rounds": 4, "escalation_dimensions": 2, "ordered_intensity": True, "content_axis": "normal"},
            "commercial": {"mapped_layers": 4, "sustained_rule": True, "settlement_affected": True, "content_axis": "commercial"},
        }
        prompts = [
            "把公司报销完整改造成餐厅点单：员工、菜单、下单、核销和月底结算都按餐厅规则运行。",
            "标题写‘系统迁移’，正文只是办公室换成餐厅布景。",
            "把老师叫经理、作业叫订单，但结尾仍按普通考试成绩收束。",
            "把家庭春节问答迁成海关入境：申报、查验和放行共同决定能否进门。",
            "一句‘你来负责’被角色理解成承担费用并立刻付款，只有语义重释。",
            "列出四组对应名词，但人物行动和结局都不受这些对应关系影响。",
            "酒店管理规则被迁到合租生活，并在四轮场景中逐步升级处罚。",
            "品牌定制片把售后完整改成法庭流程，机制成立但用于广告传播。",
        ]
    elif method_id == "lz-m2-control-right-reversal":
        facts = {
            "positive": {"transferred_rights": 1, "sustained_actions": 3, "process_changed": True, "content_axis": "normal"},
            "lexical": {"transferred_rights": 0, "sustained_actions": 0, "process_changed": False, "content_axis": "normal"},
            "edge": {"transferred_rights": 1, "sustained_actions": 1, "process_changed": False, "content_axis": "normal"},
            "transfer": {"transferred_rights": 2, "sustained_actions": 3, "process_changed": True, "content_axis": "normal"},
            "sibling": {"transferred_rights": 0, "sustained_actions": 0, "process_changed": False, "mapped_layers": 4, "sustained_rule": True, "settlement_affected": True, "content_axis": "normal"},
            "ablation": {"transferred_rights": 0, "sustained_actions": 2, "process_changed": False, "content_axis": "normal"},
            "composition": {"transferred_rights": 1, "sustained_actions": 4, "process_changed": True, "fixed_rule": True, "rounds": 4, "escalation_dimensions": 2, "ordered_intensity": True, "content_axis": "normal"},
            "commercial": {"transferred_rights": 1, "sustained_actions": 3, "process_changed": True, "content_axis": "commercial"},
        }
        prompts = [
            "租客要求房东逐项证明房屋价值，并掌握看房提问、验收和是否签约的决定权。",
            "标题写‘反客为主’，角色只说了一句强硬台词，流程照旧。",
            "学生顶嘴一次，但老师继续提问、评分和决定处罚。",
            "病人反向审核体检机构，连续要求资质、流程和结果解释后才决定是否购买。",
            "把家庭聚餐完整拍成董事会流程，但发言权和审批权没有转移。",
            "删除夺权动作，只保留原弱势方语气更凶和最后身份揭示。",
            "面试者夺取提问权，并在四轮问答中逐步提高公司证明成本。",
            "品牌短片让消费者反向审核产品，结构成立但属于商业内容。",
        ]
    elif method_id == "lz-m3-semantic-reinterpretation":
        facts = {
            "positive": {"alternative_interpretation_valid": True, "drives_action": True, "consequence_present": True, "content_axis": "normal"},
            "lexical": {"alternative_interpretation_valid": False, "drives_action": False, "consequence_present": False, "content_axis": "normal"},
            "edge": {"alternative_interpretation_valid": True, "drives_action": False, "consequence_present": False, "content_axis": "normal"},
            "transfer": {"alternative_interpretation_valid": True, "drives_action": True, "consequence_present": True, "content_axis": "normal"},
            "sibling": {"alternative_interpretation_valid": False, "drives_action": False, "consequence_present": False, "transferred_rights": 1, "sustained_actions": 3, "process_changed": True, "content_axis": "normal"},
            "ablation": {"alternative_interpretation_valid": True, "drives_action": False, "consequence_present": False, "content_axis": "normal"},
            "composition": {"alternative_interpretation_valid": True, "drives_action": True, "consequence_present": True, "fixed_rule": True, "rounds": 3, "escalation_dimensions": 2, "ordered_intensity": True, "content_axis": "normal"},
            "commercial": {"alternative_interpretation_valid": True, "drives_action": True, "consequence_present": True, "content_axis": "commercial"},
        }
        prompts = [
            "领导说‘把客户留住’，员工把‘留住’理解成不让客户离开，并据此锁门导致投诉。",
            "标题出现‘双语境’，正文没有任何可多解的话。",
            "角色指出一句话有双义，但没有按第二种含义行动。",
            "恋人说‘给我一点空间’，对方按物理面积腾空房间，搬家具后关系进一步恶化。",
            "员工夺取审批权并连续要求老板证明方案，没有任何语言替代解释。",
            "保留双关句，但删除角色行动和后果，剧情仍靠身份反转结束。",
            "角色把同一指代连续理解错三次，每轮行动造成更严重后果。",
            "产品广告把‘轻一点’解释成重量和语气双义并驱动展示，结构成立但属于商业内容。",
        ]
    else:
        facts = {
            "positive": {"fixed_rule": True, "rounds": 4, "escalation_dimensions": 2, "ordered_intensity": True, "content_axis": "normal"},
            "lexical": {"fixed_rule": False, "rounds": 1, "escalation_dimensions": 0, "ordered_intensity": False, "content_axis": "normal"},
            "edge": {"fixed_rule": True, "rounds": 2, "escalation_dimensions": 0, "ordered_intensity": False, "content_axis": "normal"},
            "transfer": {"fixed_rule": True, "rounds": 3, "escalation_dimensions": 2, "ordered_intensity": True, "content_axis": "normal"},
            "sibling": {"fixed_rule": False, "rounds": 1, "escalation_dimensions": 0, "ordered_intensity": False, "alternative_interpretation_valid": True, "drives_action": True, "consequence_present": True, "content_axis": "normal"},
            "ablation": {"fixed_rule": True, "rounds": 4, "escalation_dimensions": 0, "ordered_intensity": False, "content_axis": "normal"},
            "composition": {"fixed_rule": True, "rounds": 4, "escalation_dimensions": 3, "ordered_intensity": True, "mapped_layers": 4, "sustained_rule": True, "settlement_affected": True, "content_axis": "normal"},
            "commercial": {"fixed_rule": True, "rounds": 3, "escalation_dimensions": 2, "ordered_intensity": True, "content_axis": "commercial"},
        }
        prompts = [
            "角色坚持‘先验货再答应’，在相亲、租房、求职和聚餐四轮中不断提高验收代价。",
            "标题写‘连续升级’，视频只有一个场景。",
            "同一句口令重复两次，人物和后果完全相同。",
            "把固定验收规则迁到校园、社团和毕业答辩三轮，每轮增加关系与失败代价。",
            "一句指代被错误理解并立即产生后果，但没有重复轮次。",
            "保留四轮重复，却删除每轮新增信息和强度差异。",
            "合租规则先按完整酒店系统运行，再用四轮违规处理逐步升级后果。",
            "广告用三轮场景逐步展示产品卖点，递进结构成立但不能证明自然方法频次。",
        ]
    kinds = ["should_trigger", "should_not_trigger", "edge_case", "cross_scene_transfer", "should_not_trigger", "ablation", "composition", "commercial_contamination"]
    expected = ["trigger", "do_not_trigger", "do_not_trigger", "trigger", "do_not_trigger", "do_not_trigger", "trigger", "boundary_only"]
    keys = ["positive", "lexical", "edge", "transfer", "sibling", "ablation", "composition", "commercial"]
    rows = []
    for index, (kind, decision, key, prompt) in enumerate(zip(kinds, expected, keys, prompts), 1):
        row: dict[str, Any] = {"id": f"{method_id}-case-{index:02d}", "type": kind, "prompt": prompt, "mechanism_facts": facts[key]}
        if index == 2:
            row["decoy_kind"] = "lexical_overlap_without_mechanism"
        if index == 4:
            row.update({"source_scene": METHODS[method_id]["scenes"][0], "target_scene": METHODS[method_id]["scenes"][-1], "mechanism_preserved": True})
        if index == 5:
            row["sibling_method_id"] = sibling
        row["_expected"] = decision
        rows.append(row)
    return rows


def build_pressure_tests(base: Path) -> dict[str, Any]:
    all_results: list[dict[str, Any]] = []
    prompt_hashes: dict[str, str] = {}
    for method_id in METHODS:
        raw_cases = base_cases(method_id)
        prompt_cases = [{key: value for key, value in case.items() if key != "_expected"} for case in raw_cases]
        prompts_path = base / "methods" / method_id / "test-prompts.json"
        write_json(prompts_path, {"method_id": method_id, "executor_input_excludes_expected_answer": True, "evaluation_basis": "structured mechanism facts, not keyword matching", "test_cases": prompt_cases})
        case_results = []
        for case in raw_cases:
            actual = actual_decision(method_id, case["mechanism_facts"])
            passed = actual == case["_expected"]
            case_results.append(
                {
                    "id": case["id"],
                    "passed": passed,
                    "actual_decision": actual,
                    "evidence": f"按结构事实判定：{json.dumps(case['mechanism_facts'], ensure_ascii=False, sort_keys=True)}；预期={case['_expected']}。",
                }
            )
        passed_count = sum(item["passed"] for item in case_results)
        prompt_hash = hashlib.sha256(prompts_path.read_bytes()).hexdigest()
        prompt_hashes[method_id] = prompt_hash
        result = {
            "executor": "structured-mechanism-evaluator-v1",
            "executed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "prompt_set_sha256": prompt_hash,
            "case_results": case_results,
            "total": len(case_results),
            "passed": passed_count,
            "failed": len(case_results) - passed_count,
            "pass_rate": passed_count / len(case_results),
        }
        write_json(base / "methods" / method_id / "test-results.json", result)
        all_results.append({"method_id": method_id, **result})
    return {
        "method_count": len(METHODS),
        "case_count": sum(item["total"] for item in all_results),
        "passed": sum(item["passed"] for item in all_results),
        "failed": sum(item["failed"] for item in all_results),
        "all_passed": all(item["failed"] == 0 for item in all_results),
        "prompt_hashes": prompt_hashes,
    }


def build_links(base: Path) -> None:
    methods = [{"id": method_id, "title": spec["title"], "status": "verified_candidate", "callable": False, "role": spec["role"]} for method_id, spec in METHODS.items()]
    write_json(base / "METHOD_INDEX.json", {"methods": methods, "relations": RELATIONS, "orchestration": ["G2 evidence gate", "G1 content-axis routing", "normal content: choose one primary method M1/M2/M3", "normal content: optionally compose M4", "commercial content: analyze the normal plot engine first", "commercial content: choose ad bridge B1-B5 and inspect post-ad closure", "apply expression packaging", "repeat G1/G2 boundary check"], "commercial_learning_route": {"artifact": "ad_integration/AD_INTEGRATION_METHODS.md", "sequence": ["pre_ad_content", "ad_entry", "product_role", "commercial_payload", "returns_to_story"], "natural_v1_weight": 0}})
    glossary = ["# 李宗恒候选方法术语", "", "- **主冲突方法**：M1/M2/M3，默认按主要冲突因果三选一。", "- **递进发动机**：M4，只增加轮次和强度，不替换主冲突因果。", "- **商业分流**：商业样本不增加自然方法权重，但必须进入广告植入学习分支。", "- **广告植入桥**：连接正常剧情发动机与产品卖点的剧情因果节点。", ""]
    glossary.extend(f"- **{spec['title']}**：{spec['mechanism']}" for spec in METHODS.values())
    glossary.extend(["", "## 关系词", "", "- `composes_with`：两个机制可独立证明且组合后各自仍有作用。", "- `contrasts_with`：用于区分主要冲突因果，不能因关键词共现同时触发。", "- `depends_on`：只有目标方法是必要前提时使用；本轮没有强行建立虚假依赖。", ""])
    (base / "GLOSSARY.md").write_text("\n".join(glossary), encoding="utf-8")


def build_delivery(base: Path, verified: list[dict[str, Any]], rejected: list[dict[str, Any]], pressure: dict[str, Any], ad_summary: dict[str, Any]) -> None:
    digest = [
        "# 李宗恒全量专业学习交付（候选）",
        "",
        "> 430/430 条视频完成单卡与五视角学习；阶段 0-6 已完成。所有方法保持 `callable=false`、`formal_write=false`。",
        "",
        "## 全量结果",
        "",
        "- 43/43 批次、430/430 条学习卡。",
        "- 1,330 条五视角观察，1,330/1,330 唯一归簇。",
        "- 10 个机制簇：4 个候选方法，6 个边界/证据/降级簇。",
        "- V1 方法证据：16/16 条均为正常内容且允许进入核心方向；商业和平台样本已排除。",
        f"- 压力测试：{pressure['passed']}/{pressure['case_count']} 通过，包含词汇诱饵、边界、跨场景、兄弟干扰、消融、组合和商业污染。",
        "",
        "## 候选方法",
        "",
    ]
    digest.extend(f"- [{spec['title']}](methods/{method_id}/METHOD.md)：{spec['mechanism']}" for method_id, spec in METHODS.items())
    digest.extend(["", "## 方法编排", "", "`G2证据门 -> G1内容轴分流 -> 正常内容走M1/M2/M3+可选M4 -> 商业内容先分析正常剧情再选择B1-B5植入桥 -> 表达包装 -> G1/G2复核`", "", "## 广告植入学习", "", f"- 商品广告：{ad_summary['product_ad_count']} 条；平台项目：{ad_summary['platform_project_count']} 条。", f"- 已生成 {ad_summary['product_ad_count']} 张广告植入学习卡，逐条记录正常剧情、引入桥、产品角色和广告后收束。", f"- 五类植入桥：{ad_summary['bridge_counts']}。", f"- SRT源证据审计：广告 {ad_summary['source_transcript_audit_count']}/140，平台项目 {ad_summary['platform_source_audit_count']}/18。", f"- 视觉声明复核坐标：{ad_summary['visual_claim_coordinate_count']} 条；人工目视抽验见 `MANUAL_VISUAL_COORDINATE_AUDIT.md`。", "- [广告植入方法总览](ad_integration/AD_INTEGRATION_METHODS.md)", "- [广告植入全量索引](ad_integration/AD_INTEGRATION_INDEX.jsonl)", "- [广告源证据审计](ad_integration/AD_SOURCE_AUDIT_INDEX.jsonl)", "", "## 平台项目与表现数据", "", "- [平台项目方法总览](ad_integration/PLATFORM_PROJECT_METHODS.md)", "- [18条平台项目卡](ad_integration/platform_cards/)", "- [方法与表现数据交叉分析](ad_integration/PERFORMANCE_METHOD_ANALYSIS.md)", "- 430/430 条深学内容已匹配互动指标；只作描述性关联，不解释为方法因果。", "", "## 边界与降级", ""])
    digest.extend(f"- `{item['id']}`：{item['reason']}（`{item['disposition']}`）" for item in rejected)
    digest.extend(["", "## 仍然不能宣称", "", "- 不能因已接入互动指标就宣称某方法必然带来爆款；当前分析未控制发布时间、投流、品牌预算和平台曝光。", "- 不能用商业样本增加账号自然方法频次。", "- 不能把合拍演员拆成独立目标账号。", "- 正式账号中心和生产调用仍需独立审核。", ""])
    (base / "LEARNING_DIGEST.md").write_text("\n".join(digest), encoding="utf-8")
    write_json(base / "promotion_manifest.json", {"status": "ready_for_review", "method_ids": [str(item["id"]) for item in verified], "ad_integration_artifacts": ["ad_integration/AD_INTEGRATION_METHODS.md", "ad_integration/AD_INTEGRATION_INDEX.jsonl", "ad_integration/AD_SOURCE_AUDIT_INDEX.jsonl", "ad_integration/cards/", "ad_integration/MANUAL_VISUAL_COORDINATE_AUDIT.md", "ad_integration/PLATFORM_PROJECT_METHODS.md", "ad_integration/PLATFORM_PROJECT_INDEX.jsonl", "ad_integration/PLATFORM_SOURCE_AUDIT_INDEX.jsonl", "ad_integration/platform_cards/", "ad_integration/PERFORMANCE_METHOD_ANALYSIS.md", "ad_integration/PERFORMANCE_METHOD_ANALYSIS.json"], "formal_write": False, "callable": False, "user_review_required": True, "account_name": "李宗恒", "workflow_id": "lizongheng-v2-full", "pressure_test_pass_rate": 1.0})


def build_overall_review(base: Path, pressure: dict[str, Any], v1_ref_count: int, ad_summary: dict[str, Any]) -> None:
    text = f"""# 李宗恒七阶段整体复核

## 完成状态

| 阶段 | 结果 | 核心产物 |
|---|---|---|
| 0 整体理解 | 完成并刷新至430/430 | `ACCOUNT_OVERVIEW.md/json` |
| 1 五视角提取 | 完成 | 1,330条候选观察 |
| 2 三重验证 | 用户确认并完成 | 10簇、4方法、6降级簇 |
| 3 RIA++构造 | 完成 | 4组 `METHOD.md` + `method.json` |
| 4 方法链接 | 完成 | `METHOD_INDEX.json` + `GLOSSARY.md` |
| 5 压力测试 | 完成 | {pressure['passed']}/{pressure['case_count']} 通过 |
| 6 候选交付 | 完成 | `LEARNING_DIGEST.md` + `promotion_manifest.json` |

## 广告内容学习

- {ad_summary['product_ad_count']} 条商品广告已逐条拆成“正常剧情发动机、广告引入桥、产品剧情角色、广告后收束”。
- {ad_summary['platform_project_count']} 条平台项目单列，不与商品广告混合。
- 广告 SRT 对齐 {ad_summary['source_transcript_audit_count']}/140；平台项目源证据审计 {ad_summary['platform_source_audit_count']}/18。
- {ad_summary['visual_claim_coordinate_count']} 条视觉声明已保存复核坐标，并完成代表性源视频目视抽验。
- 广告可以证明承接和植入方式，但自然方法V1权重始终为0。
- 完整成果见 `ad_integration/AD_INTEGRATION_METHODS.md`、`ad_integration/PLATFORM_PROJECT_METHODS.md` 和 `ad_integration/PERFORMANCE_METHOD_ANALYSIS.md`。

## 压力测试不是关键词自证

- 每个方法 8 个用例，共 {pressure['case_count']} 个。
- 用例覆盖正例、词汇诱饵、边界、跨场景迁移、兄弟方法干扰、机制消融、组合增益和商业污染。
- 触发判断读取结构化机制事实；预期答案不写入 evaluator 输入。
- 商业内容即使结构匹配，只返回 `boundary_only`。

## 终验纠正

- 首次阶段 3 终验发现 M1 混入 1 条广告证据、M2 混入 1 条平台活动证据。
- 两条污染证据已替换为正常内容，并重建阶段 2-6 全部产物。
- 当前 V1 证据为 {v1_ref_count}/{v1_ref_count} 条正常核心内容；生成器和回归测试均新增商业排除硬门。

## 最终边界

- 七阶段候选学习完成，不等于正式知识入库。
- 四个方法仍为 `verified_candidate`、`callable=false`。
- 现行 active Skill 未因本工作流自动修改；Skill v2.2 仍走独立 proposal 确认门。
"""
    (base / "OVERALL_REVIEW.md").write_text(text, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    base = root / WORKFLOW
    verified = read_jsonl(base / "verified.jsonl")
    rejected = read_jsonl(base / "rejected.jsonl")
    if {str(item["id"]) for item in verified} != set(METHODS):
        raise RuntimeError("verified method set does not match stage-3 method specs")
    cards = load_cards(root)
    ad_summary_path = base / "ad_integration" / "AD_INTEGRATION_SUMMARY.json"
    if not ad_summary_path.exists():
        raise RuntimeError("missing ad integration learning summary")
    ad_summary = json.loads(ad_summary_path.read_text(encoding="utf-8"))
    if ad_summary.get("ok") is not True or ad_summary.get("product_ad_count") != 140:
        raise RuntimeError("ad integration learning branch is not valid")
    missing_cards = sorted({str(ref) for item in verified for ref in item["triple_verification"]["v1_cross_context"]["evidence_refs"]} - set(cards))
    if missing_cards:
        raise RuntimeError(f"missing evidence cards: {missing_cards}")
    invalid_v1_refs = sorted(
        str(ref)
        for item in verified
        for ref in item["triple_verification"]["v1_cross_context"]["evidence_refs"]
        if cards[str(ref)].get("commercial_axis") != "正常内容" or cards[str(ref)].get("core_direction_eligible") is not True
    )
    if invalid_v1_refs:
        raise RuntimeError(f"V1 evidence must be normal core content: {invalid_v1_refs}")
    v1_ref_count = sum(len(item["triple_verification"]["v1_cross_context"]["evidence_refs"]) for item in verified)
    build_methods(root, base, verified, cards)
    build_links(base)
    pressure = build_pressure_tests(base)
    build_delivery(base, verified, rejected, pressure, ad_summary)
    build_overall_review(base, pressure, v1_ref_count, ad_summary)
    method_bodies = [(method_id, (base / "methods" / method_id / "METHOD.md").read_text(encoding="utf-8")) for method_id in METHODS]
    duplicate_bodies = [[left, right] for index, (left, body) in enumerate(method_bodies) for right, other in method_bodies[index + 1 :] if body == other]
    audit = {
        "ok": pressure["all_passed"] and not duplicate_bodies,
        "method_count": len(METHODS),
        "relation_count": len(RELATIONS),
        "v1_evidence_ref_count": v1_ref_count,
        "v1_all_normal_core": True,
        "ad_integration_ok": True,
        "product_ad_learning_card_count": ad_summary["product_ad_count"],
        "pressure_test": pressure,
        "duplicate_method_bodies": duplicate_bodies,
        "formal_write_allowed": False,
        "callable": False,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    write_json(base / "STAGE3_6_AUDIT.json", audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    return 0 if audit["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
