---
name: account-shengqian-weibao-hupiao
description: Produce Xiaohongshu one-person-meal topics, image-text page plans, titles, captions, and complete publishing packages using the formally validated positioning, topic, structure, expression, evidence, and commercial-isolation rules of 省钱也要喂饱自己（沪漂版）. Use only when the user explicitly requests this account or its production style.
---

# 省钱也要喂饱自己（沪漂版）账号生产

账号 Skill 版本：2.1

使用本账号正式方法和证据生产小红书一人食内容。不要把本 Skill 当作通用减脂、营养、食谱或广告模板。

## 生产前

1. 先确认用户明确调用本账号，并明确目标人群、用餐场景、真实素材和输出形式。
2. 生成图片前先按 `references/package-cycle.md` 形成完整发布包计划；将规范菜品组合、主食和核心角度写入候选，再调用 `topic-memory-check --account-skill-id shengqian_weibao_hupiao` 检查历史，并运行批次脚本检查同批重复与视觉参考计划。只读取少量冲突摘要，不读取完整生产数据库。
3. 先分轨为自然内容、商品广告或平台项目；三类证据不得互相抬升。
4. 从 `../METHOD_INDEX.json` 只选一个主冲突方法和一个主结构；支持方法必须沿同一因果链，逐项消融后无信息损失的就删除。
5. 只调用本账号正式方法和必要正式单卡；按需读取 `../methods/` 与 `../directions/{方向}/cards/`，不得全盘读取账号证据。
6. 只要交付标题、正文、话题或完整发布包，必须读取 `references/publishing-copy.md`；不要只用 `m07` 的一句摘要代替发布文案生产规则。
7. 生产自然单餐发布文案时，必须同时读取 `references/publishing-copy-golden.md`。它是整篇信息密度和菜单覆盖的验收基线，不是可照抄的固定菜谱。
8. 用户指出某个既有成稿为合格基线时，先与该成稿做结构回归，再改规则或正文；不得只修用户最后指出的局部症状。
9. 不得复制其他账号规则；标题、页面和正文必须由本账号已验证机制与目标素材共同决定。
10. 升级前先读取 `UPGRADE_COMPATIBILITY.json` 与 `references/upgrade-compatibility.md`。v1.0–v2.0 的能力 ID 必须逐项保留；除非用户在同账号提案中明确批准替换/弃用并提供回滚，否则不得用新规则覆盖旧能力。

## 生产

按需读取：

- `references/production.md`：四类正式结构、方法组合和页面顺序。
- `references/style.md`：固定母题、单一变量、正文指纹与防模板规则。
- `references/publishing-copy.md`：标题、菜谱正文、计量、收尾、话题与不同内容轨道的完整发布文案规则。
- `references/publishing-copy-golden.md`：自然单餐合格样稿的结构不变量、允许变化项与已知失败模式。
- `references/visual-production.md`：账号黑灰桌面与手机直闪基线、食物母版后可选餐具替换、提示词防火墙、固定手部身份和完整发布包目录。
- `references/visual-golden.md`：账号原图独占真实感、用户认可生成图只做连续性回归的视觉参考角色隔离。
- `references/visual-lineage.md`：食物母版门、可选餐具材质门、最终母版单跳派生、三页校准与 `visual-lineage.json`。
- `references/package-cycle.md`：完整发布包签名、批内查重、2–3 菜加变化主食和按复杂度动态分配步骤页。
- `references/boundaries.md`：减脂、热量、营养、价格、熟度、商业和平台边界。
- `references/acceptance.md`：发布前逐项验收。
- `references/upgrade-compatibility.md`：本账号历史能力账本、显式替换、五页回归包和升级回滚边界。

自然单餐先确定 2–3 个菜和 1 个变化主食，完成发布包级历史查重与批内查重，再按操作价值分配教程；两道复杂菜应分别获得步骤页，页面总数不固定。每张教程页必须在内部计划声明 `layout_family`；四宫格只是一种可选版式，同批按 `visual-production.md` 和批次脚本轮换。正文按 `publishing-copy.md` 执行，并用 `publishing-copy-golden.md` 检查整篇信息密度；不强制附言，不虚构真人经历；自然单餐默认最多选择一种叙事附言。

需要配图时先运行黄金包校验。完整餐食物母版只引用账号 `account_source` 中标为 `master_reference` 的真实完整餐/封面，不引用用户认可生成图、食材近景或旧材质锚点。食物、构图、黑灰桌面、手机直闪和随手拍质感通过第一道门后，才允许按 `visual-production.md` 可选只换餐具；桌面不得更换，餐具编辑必须通过食物、光线、构图保持不变的第二道门。最终母版锁定后再生产一张高风险教程和一张结果图；三页校准未通过前禁止展开或并行。每个独立轮播文件从最终母版单跳派生，任何出现手的页面使用固定手部锚点。

用户认可的五页成套结果必须按 `assets/visual/regression-packages/accepted-tomato-tofu-v1/manifest.json` 作为一个有序回归包整体检查，不得拆成互不关联的五张参考。该包的无字完整餐只承担历史连续性母图，不是食物真实感母版或生图输入；新生产仍以账号原图建立食物母版。

反例包仅用于验收规则，不得作为生图参考或账号证据；生产清单引用任一 `user_rejected_output` 资产直接失败。

## 生产后

1. 完整发布包保存到 `美食系列/{菜名或选题名}/`，文件夹同时包含全部图片和 `发布文案.txt`；不得另存同名 `.md`。
2. `发布文案.txt` 只保留“发布标题、发布文案、话题”三个一级区块；不得混入食材清单、页面计划、发布检查、执行口径或内部溯源。
3. 自然单餐交付前必须运行 `python skill/scripts/validate_publishing_copy.py --input <发布文案.txt>`；失败时先修稿并重跑，禁止带失败项交付。
4. 对照 `publishing-copy-golden.md` 复核：主菜信息密度、每道菜/主食覆盖、附言具体性均不得低于合格基线。
5. 图像验收后保存 `visual-lineage.json`，运行 `validate_visual_package.py` 并写入通过状态；发布文案运行原有校验。两项都通过后才登记 `topic_id`、`content_id` 和账号 Skill 版本。
6. 选题确认后执行 `topic-memory-record --account-skill-id shengqian_weibao_hupiao`；成品交付后执行 `production-memory-record --account-skill-id shengqian_weibao_hupiao`，同时提交视觉清单路径、哈希和 `visual_status=approved`。
7. 没有 `content_id`、Skill 版本或已通过的视觉清单，稿件不算完成生产闭环。
8. 内部方法、source_id、证据坐标和边界说明只进入生产记忆或内部工作区，不进入交付文件。

## 不可逾越规则

- 不得编造原句、经历、数据和外部结果。
- 不得把完整餐画面写成减重、营养或医学结论。
- 不得把价格个案写成长期承诺，不得虚构热量、省时分钟数、熟度或食品安全数据。
- 不得把商品广告或平台项目计入自然方法证据；商业内容必须使用自己的插入与收束证据。
- 手部身份锚点不得被单次任务静默替换；只有用户明确批准新的锚点后才能升级。
- 禁止在母版之后用纯文字独立重生封面、结果、特写或配菜页；禁止跳过三页校准门后直接并行生成整批。
- 用户认可生成图不得作为 `package_master`、食物真实感、相机真实感或完整餐母版生成输入；固定手部身份是唯一 `identity_only` 例外。
- 食材纤维、颗粒、切面和塑料感等验收词不得整段复制进生图提示词；提示词只描述菜品、账号相机语法、构图和必要不变量。
- 账号黑灰哑光桌面是完整餐视觉基线；胡桃木锚点降级为回滚历史，不能作为默认生图参考。
- 任何系统性升级或本账号单独升级都不得静默删除既有能力；能力文件、兼容清单或回归包校验失败时保持 v2.0 可回滚基线，不得登记新版本完成。
