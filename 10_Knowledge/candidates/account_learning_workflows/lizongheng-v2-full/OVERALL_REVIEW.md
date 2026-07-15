# 李宗恒七阶段整体复核

## 完成状态

| 阶段 | 结果 | 核心产物 |
|---|---|---|
| 0 整体理解 | 完成并刷新至430/430 | `ACCOUNT_OVERVIEW.md/json` |
| 1 五视角提取 | 完成 | 1,330条候选观察 |
| 2 三重验证 | 用户确认并完成 | 10簇、4方法、6降级簇 |
| 3 RIA++构造 | 完成 | 4组 `METHOD.md` + `method.json` |
| 4 方法链接 | 完成 | `METHOD_INDEX.json` + `GLOSSARY.md` |
| 5 压力测试 | 完成 | 32/32 通过 |
| 6 候选交付 | 完成 | `LEARNING_DIGEST.md` + `promotion_manifest.json` |

## 广告内容学习

- 140 条商品广告已逐条拆成“正常剧情发动机、广告引入桥、产品剧情角色、广告后收束”。
- 18 条平台项目单列，不与商品广告混合。
- 广告 SRT 对齐 140/140；平台项目源证据审计 18/18。
- 88 条视觉声明已保存复核坐标，并完成代表性源视频目视抽验。
- 广告可以证明承接和植入方式，但自然方法V1权重始终为0。
- 完整成果见 `ad_integration/AD_INTEGRATION_METHODS.md`、`ad_integration/PLATFORM_PROJECT_METHODS.md` 和 `ad_integration/PERFORMANCE_METHOD_ANALYSIS.md`。

## 压力测试不是关键词自证

- 每个方法 8 个用例，共 32 个。
- 用例覆盖正例、词汇诱饵、边界、跨场景迁移、兄弟方法干扰、机制消融、组合增益和商业污染。
- 触发判断读取结构化机制事实；预期答案不写入 evaluator 输入。
- 商业内容即使结构匹配，只返回 `boundary_only`。

## 终验纠正

- 首次阶段 3 终验发现 M1 混入 1 条广告证据、M2 混入 1 条平台活动证据。
- 两条污染证据已替换为正常内容，并重建阶段 2-6 全部产物。
- 当前 V1 证据为 16/16 条正常核心内容；生成器和回归测试均新增商业排除硬门。

## 最终边界

- 七阶段候选学习完成，不等于正式知识入库。
- 四个方法仍为 `verified_candidate`、`callable=false`。
- 现行 active Skill 未因本工作流自动修改；Skill v2.2 仍走独立 proposal 确认门。
