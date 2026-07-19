#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path


EXPECTED_H1 = ["发布标题", "发布文案", "话题"]
MENU_MARKERS = (
    "🍅", "🥬", "🍚", "🥘", "🥦", "🌽", "🍳", "🥩", "🍗", "🐟",
    "🥗", "🥕", "🍆", "🍄", "🥚", "🍤", "🥒", "🍠", "🥔", "🍜", "🍲",
)
APPENDIX_MARKERS = ("✨碎碎念", "📖读书笔记")
ACTION_WORDS = (
    "切", "洗", "焯", "煎", "炒", "蒸", "煮", "焖", "拌", "倒入", "放入",
    "加入", "加水", "调味", "收汁", "出锅", "按电饭煲", "烤", "腌",
)
HEAT_WORDS = ("大火", "中火", "小火", "中小火", "中大火", "水开", "热锅")
END_STATE_WORDS = (
    "出汁", "定型", "微黄", "变色", "凝固", "断生", "收汁", "收浓", "透亮",
    "挂在", "熟透", "熟", "香味", "裹上", "沸腾",
)
GENERIC_APPENDIX_PHRASES = (
    "红黄绿都有", "看着就很有食欲", "一个人也要好好吃饭", "好好爱自己",
    "治愈自己", "幸福感满满",
)


def validate_path(path: Path) -> list[str]:
    if path.suffix.lower() != ".txt":
        return ["交付文案必须保存为发布文案.txt，不得使用 Markdown 或其他扩展名"]
    return []


def split_sections(text: str) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    matches = list(re.finditer(r"^# ([^#\n]+)\s*$", text, re.MULTILINE))
    names = [match.group(1).strip() for match in matches]
    if names != EXPECTED_H1:
        errors.append(f"一级区块必须且只能是：{'、'.join(EXPECTED_H1)}；当前为：{names}")
        return {}, errors
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[names[index]] = text[start:end].strip()
    return sections, errors


def is_menu_heading(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(MENU_MARKERS)


def is_appendix_heading(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(APPENDIX_MARKERS)


def validate_text(text: str) -> list[str]:
    sections, errors = split_sections(text)
    if errors:
        return errors

    title = sections["发布标题"]
    body = sections["发布文案"]
    tags = sections["话题"]

    if not title.startswith("独居一人食｜"):
        errors.append("自然单餐标题必须以“独居一人食｜”建立账号入口")

    lines = body.splitlines()
    menu_indexes = [index for index, line in enumerate(lines) if is_menu_heading(line)]
    appendix_indexes = [index for index, line in enumerate(lines) if is_appendix_heading(line)]
    if len(menu_indexes) < 3:
        errors.append("正文至少要完整覆盖主菜、配菜和主食三个菜单段")
        return errors

    boundaries = sorted(menu_indexes + appendix_indexes + [len(lines)])
    menu_blocks: list[tuple[str, str]] = []
    for index in menu_indexes:
        next_boundary = min(boundary for boundary in boundaries if boundary > index)
        heading = lines[index].strip()
        content = "\n".join(lines[index + 1 : next_boundary]).strip()
        menu_blocks.append((heading, content))
        if not content:
            errors.append(f"菜单段“{heading}”只有名称，没有做法、执行标准或结果")
        elif not any(word in content for word in ACTION_WORDS + END_STATE_WORDS):
            errors.append(f"菜单段“{heading}”缺少可执行动作或结束状态")

    main_heading, main = menu_blocks[0]
    if "一人份" not in main:
        errors.append(f"主菜“{main_heading}”缺少一人份核心食材说明")
    numbered_steps = re.findall(r"(?m)^\s*\d+\.\s+", main)
    if len(numbered_steps) < 3:
        errors.append(f"主菜“{main_heading}”至少需要三个编号步骤")
    measures = re.findall(r"\d+(?:\.\d+)?\s*(?:g|ml|克|个|颗|勺|瓣|片|根|盒)", main, re.IGNORECASE)
    if len(measures) < 3:
        errors.append(f"主菜“{main_heading}”的食材或调味量不足以复刻")
    if not any(word in main for word in HEAT_WORDS):
        errors.append(f"主菜“{main_heading}”缺少火候")
    time_pattern = r"\d+(?:\.\d+)?(?:\s*[–~\-至]\s*\d+(?:\.\d+)?)?\s*(?:分钟|分|秒)"
    if not re.search(time_pattern, main):
        errors.append(f"主菜“{main_heading}”缺少关键时间")
    if not any(word in main for word in END_STATE_WORDS):
        errors.append(f"主菜“{main_heading}”缺少肉眼可判断的结束状态")

    appendix_headings = [lines[index].strip() for index in appendix_indexes]
    if len(appendix_headings) > 1:
        errors.append("自然单餐默认最多一种叙事附言，不能同时出现碎碎念和读书笔记")
    if "碎碎念📖" in body:
        errors.append("不得使用“碎碎念📖”混合标题")
    if appendix_indexes:
        start = appendix_indexes[0] + 1
        appendix = "\n".join(lines[start:]).strip()
        if not appendix:
            errors.append("附言标题后没有正文")
        if any(phrase in appendix for phrase in GENERIC_APPENDIX_PHRASES):
            errors.append("附言包含已知泛化表达，应改为本餐具体动作、口感或搭配感受")

    hashtags = re.findall(r"#[^#\s]+", tags)
    if len(hashtags) < 5:
        errors.append("话题少于五个，未完整覆盖账号人群、用餐形式与菜品")
    if "#独居" not in hashtags or "#一人食" not in hashtags:
        errors.append("话题必须包含账号核心人群标签 #独居 和 #一人食")

    return errors


def self_test() -> int:
    good = """# 发布标题

独居一人食｜今天吃番茄豆腐！

# 发布文案

🍅番茄豆腐

一人份：豆腐250g、番茄300g、蒜2瓣。

1. 豆腐切块；
2. 中小火煎2–3分钟，表面定型微黄；
3. 番茄中火炒2分钟至出汁，放回豆腐收汁。

🥬青菜

水开焯1分钟，炒香后出锅。

🍚米饭

大米65g，加水煮熟。

✨碎碎念

番茄汁多留一点，拌饭刚刚好。

# 话题

#独居 #一人食 #独居一人食 #家常菜 #番茄豆腐
"""
    bad = """# 发布标题

独居一人食｜今天吃番茄牛肉滑蛋！

# 发布文案

🥘番茄牛肉滑蛋

牛肉加1勺生抽和少许淀粉，炒熟即可。

🥦西兰花

焯熟即可。

🌽蒸玉米

✨碎碎念

这一顿红黄绿都有，看着就很有食欲！

# 话题

#独居 #一人食 #家常菜 #做饭日记 #一人食食谱
"""
    if validate_path(Path("发布文案.txt")) or validate_text(good):
        print("SELF-TEST FAIL: 合格样例被误判")
        return 1
    if not validate_path(Path("发布文案.md")):
        print("SELF-TEST FAIL: Markdown 扩展名没有被拦截")
        return 1
    if not validate_text(bad):
        print("SELF-TEST FAIL: 退化样例没有被拦截")
        return 1
    print("SELF-TEST PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="校验省钱也要喂饱自己账号的自然单餐发布文案")
    parser.add_argument("--input", type=Path, help="发布文案.txt 路径")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.input:
        parser.error("--input 为必填项")
    errors = validate_path(args.input)
    if not errors:
        errors = validate_text(args.input.read_text(encoding="utf-8"))
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
