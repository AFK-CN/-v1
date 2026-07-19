# 视觉母版、血缘与校准门

“每页是独立文件”不等于“每页独立重新生成”。本账号的流畅和真实来自账号原图先建立一张可信的食物母版，再按需局部换餐具，最后由同一张最终母版向后派生。

## 两阶段母版

1. 先只用 2–3 张账号真实完整餐、且黄金清单 `use_for` 含 `master_reference` 的图片生成 `food_master_asset_id`。
2. 食物母版先通过菜品数量、形态、熟制状态、光线、黑/深炭灰桌面和手机直闪感检查。账号过程图、食材特写、用户认可 AI 图、餐具材质图均不得参与这一步。
3. 若不换餐具，`master_asset_id` 与 `food_master_asset_id` 指向同一资产，材质门记为 `skipped`。
4. 若换餐具，只能在食物母版通过后进行一次 `tableware_local_edit`：引用用户真实餐具材质锚点，锁定桌面、食物、构图、机位和光线，只替换指定器皿。
5. 餐具局部编辑通过材质保真门后成为 `master_asset_id`。后续标注封面、教程、结果和特写一律直接引用这张最终母版。

用户认可的 AI 成图只做包内连续性回归；唯一例外是固定手部锚点只负责 `hand_identity`。它们不得进入食物母版或最终母版的生成参考。

历史五页认可结果必须按回归包 manifest 整体加载。无字完整餐是该历史包的 `continuity_mother_asset_id`，其它四页直接与它比较同餐、餐具、桌面、光线和标注体系；这是一条验收关系，不是新内容的生成血缘。新内容仍从账号原图生成自己的食物母版。

## 血缘约束

- 允许的生成模式：`single_generation`、`tableware_local_edit`、`annotation_overlay`、`crop`、`local_edit`、`tutorial_generation`。
- `text_only_generation` 永久禁止。
- 同一内容包声明连续性时禁止逐页整图重生。优先 `annotation_overlay`、`crop` 或 `local_edit`；若确实需要整图重生，必须新建发布包、重新建立食物母版并重走三页校准，不能宣称继承旧包连续性。
- 食物母版没有页面父节点；餐具局部编辑（若有）的唯一父节点是食物母版。
- 除食物母版和可选餐具编辑外，每一页必须直接以最终母版为唯一父资产；不得把结果页再作为下一页的父资产。
- 每页记录文件哈希、提示词哈希、参考资产 ID、父资产 ID、生成器和模型版本。
- `visual-lineage.json` 顶层必须分别记录 `food_master_asset_id` 与 `master_asset_id`，不得用同一个字段模糊两个验收阶段。

## 参考角色防火墙

- `master_reference`：只允许账号真实完整餐，负责桌面、构图、机位、手机直闪和整餐关系。
- `ingredient_real`：只在高风险结果或教程页使用，负责具体食材形态，不进入食物母版。
- `kitchen_process`：只在教程页使用，负责真实厨房动作、锅具和受热逻辑。
- `tableware_material_only`：只在食物母版通过后用于餐具局部替换，不迁移参考图桌面、杯子、方盘、手柄盘、灯光和构图。
- `hand_identity`：只在出现手的页面使用，不负责食物、场景或光线。
- `validation_only`：只做验收对照，不得出现在任何生成页面的 `reference_asset_ids`。

每张参考只能承担一个主角色。若同一原图需要承担不同角色，必须在黄金清单中拆成明确条目，不能把整包风格、食材纹理、餐具和手部身份混在同一次生成里。

## 生图提示词防火墙

`prompt_firewall` 必须全部通过：

- `qa_language_separated`：验收清单与生图提示词分开保存；
- `no_microtexture_enumeration`：不在提示词中枚举纤维、颗粒、叶脉、毛孔、油亮切面等微纹理；
- `single_role_per_reference`：每张参考只承担一个声明角色；
- `no_uniform_sharpness_request`：不要求全画面统一锐利、超清或商业食品广告质感。

生图提示词只写宏观对象、关系、动作、数量、机位、桌面和光线。纹理是否自然由成图后的 `visual_review` 判断，不反向诱导模型制造纹理。

## 三页校准门

批量展开之前只生产三页：

1. `master_asset_id`：最终无字完整餐母版；
2. 一张最有风险的 `tutorial`：优先含手、锅具或高风险食材；
3. 一张 `result`：优先整鱼、虾、肉、菌菇等形态敏感食材。

食物母版另由 `food_master_gate` 先行验收；若换餐具，再由 `material_gate` 验收。三页必须逐项检查并全部通过，`calibration_gate.status` 才能写为 `passed`。未通过时只修这些校准资产，不得并行生成其余页面。

## 高风险食材与纹理预算

默认高风险类别包括 `whole_fish`、`fish`、`shrimp`、`beef`、`pork`、`chicken`、`mushroom`、`shellfish`。套餐计划也可把结构复杂、容易变塑料或失真的食材显式标为 `high`。

每个高风险食材必须绑定至少一张 `account_source` 且 `use_for` 含 `ingredient_real` 的黄金参考；只有教程图但没有真实成品形态图，不算满足。同一完整餐最多安排两个 `texture_risk=high` 的菜或主食，防止整张图同时争抢微纹理细节。

## 逐页视觉复核

每页必须记录以下结果，值只能是 `passed` 或 `not_applicable`；其中适用项不得写 `not_applicable`：

- `identity_continuity`：同一顿餐、同一最终餐具和桌面；
- `ingredient_morphology`：数量、结构、切面和熟制形态自然；
- `texture_naturalness`：不呈塑料、蜡、橡胶、果冻或过度均匀高光；
- `lighting_continuity`：光向、色温、阴影和手机补光连续；
- `cookware_realism`：厨房页中的锅、灶、铲和容器是真实结构，不像碗或玩具；
- `hand_identity`：含手页与固定锚点同一身份且无多指/粘连；无手页可写 `not_applicable`。

若发生餐具局部编辑，`material_gate` 还必须明确记录：`table_locked`、`food_preservation`、`composition_preservation`、`lighting_preservation` 均通过。

只靠元数据不能替代视觉检查。校验器负责证明参考角色、血缘、哈希和复核记录没有缺失；复核人/模型对画面做实际判断并对结果负责。

## 完成门

每个发布包必须保存 `visual-lineage.json`，并通过：

```bash
python skill/scripts/validate_visual_package.py \
  --input 美食系列/{选题名}/visual-lineage.json \
  --package-root 美食系列/{选题名} \
  --golden-manifest skill/assets/visual/golden-package-v2/manifest.json
```

未通过时不得登记 `production-memory-record`，也不得标记发布包完成。
