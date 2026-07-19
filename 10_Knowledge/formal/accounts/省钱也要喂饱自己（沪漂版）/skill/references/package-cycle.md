# 完整发布包循环与查重

## 查重单位

图片生产以前置的完整图文发布包为单位。先判断套餐内容是否重复，再决定是否生成图片；默认不对同一发布包内部的功能页做视觉去重。

发布包签名至少包含：

- 内容轨道与核心角度；
- 2–3 个菜的规范食材键与做法键；
- 1 个主食及其类别；
- 主菜或主变量。

标题、菜品排列顺序、桌面、餐具、页面数量或文字改写不能把同一套餐变成新包。标注封面/无字净图、步骤/结果是同包内的不同功能页，不算重复。

## 套餐计划格式

先在内部工作区生成结构化计划，不把它写入 `发布文案.txt`：

```json
{
  "layout_policy_version": "1.7",
  "visual_policy_version": "2.0",
  "golden_package_id": "shengqian-visual-golden-v2",
  "golden_package_version": "2.0",
  "food_master_gate_required": true,
  "tableware_gate_required": true,
  "prompt_firewall_required": true,
  "table_locked": true,
  "calibration_gate_required": true,
  "parallel_generation_locked": true,
  "packages": [
    {
      "package_id": "meal_001",
      "core_angle": "下班后热乎家常一人食",
      "dishes": [
        {
          "name": "番茄烧豆腐",
          "ingredient_key": "番茄+豆腐",
          "technique": "烧",
          "role": "main",
          "complexity": "complex",
          "visual_risk": "medium",
          "texture_risk": "medium"
        },
        {
          "name": "蒜香上海青",
          "ingredient_key": "上海青",
          "technique": "炒",
          "role": "side",
          "complexity": "simple",
          "visual_risk": "low",
          "texture_risk": "low"
        }
      ],
      "staple": {
        "name": "烤玉米",
        "category": "corn",
        "complexity": "simple",
        "visual_risk": "medium",
        "texture_risk": "medium"
      },
      "food_master_required": true,
      "tableware_edit_policy": "optional_after_food_approval",
      "table_locked": true,
      "visual_lineage_manifest_required": true,
      "pages": [
        {"role": "cover", "subject": "complete_meal"},
        {"role": "clean_cover", "subject": "complete_meal"},
        {"role": "tutorial", "subject": "番茄烧豆腐", "layout_family": "hero_plus_steps"},
        {"role": "result", "subject": "番茄烧豆腐"},
        {"role": "result", "subject": "蒜香上海青"},
        {"role": "result", "subject": "烤玉米"}
      ]
    }
  ],
  "history_packages": []
}
```

`ingredient_key` 用主要食材归一同义菜名，`technique` 区分真正不同的做法；不要只靠发布标题查重。

## 批次循环

1. 先生成套餐计划，不生成图片。
2. 每套必须有 2–3 个菜和 1 个主食；菜与主食都来自当次真实计划或素材。
3. 将规范套餐组合写入 `topic-memory-check` 的 `angle` 和 `mechanism`，先与既有生产历史查重。
4. 为每个菜与主食分别声明 `visual_risk` 与 `texture_risk`；高视觉风险项必须写 `real_reference_planned: true`。同一套餐最多两个 `texture_risk=high` 单元，避免完整餐同时要求过多精细纹理。还要声明食物母版门、可选餐具后置门、提示词防火墙、桌面锁定和视觉血缘清单均为必需，批量生成初始保持锁定。
5. 为每张教程页声明 `layout_family`，再运行 `python skill/scripts/validate_package_batch.py --input {内部计划.json}`，拦截同批重复、主食不轮换、复杂菜漏拆步骤、教程版式重复和高风险食材未计划真实参考。
6. 只有计划通过后，才按 `visual-golden.md` 与 `visual-lineage.md` 先生产并验收食物母版；餐具只可在食物通过后局部替换。最终母版、教程和结果三页校准通过后，才解锁其余独立页面。
7. 交付后登记选题与生产记忆；后续批次从已登记历史继续检查。

## 主食轮换

- 主食是套餐独立单元，不默认固定白米饭。
- 正式卡已出现白米/杂粮或紫米饭、玉米、红薯、贝贝南瓜等形态；按本批真实菜单轮换，不虚构不合场景的主食。
- 两套及以上批量生产时，至少包含两类主食，且不能全部属于米饭类；连续两套不使用同一主食类别。
- 主食若只有承接完整餐的作用，给结果图即可；若有烤制节点、掰开切面、颗粒或焦边等价值，可获得教程或质感特写。

## 动态步骤页

先给每个菜和主食标复杂度：

- `simple`：单一动作、无关键转折；通常只给结果或与其它简单单元合并交付。
- `medium`：有 2–3 个必要节点或一个易失败状态；视收藏价值决定是否压成一张步骤页。
- `complex`：存在预处理、调味、受热转换、翻面/收汁/成形等多阶段；必须获得自己的步骤拆解页，通常另给结果或质感页。

页面数量由复杂度决定，不固定为五图，也不固定只拆一道菜：

- 一道复杂菜：至少一张对应步骤页。
- 两道复杂菜：两道分别获得步骤页。
- 三道都复杂时，不为追求菜品数量硬塞页面；优先简化套餐或拆分为两个发布包。确需保留时，每道复杂菜都要有可解释的页面价值。
- 简单菜不得为了凑固定页数重复展示相同结果。

常见而非固定的顺序是：标注完整餐 → 可选无字净图 → 可选主食质感 → 复杂菜 A 步骤/结果 → 复杂菜 B 步骤/结果（若有）→ 简单菜或主食结果。正常可在 5–8 张之间变化；素材与信息价值优先于页数。

教程布局也属于批次计划：四宫格只是一种 `layout_family`。四张及以上教程页时四宫格占比不得超过 40%；六张及以上至少使用三类布局。不能通过把同一画面重复裁切、删除必要步骤或伪造布局名来通过校验。

## 证据坐标

- `xhs:68cb6d6700000000120219c8`：牛肋条教程 + 基围虾教程；玉米主食。
- `xhs:68f9fd8d000000000700215d`：白灼虾教程；紫米饭颗粒特写。
- `xhs:6901f2f500000000070140c5`：牛肉教程 + 开背虾教程；红薯切面特写。
- `xhs:6917060e000000000703382f`：蒜蓉虾教程 + 贝贝南瓜教程；简单菜只给结果。

这些卡只校准页面分配机制，不允许复制原菜名组合、原句、价格或效果主张。
