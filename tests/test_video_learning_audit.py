import json
import tempfile
import unittest
from pathlib import Path

from tools.video_learning_audit import (
    AuditConfig,
    EvidenceRecord,
    audit_card,
    find_repeated_passages,
    find_similarity_pairs,
    parse_card,
    run_audit,
    text_support_score,
)


def build_card(
    *,
    title: str = "把问题做成产品",
    direction: str = "赚钱",
    method: str | None = None,
    source_id: str = "1001",
    account: str = "测试账号",
) -> str:
    method = method or "- 问题验证法：先记录具体问题，再交付一个最小方案，最后根据付费反馈调整。"
    return f"""# 视频深度学习卡：{title}

source_id: {source_id}
原视频链接：https://www.douyin.com/video/{source_id}
账号：{account}
平台：抖音
主方向：{direction}
辅方向：创业
学习批次：20260621-X
状态：confirmed_learned

## 1. 为什么值得学习

- 这条把普通人的问题观察变成了可以验证的交付动作。

## 2. 核心观点

- 不要先找抽象项目，先找到反复出现、有人愿意付出成本的问题。
- 用一次真实交付验证需求，再把重复部分沉淀成产品。

## 3. 内容结构

- 黄金 3 秒钩子：普通人怎么找到第一个能赚钱的问题。
- 开头钩子：从工作里的具体麻烦切入。
- 问题定义：只想项目，不看真实需求。
- 关键转折：把问题交付给一个具体用户。
- 论证方式：个人案例加步骤拆解。
- 结尾行动指向：今天记录三个重复问题。
- 收尾/互动引导：未明确。

## 4. 表达素材与金句提炼

- 候选金句：赚钱不是先找项目，是先解决一个真实问题。
- 候选短句：先问题，后产品。
- 候选问题句：谁愿意为这个问题付出成本？
- 反常识表达：先交付，再学习。
- 证据说明：来自逐字稿中的问题、方案和交付段落。

## 5. 视频层学习

- 标题/封面承诺：给普通人一条低门槛路径。
- 画面或场景表达：单人口播，没有额外画面判断。
- 节奏与停顿：先否定找项目，再给三步动作。
- 信息密度：中等。
- 评论区可能触发点：如何判断问题是否值得付费。

## 6. 可复用案例

- 同事反复问表格整理方法，先代做一次，再沉淀成模板。

## 7. 可复用方法论

{method}

## 8. 可复用模板

```text
最近谁反复问我___？
我能不能先替他完成一次___？
如果有人愿意付出成本，再把重复步骤做成___。
```

## 9. 证据缺口/后续问题

- 单个案例不能证明所有问题都能形成产品，需要真实付费验证。

## 10. 入库判断

- 可入库：沉淀“问题—最小交付—付费验证—产品化”方法，并保留单案例边界。
"""


class VideoLearningAuditTests(unittest.TestCase):
    def test_run_audit_uses_profile_config_not_hardcoded_account_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = "demo_profile"
            card_path = root / f"01_Case_Cleaning/video_learning/learned_cards/{profile}/赚钱/cards/01_1001_测试卡.md"
            card_path.parent.mkdir(parents=True)
            card_path.write_text(build_card(account="测试账号"), encoding="utf-8")
            scope_path = root / f"01_Case_Cleaning/content_rough_scan/{profile}/deep_learning_scope.json"
            scope_path.parent.mkdir(parents=True)
            scope_path.write_text(
                json.dumps({"items": [{"source_id": "1001", "card_path": card_path.relative_to(root).as_posix()}]}, ensure_ascii=False),
                encoding="utf-8",
            )
            selected = root / "01_Case_Cleaning/video_learning/selected_deep_cards/douyin_1001.md"
            selected.parent.mkdir(parents=True)
            selected.write_text("video_analysis_status: video_transcribed_scene_ok\n", encoding="utf-8")
            artifact = root / "01_Case_Cleaning/video_learning/video_artifacts/douyin_1001"
            artifact.mkdir(parents=True)
            (artifact / "transcript.json").write_text(json.dumps({"text": "测试"}, ensure_ascii=False), encoding="utf-8")

            result = run_audit(root, AuditConfig.for_profile(profile))
            report = root / f"01_Case_Cleaning/video_learning/learned_cards/{profile}/audit/machine_audit.md"
            wrong_report = root / "01_Case_Cleaning/video_learning/learned_cards/jianghushuo/audit/machine_audit.md"
            report_exists = report.exists()
            wrong_report_exists = wrong_report.exists()

        self.assertEqual(result["profile_id"], profile)
        self.assertEqual(result["scope_count"], 1)
        self.assertTrue(report_exists)
        self.assertFalse(wrong_report_exists)

    def test_missing_required_section_fails_structure_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.md"
            path.write_text(build_card().replace("## 6. 可复用案例\n\n- 同事反复问表格整理方法，先代做一次，再沉淀成模板。\n\n", ""), encoding="utf-8")

            card = parse_card(path)
            result = audit_card(card, EvidenceRecord(transcript_available=True, selected_card_available=True))

        self.assertIn("missing_section:可复用案例", result.structure_errors)
        self.assertNotEqual(result.machine_decision, "pass")

    def test_shallow_method_and_template_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.md"
            text = build_card(method="- 持续努力，不断成长。")
            text = text.replace(
                "```text\n最近谁反复问我___？\n我能不能先替他完成一次___？\n如果有人愿意付出成本，再把重复步骤做成___。\n```",
                "```text\n持续努力。\n```",
            )
            path.write_text(text, encoding="utf-8")

            result = audit_card(parse_card(path), EvidenceRecord(transcript_available=True, selected_card_available=True))

        self.assertIn("method_lacks_action", result.depth_risks)
        self.assertIn("template_too_shallow", result.depth_risks)
        self.assertNotEqual(result.machine_decision, "pass")

    def test_similarity_finds_keyword_swapped_cards_but_ignores_template_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.md"
            second = root / "b.md"
            third = root / "c.md"
            first.write_text(build_card(direction="赚钱", source_id="1001"), encoding="utf-8")
            second.write_text(build_card(direction="创业", source_id="1002"), encoding="utf-8")
            third.write_text(build_card(title="完全不同的表达", source_id="1003").replace("问题验证法", "公开学习法").replace("真实交付", "公开复盘"), encoding="utf-8")

            pairs = find_similarity_pairs([parse_card(first), parse_card(second), parse_card(third)], threshold=0.90)

        ids = {(pair.left_source_id, pair.right_source_id) for pair in pairs}
        self.assertIn(("1001", "1002"), ids)
        self.assertNotIn(("1001", "1003"), ids)

    def test_scene_claim_is_flagged_when_scene_analysis_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "card.md"
            path.write_text(build_card().replace("单人口播，没有额外画面判断", "镜头切换到办公室和地铁，字幕变成红色"), encoding="utf-8")

            evidence = EvidenceRecord(
                transcript_available=True,
                selected_card_available=True,
                scene_status="video_transcribed_scene_failed",
            )
            result = audit_card(parse_card(path), evidence)

        self.assertIn("unsupported_scene_detail", result.evidence_risks)
        self.assertNotEqual(result.machine_decision, "pass")

    def test_similarity_flags_three_of_four_key_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.md"
            second = root / "b.md"
            first.write_text(build_card(source_id="1001"), encoding="utf-8")
            second_text = build_card(direction="创业", source_id="1002")
            second_text = second_text.replace(
                "- 单个案例不能证明所有问题都能形成产品，需要真实付费验证。",
                "- 这条内容的全部证据边界已经改写成完全不同的风险说明，不能与第一张卡共用。",
            )
            second.write_text(second_text, encoding="utf-8")

            pairs = find_similarity_pairs([parse_card(first), parse_card(second)], threshold=0.90)

        self.assertEqual(len(pairs), 1)

    def test_repeated_passages_require_three_cards_and_ignore_short_boilerplate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cards = []
            repeated = "这是一段被三张卡机械复制的长句，只有方向名称不同，没有提供新的具体证据或动作。"
            for index, direction in enumerate(("赚钱", "创业", "自媒体"), start=1):
                path = root / f"{index}.md"
                text = build_card(direction=direction, source_id=f"100{index}")
                text = text.replace("- 这条把普通人的问题观察变成了可以验证的交付动作。", f"- {repeated}")
                path.write_text(text, encoding="utf-8")
                cards.append(parse_card(path))

            passages = find_repeated_passages(cards, min_cards=3)

        self.assertTrue(any(repeated in passage.text for passage in passages))
        self.assertFalse(any(passage.text == "未明确" for passage in passages))

    def test_text_support_score_separates_supported_and_unrelated_claims(self):
        evidence = "普通人赚钱不要先找风口，先找到真实问题，整理答案，完成一次小额交付。"

        supported = text_support_score("先找到真实问题，再整理答案并完成小额交付。", evidence)
        unrelated = text_support_score("镜头切换到办公室，字幕变成红色，背景音乐突然加快。", evidence)

        self.assertGreater(supported, 0.70)
        self.assertLess(unrelated, 0.15)


if __name__ == "__main__":
    unittest.main()
