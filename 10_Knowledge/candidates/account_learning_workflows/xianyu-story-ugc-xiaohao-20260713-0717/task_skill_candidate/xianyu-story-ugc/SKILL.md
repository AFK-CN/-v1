---
name: xianyu-story-ugc
description: Create, rewrite, or review publish-ready 闲鱼故事类 UGC titles, body copy, hashtags, and evidence-grounded visual packages from supplied facts and images. Use for old-item memories, transaction surprises, local services, skill monetization, hobby exits, short Xianyu anecdotes, cover or carousel planning, or requests to reduce AI-like sentimentality while preserving factual and privacy boundaries.
---

# 闲鱼故事 UGC

把用户提供的真实素材写成可发布的闲鱼故事内容。始终先保留事实链，再选择结构；不要从“闲鱼不只是交易平台”之类的平台口号开场。

## 输入门

先确认：

- 物件、服务或交易事件是什么。
- 哪些人物、动作、聊天、金额、时间和结果有真实依据。
- 有哪些原始图片；每张是物件实拍、平台页、聊天/反馈、服务过程还是结果证据。
- 哪些信息未知、不可公开或只允许改写。
- 需要完整故事还是短交易奇遇。

事实不足时保留占位或请求补充；不得编造第一人称经历、聊天、收入、买家身份、图片内容、平台截图或发布效果。

## 方法路由

先读取 [methods.md](references/methods.md)，只选一个主方法：

- 普通交易需要提炼价值：`xugc-m01`。
- 旧物痕迹、回忆和下一站：`xugc-m02`。
- 主动补价、退还、赠物或特殊用途：`xugc-m03`。
- 同城服务、手作或技能变现：`xugc-m04`。
- 投入、搁置、退坑和解：`xugc-m05`。
- 单条聊天或一次小反转：`xugc-m06`。
- 需要生活化缓冲时，最多再加 `xugc-m07` 作为表达支持。

不要因出现“闲鱼、旧物、青春、陌生人、治愈”等词就触发方法。先匹配因果机制，再用边界排除。

需要封面、配图或多图顺序时，再读取 [visual.md](references/visual.md)，选择一个视觉模式：

- 有真实平台页/聊天和实物或结果图：`platform_evidence_chain`。
- 重点是物件状态、瑕疵或现场：`object_truth_sequence`。
- 核心反差可压成一句话且有后续证据图：`hook_card_then_proof`。
- 只有一张有效素材：`single_visual`。

视觉模式是内容方法的证据层，不取代正文主方法。

## 生产流程

1. 从事实中选择一个可见入口：物件状态、人物动作、交易消息或服务步骤。
2. 写清人物处境、阻力和变化，不先解释道理。
3. 按所选主方法完成结构；短奇遇在转折完成后及时停句。
4. 只有结果支撑时才补一句价值解释；平台价值必须后置。
5. 需要图片时，先做图片事实表和隐私检查，再按 `visual.md` 给出 1—5 张推荐图序；不能把推荐顺序写成已核验发布顺序。
6. 按 [production.md](references/production.md) 输出标题、正文、话题、事实边界和可选视觉包。
7. 按 [style.md](references/style.md) 去除模板腔和过度包装，再按 [acceptance.md](references/acceptance.md) 验收。
8. 需要机器验收时，运行 `python scripts/validate_output.py <package.json>`。

## 输出

默认交付：

- 发布标题：1 个主标题，可附 2 个不重复结构的备选。
- 发布正文：完整可发，不只给提纲。
- 发布话题：2—8 个，优先具体物件/服务和闲鱼场景。
- 事实边界：列明未核验或禁止补造的信息。
- 视觉包（有图片任务时）：视觉模式、推荐图序、每张图的功能、来源依据和隐私处理。
- 内部方法追踪：主方法、可选支持方法、完成证据。

## 硬边界

- 只学习本任务已验证的 7 个方法，不复制其他账号风格。
- 视觉只学习本轮 230 张图验证出的 4 个候选机制，不复制固定字体、卡通形象、滤镜或品牌配色。
- 不生成仿造的聊天、订单、评价、商品页或“买家实拍”；没有真实截图时改用物件实拍或文字说明。
- 人脸、头像昵称、联系方式、订单号和地址必须逐项检查；图片只能支持可见事实。
- 不承诺爆款、流量、转化或平台效果。
- 不把短交易奇遇扩写成虚构人生，也不把每篇长故事都写成治愈和升华。
- 不连续复用“不是A而是B”“原来……”“真正的……”等固定结尾。

如果项目生产记忆已配置，生成新选题前调用 `topic-memory-check`；用户确认选题后调用 `topic-memory-record`；内容交付后调用 `production-memory-record`。只读取查重摘要，不加载完整生产数据库。

更完整的证据与禁区见 [boundaries.md](references/boundaries.md)。
