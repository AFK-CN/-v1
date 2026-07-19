# 视觉黄金包调用规则

黄金包入口：`../assets/visual/golden-package-v2/manifest.json`。

用户认可五页成套回归入口：`../assets/visual/regression-packages/accepted-tomato-tofu-v1/manifest.json`。五页必须作为一个有序包读取母图、页序和父关系，不能只抽其中一两张冒充已经保留整包连续性。

它不是风格拼贴，也不是新的账号方法。v2 将账号真实照片与历史生成图彻底分工：账号原图是食物、相机、构图和厨房过程的唯一真实感来源；用户认可生成图只在生成后承担连续性、标注和版式回归。生成工具只读取本次页面角色所需的少量条目，不加载全部 NAS 或全部正式卡。

## 双层职责

### 账号原图层 `account_source`

- 用于校准完整餐构图、黑灰桌面、普通餐具、手机直闪、食材真实形态、厨房锅具和过程状态。
- 食物母版只选择 2–3 张 role 为 `annotated_cover` 或 `clean_meal` 且 `use_for` 含 `master_reference` 的账号完整餐原图。
- 食材结果近景和教程图不得进入完整餐食物母版。教程页至少选择一张同页面角色的账号原图；含虾、整鱼、肉片/肉块、鸡块、菌菇等高风险食材时，再选择一张同食材类别的 `ingredient_real` 结果图。
- 只继承可见真实感和页面机制，不复制原菜名组合、原文、价格、减脂或营养主张。

### 用户认可层 `user_accepted`

- 用户认可层包含历史生成图，因此默认 `validation_only`：用于生成后检查同一顿餐、页间构图、标注和编辑连续性，不作为任何食物母版、食材或相机真实感的生成输入。
- `accepted-tomato-tofu-clean-meal` 不再使用 `package_master`；不得以其校准新菜的食物纹理、桌面、光线或相机效果。
- 唯一例外是 `accepted-tomato-tofu-tutorial` 的 `identity_only` 手部身份；实际生产优先引用独立 `default-hand-identity-anchor.png`，并明确忽略锚点中的食物、桌面与文字。
- 用户认可生成图不得拥有 `package_master`、`phone_realism`、`camera_realism`、`food_morphology`、`ingredient_real` 或 `texture_naturalness` 用途。
- 五页回归包中的 `continuity_mother_asset_id` 只表示历史包内连续性比较根节点，不获得真实感、黄金正例、食物母版或生成参考资格。

### 用户餐具材质 `user_material_reference`

- 当前可选锚点为 `optional-minimal-black-ivory-tableware-anchor.png`，只在食物母版通过后用于餐具局部编辑。
- 它不是黄金真实感资产，不进入食物母版；只继承极简圆形、象牙白/哑光黑和光滑哑光表面。
- 参考中的白桌、杯子、方盘、带柄烤盘、空餐具陈列、光线和机位不得迁移。

## 最小召回

每个新包生成前，内部计划必须声明：

1. 食物母版使用 2–3 张账号原图 `master_reference`；不得混入用户认可生成图、食材近景或材质锚点。
2. 每张教程页至少一张账号原图教程参考。
3. 每类高风险食材至少一张账号原图 `ingredient_real` 参考；完整餐阶段只用于生成后验收，不作为母版输入。
4. 用户认可生成图只列入 `validation_reference_asset_ids`，不列入页面 `reference_asset_ids`。
5. 出现手时使用固定手部身份锚点；餐具编辑时使用可选餐具锚点，两者均单独声明角色。

引用使用 manifest 中的 `id`，禁止把 `/Volumes/...` 等 NAS 绝对路径写入生产包。NAS 只负责按 source_id 补充或更新黄金包；运行时优先用 Skill 内已复制并校验哈希的资产。

## 不允许的用法

- 只写“真实、自然、手机拍摄”而不附带黄金参考。
- 用一张审美图同时冒充食材形态、厨房步骤、餐具连续性和手部身份。
- 把用户认可生成图、胡桃木锚点或餐具参考用作食物母版、相机真实感或光线参考。
- 把牛肉、米饭、青菜等食材近景用于完整餐母版，迫使全画面继承近景微纹理。
- 为了靠近账号而复制来源的整套餐、文字、价格、标签或效果结论。
- 读取全部轻量包、全部正式卡或扫描 NAS 后再凭平均印象生成。
- 黄金资产哈希不一致时继续生产。

## 反例包隔离

`../assets/visual/negative-regression-v1/manifest.json` 保存用户明确否定的生产图片，只用于验收和回归测试。其 `source_kind` 固定为 `user_rejected_output`，`reference_policy` 固定为 `validation_only`。

- 反例不是账号原图，不证明账号风格、结构或方法。
- 反例不得进入提示词参考、黄金正例召回或生成器图像输入。
- 只能读取 manifest 中的失败标签和拒绝规则，或在视觉验收时对照检查同类缺陷。
- 正反例 ID 空间必须隔离；任何生产清单引用反例资产都由校验器直接拒绝。

## 更新规则

新增黄金资产必须有明确 `source_id` 或 `content_id`、角色、用途、引用策略和 SHA-256。账号原图从正式卡已指向的 NAS source_id 精确抽取；用户认可生成图必须标记 `validation_only` 或 `identity_only`。manifest 的 `source_lineage` 同时记录基础离线轻量源、专用抽样与参考角色防火墙；更新后先运行 `scripts/validate_visual_golden.py`，再升级黄金包版本。
