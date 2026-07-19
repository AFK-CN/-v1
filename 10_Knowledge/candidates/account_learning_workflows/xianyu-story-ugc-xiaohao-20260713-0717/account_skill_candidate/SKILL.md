---
name: xianyu-story-ugc
description: Create, rewrite, or review publish-ready 闲鱼故事类 UGC titles, body copy, hashtags, and evidence-grounded visual packages from supplied facts and images. Use for old-item memories, transaction surprises, local services, skill monetization, hobby exits, short Xianyu anecdotes, cover or carousel planning, or requests to reduce AI-like sentimentality while preserving factual and privacy boundaries.
---

# 闲鱼故事 UGC

正式版本：`1.3`。这是闲鱼故事类 UGC 发布任务中心，不代表“小浩”或任何个人账号。

把用户提供的真实素材写成可发布的闲鱼故事内容。始终先保留事实链，再选择结构；不要从“闲鱼不只是交易平台”之类的平台口号开场。

## 输入门

先识别：

- 物件、服务或交易事件是什么。
- 哪些人物、动作、聊天、金额、时间和结果有真实依据。
- 有哪些原始图片；每张是物件实拍、平台页、聊天/反馈、服务过程还是结果证据。
- 哪些信息未知、不可公开或只允许改写。
- 需要完整故事还是短交易奇遇。

默认直接生成无占位符的第一人称完整成稿，不在写作前等待用户逐项确认，也不输出“虚构”“情景创作”等干扰发布的标签。用户输入仍是事实边界；缺少精确金额、身份、聊天原句、收入或外部结果时，使用不依赖这些数据的一般化写法，不伪造原句、截图或平台成绩。用户明确要求严格事实核对且最低事实不足时，才集中请求补充。

## 方法路由

先读取 [methods.md](references/methods.md)，只选一个主方法：

- 普通交易需要提炼价值：`xugc-m01`。
- 旧物痕迹、回忆和下一站：`xugc-m02`。
- 主动补价、退还、赠物或特殊用途：`xugc-m03`。
- 同城服务、手作或技能变现：`xugc-m04`。
- 投入、搁置、退坑和解：`xugc-m05`。
- 单条聊天或一次小反转：`xugc-m06`。
- 需要生活化缓冲时，最多再加 `xugc-m07` 作为表达支持。

当用户只要求批量生成且未指定题材时，默认优先实物相关的 `xugc-m01/m02/m03/m05/m06`。`xugc-m04` 同城服务、手作或技能变现仍保留，但只在用户明确要求服务、接单或技能变现方向时进入；用户当次指定优先。

不要因出现“闲鱼、旧物、青春、陌生人、治愈”等词就触发方法。先匹配因果机制，再用边界排除。

需要封面、配图或多图顺序时，再读取 [visual.md](references/visual.md)，选择一个视觉模式：

- 有真实平台页/聊天和实物或结果图：`platform_evidence_chain`。
- 重点是物件状态、瑕疵或现场：`object_truth_sequence`。
- 核心反差可压成一句话且有后续证据图：`hook_card_then_proof`。
- 只有一张有效素材：`single_visual`。

视觉模式是内容方法的证据层，不取代正文主方法。

## 生产流程

1. 批量任务先建立结构差异表，为每条分配不同的开头、推进方式、篇幅和结尾；不得写完后只替换物件名。
2. 从事实中选择一个可见入口：物件状态、人物动作、交易消息或服务步骤。
3. 写清人物处境、阻力和变化，不先解释道理。
4. 按所选主方法完成结构；短奇遇在转折完成后及时停句。
5. 只有结果支撑时才补一句价值解释；同批内容不得每条都升华。
6. 需要补图且用户未提供原图时，每条默认生成 1 张与核心实物一致的生活化竖图；画面内不添加 AI 标识、水印、标题或标签。生成来源只进入内部视觉记录，不把补图当作交易证据。
7. 按 [production.md](references/production.md) 分别维护内部结构化包与用户可见发布稿。
8. 交付标题、正文、话题或完整发布包时，必须读取 [publishing-copy.md](references/publishing-copy.md)，按“短标题承诺变化、正文完成事实链、话题限定平台和具体场景”组织发布层。
9. 按 [style.md](references/style.md) 执行批次结构去同质化，再按 [acceptance.md](references/acceptance.md) 验收。
10. 单条机器验收运行 `python scripts/validate_output.py <package.json>`；两条及以上批量任务另运行 `python scripts/validate_batch.py <batch.json>`。

## 输出

默认用户可见交付：

- 发布标题。
- 1 张与正文核心实物一致的图片（用户明确要求多图时除外）。
- 自然分段的完整正文。
- 紧接正文末尾的 2—8 个话题，不单独显示“话题：”。

事实边界、内部方法追踪、图片来源、生成来源、隐私检查、topic_id、content_id 和 Skill 版本继续保存在内部结构化包，不混入用户可见发布稿。

## 硬边界

- 只学习本任务已验证的 7 个方法，不复制其他账号风格。
- 视觉只学习本轮 230 张图验证出的 4 个已批准视觉机制，不复制固定字体、卡通形象、滤镜或品牌配色。
- 不生成仿造的聊天、订单、评价、商品页或“买家实拍”；没有真实截图时改用物件实拍或文字说明。
- 人脸、头像昵称、联系方式、订单号和地址必须逐项检查；图片只能支持可见事实。
- 不承诺爆款、流量、转化或平台效果。
- 不把短交易奇遇扩写成虚构人生，也不把每篇长故事都写成治愈和升华。
- 不连续复用“不是A而是B”“原来……”“真正的……”等固定结尾。

如果项目生产记忆已配置，生成新选题前整批调用 `topic-memory-check --account-skill-id xianyu_story_ugc_task`；开始生产时调用 `topic-memory-record`；内容交付后调用 `production-memory-record`，登记账号 Skill 版本 `1.3`。只读取少量查重摘要，不加载完整生产数据库。

更完整的证据与禁区见 [boundaries.md](references/boundaries.md)。

## 升级兼容

升级本账号 Skill 前必须读取 `UPGRADE_COMPATIBILITY.json` 和 `references/upgrade-compatibility.md`。旧能力 ID 不得静默丢失；替换或弃用必须经用户确认并保留回滚。整体账号升级仍只能使用本账号证据，禁止跨账号合并能力、规则、素材和正例。
