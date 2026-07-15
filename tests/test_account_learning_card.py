from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.account_learning_card import CONTRACT_ID, detect_schema, validate_card_text, validate_unified_text
from tools.video_learning_audit import EvidenceRecord, audit_card, parse_card
from tools.video_learning import NormalizedRecord, selected_card_markdown


REPO_ROOT = Path(__file__).resolve().parents[1]


def unified_card_text(content_form: str = "剧情段子") -> str:
    structure = """- 开头设定：先给出一个看似有效的解决办法。
- 核心冲突：解决办法与人物真实态度冲突。
- 升级：限制不断增加，解释空间持续缩小。
- 转折或笑点：角色用最短回答暴露真实立场。
- 收尾：停在关系反转结果，不额外拔高。"""
    if content_form == "知识口播":
        structure = """- 黄金3秒：先提出一个反常识问题。
- 观点提出：给出明确判断。
- 证据或案例：用两个来源支撑判断。
- 推演：把模型应用到新场景。
- 收尾：给出一个可执行检查动作。"""
    if content_form == "图文":
        structure = """- 封面承诺：给出明确结果。
- 分图顺序：问题、步骤、结果、边界。
- 信息层级：每图只承担一个信息任务。
- 行动建议：给出可执行清单。
- 收尾互动：邀请读者核对自己的情况。"""
    return f"""# 视频深度学习卡：sample-1

学习卡契约：{CONTRACT_ID}
source_id：sample-1
原内容链接：https://example.com/sample-1
账号：示例来源
平台：抖音
主方向：表达结构
学习批次：batch-01
状态：candidate_learned

## 1. 证据边界

- 主证据：完整逐字稿和原视频。
- 辅助证据：标题、正文和话题。
- 证据状态：逐字稿、视频和抽帧均可用。

## 2. 为什么值得学习

- 观点清晰，结构完整，可用于观察内容如何推进。
- 标题、正文和表现层围绕同一个承诺协同。

## 3. 多维分类与商业隔离

- 内容形态：{content_form}
- 场景：通用示例场景
- 商业属性：正常内容
- 隔离判断：没有品牌、购买行动或平台活动，不进入广告隔离区。

## 4. 核心观点

- 内容观点：限制条件会迫使真实态度更快暴露。
- 表达观点：先给错误解决方案，再用结果反证，能够形成清晰转折。

## 5. 内容结构

{structure}

## 6. 发布内容层学习

- 标题：先承诺一个看似有效的解决办法。
- 正文或文案：逐步增加限制，不提前泄露结局。
- 话题或标签：关系、沟通、反转。

## 7. 视频/图文表现层学习

- 媒体类型：视频。
- 分析状态：逐字稿和抽帧完成。
- 表现学习：通过停顿、反应镜头和回答长度变化推进冲突。

## 8. 金句与表达素材

- 原文金句：这是可回查的来源原句。
- 提炼表达（非原话）：限制越多，真实立场越快暴露。
- 可复用句式：先让办法看似成立，再让结果反向证明它失效。

## 9. 可复用选题与案例

- 可复用选题：当一个沟通办法反而让冲突更快发生。
- 可复用案例：角色改用受限表达后直接暴露真实态度。

## 10. 方法候选与可复用方法论

> 状态：候选，待跨卡三重验证。

### R - 原始证据

这是可回查的来源原句。

### I - 初步解释

通过限制表达空间，让人物无法继续使用模糊话术。

### A1 - 本条案例

角色在受限表达中直接说出真实立场。

### A2 - 未来触发场景

- 触发机制：新内容需要用错误解决方案制造结构反转时调用。
- 适用关系：来源关系不是硬条件，目标关系能承载同类冲突即可迁移。
- 可迁移场景：更换场景后错误方案与结果反证的因果仍成立时可以迁移。
- 不触发条件：只出现相同人物、场景、道具或题材词，但没有错误方案反证结构时不调用。

### E - 初步执行步骤

1. 建立人物和冲突；2. 给出解决方案；3. 增加限制；4. 用结果反证。

### B - 边界与反例

单卡不能证明稳定规律；纯信息内容不使用该结构。

## 11. 可复用模板

```text
当【人物】用【解决方案】处理【冲突】，先让它短暂成立，再通过【限制】推向【反转】。
替换人物、场景和冲突，但不复制来源事实和原句。
```

## 12. 证据缺口与候选判断

- 证据缺口：目前只有单卡证据，缺少跨内容重复出现的证明。
- 卡片判断：支持进入结构候选池。
- 跨卡状态：待验证。
"""


class AccountLearningCardContractTest(unittest.TestCase):
    def _record(self, platform: str = "douyin") -> NormalizedRecord:
        return NormalizedRecord(
            platform=platform,
            source_id="sample-1",
            source_file="candidate.json",
            title="一个看似正确的办法为什么反而失败",
            body="先给出解决办法，再通过两个案例展示限制条件，最后给出适用边界。",
            author_name="示例来源",
            published_at="2026-01-01",
            metrics={"likes": 10, "collects": 8, "comments": 2, "shares": 3},
            tags=["结构", "案例"],
            url="https://example.com/sample-1",
            video_download_url="",
            text_fingerprint="sample",
            account_name="示例来源",
            image_urls=["https://sns-webpic-qc.xhscdn.com/a.webp"] if platform == "xhs" else [],
        )

    def test_unified_card_passes_all_twelve_sections(self) -> None:
        result = validate_unified_text(unified_card_text())

        self.assertTrue(result.valid, result.errors)
        self.assertEqual(result.schema, CONTRACT_ID)
        self.assertEqual(len(result.sections), 12)

    def test_contract_supports_dynamic_structure_profiles(self) -> None:
        for content_form in ("剧情段子", "知识口播", "图文"):
            with self.subTest(content_form=content_form):
                result = validate_unified_text(unified_card_text(content_form))
                self.assertTrue(result.valid, result.errors)

    def test_generic_video_learning_generator_uses_unified_contract(self) -> None:
        scenarios = [
            (self._record("douyin"), ["剧情短剧"]),
            (self._record("douyin"), ["个人成长"]),
            (self._record("xhs"), ["个人成长"]),
        ]
        for record, directions in scenarios:
            with self.subTest(platform=record.platform, direction=directions[0]):
                text = selected_card_markdown(
                    record,
                    directions,
                    {"status": "video_transcribed_and_scenes_detected", "artifacts": {}},
                    {"status": "images_downloaded_ocr_completed", "artifacts": {}},
                    "这是来自逐字稿的可回查原始表达。",
                )
                result = validate_unified_text(text)
                self.assertTrue(result.valid, result.errors)

    def test_missing_old_strengths_and_ria_sections_fail(self) -> None:
        text = unified_card_text().replace("## 4. 核心观点", "## 4. 观点摘要").replace("### B - 边界与反例", "### 边界")

        result = validate_unified_text(text)

        self.assertIn("missing_section:4:核心观点", result.errors)
        self.assertIn("方法候选与可复用方法论:missing_B - 边界与反例", result.errors)

    def test_a2_requires_mechanism_based_transfer_fields(self) -> None:
        text = unified_card_text().replace("- 不触发条件：", "- 题材词边界：")

        result = validate_unified_text(text)

        self.assertIn("A2 - 未来触发场景:missing_不触发条件", result.errors)

    def test_quote_types_must_remain_separate(self) -> None:
        result = validate_unified_text(unified_card_text().replace("提炼表达（非原话）", "表达总结"))

        self.assertIn("金句与表达素材:missing_提炼表达", result.errors)

    def test_legacy_rich_card_is_read_compatible(self) -> None:
        sections = [
            "为什么值得学习", "核心观点", "内容结构", "表达素材与金句提炼", "视频层学习",
            "可复用案例", "可复用方法论", "可复用模板", "证据缺口/后续问题", "入库判断",
        ]
        text = "# 账号发布资产学习卡：历史样本\n\n" + "\n\n".join(
            f"## {index}. {name}\n\n- 有效历史内容" for index, name in enumerate(sections, 1)
        )

        result = validate_card_text(text)

        self.assertEqual(detect_schema(text), "legacy_rich_v1")
        self.assertTrue(result.valid, result.errors)

    def test_unified_card_passes_generic_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.md"
            path.write_text(unified_card_text(), encoding="utf-8")
            card = parse_card(path)
            evidence = EvidenceRecord(
                platform="douyin",
                transcript_available=True,
                selected_card_available=True,
                publish_title_available=True,
                publish_body_available=True,
                publish_topics_available=True,
                scene_artifacts_available=True,
                scene_status="completed",
            )

            result = audit_card(card, evidence)

        self.assertEqual(card.schema, CONTRACT_ID)
        self.assertEqual(result.machine_decision, "pass", result)

    def test_system_rule_and_contract_contain_no_account_specific_names(self) -> None:
        paths = [
            REPO_ROOT / "00_System/shareable/config/account_learning_card_contract.json",
            REPO_ROOT / "00_System/shareable/rules/统一学习卡产出标准.md",
            REPO_ROOT / "00_System/shareable/rules/账号专业学习提取与验证规范.md",
            REPO_ROOT / "00_System/shareable/skills/active/账号专业学习Skill_v2.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for account_name in ("姜胡说", "李宗恒", "小森林"):
            self.assertNotIn(account_name, text)

    def test_kb_cli_validates_any_unified_card_with_one_command(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as tmp:
            path = Path(tmp) / "card.md"
            path.write_text(unified_card_text(), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.kb.cli",
                    "--root",
                    str(REPO_ROOT),
                    "account-learning-validate-card",
                    "--path",
                    str(path),
                ],
                cwd=REPO_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["schema"], CONTRACT_ID)
        self.assertEqual(payload["section_count"], 12)

    def test_account_learning_route_loads_generic_card_contract(self) -> None:
        payload = json.loads((REPO_ROOT / "00_System/shareable/index/controller_routes.json").read_text(encoding="utf-8"))
        route = next(item for item in payload["routes"] if item["id"] == "account_learning")

        self.assertIn("00_System/shareable/config/account_learning_card_contract.json", route["read_first"])
        self.assertIn("00_System/shareable/rules/统一学习卡产出标准.md", route["read_first"])
        self.assertIn("tools.kb.cli account-learning-validate-card", route["tools"])


if __name__ == "__main__":
    unittest.main()
