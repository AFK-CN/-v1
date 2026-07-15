# 李宗恒全量专业学习交付（候选）

> 430/430 条视频完成单卡与五视角学习；阶段 0-6 已完成。所有方法保持 `callable=false`、`formal_write=false`。

## 全量结果

- 43/43 批次、430/430 条学习卡。
- 1,330 条五视角观察，1,330/1,330 唯一归簇。
- 10 个机制簇：4 个候选方法，6 个边界/证据/降级簇。
- V1 方法证据：16/16 条均为正常内容且允许进入核心方向；商业和平台样本已排除。
- 压力测试：32/32 通过，包含词汇诱饵、边界、跨场景、兄弟干扰、消融、组合和商业污染。

## 候选方法

- [整套系统迁移](methods/lz-m1-system-transfer/METHOD.md)：把源系统的角色、流程、术语和结算规则整体迁入目标场景，并让迁移后的规则持续决定人物行动与最终后果。
- [评价权与控制权反转](methods/lz-m2-control-right-reversal/METHOD.md)：把提问权、定义权、审批权或服务控制权从原权力方转移给被评价者，并让新权力关系持续改变流程。
- [字面重释与双语境链](methods/lz-m3-semantic-reinterpretation/METHOD.md)：为同一句话建立可解释的第二语境，角色按替代解释行动，并让行动后果继续强化语义错位。
- [固定规则多场景递进](methods/lz-m4-fixed-rule-escalation/METHOD.md)：先固定口令、执念或验收规则，再用至少三轮场景重复验证，并在每轮增加关系、信息或后果强度。

## 方法编排

`G2证据门 -> G1内容轴分流 -> 正常内容走M1/M2/M3+可选M4 -> 商业内容先分析正常剧情再选择B1-B5植入桥 -> 表达包装 -> G1/G2复核`

## 广告植入学习

- 商品广告：140 条；平台项目：18 条。
- 已生成 140 张广告植入学习卡，逐条记录正常剧情、引入桥、产品角色和广告后收束。
- 五类植入桥：{'ad-b1-same-engine': 26, 'ad-b5-payload-takeover': 37, 'ad-b4-world-feature': 3, 'ad-b3-role-need-prop': 59, 'ad-b2-reveal-payoff': 15}。
- SRT源证据审计：广告 140/140，平台项目 18/18。
- 视觉声明复核坐标：88 条；人工目视抽验见 `MANUAL_VISUAL_COORDINATE_AUDIT.md`。
- [广告植入方法总览](ad_integration/AD_INTEGRATION_METHODS.md)
- [广告植入全量索引](ad_integration/AD_INTEGRATION_INDEX.jsonl)
- [广告源证据审计](ad_integration/AD_SOURCE_AUDIT_INDEX.jsonl)

## 平台项目与表现数据

- [平台项目方法总览](ad_integration/PLATFORM_PROJECT_METHODS.md)
- [18条平台项目卡](ad_integration/platform_cards/)
- [方法与表现数据交叉分析](ad_integration/PERFORMANCE_METHOD_ANALYSIS.md)
- 430/430 条深学内容已匹配互动指标；只作描述性关联，不解释为方法因果。

## 边界与降级

- `lz-g1-commercial-contamination`：商业内容不参与账号自然方法频次证明，但必须路由到广告植入学习分支，拆解正常剧情、引入桥、产品角色和收束。（`route_to_ad_integration_learning`）
- `lz-g2-evidence-account-boundary`：证据质量与账号归属是前置门禁，不是内容生成方法。（`retain_as_evidence_gate`）
- `lz-r1-generic-contrast`：正常/自己或前后对照是通用容器，尚未通过账号排他性验证。（`retain_as_support_pattern`）
- `lz-r2-generic-reveal-gap`：揭示、信息差和末尾反转属于行业通用收束方式，不能单独触发。（`retain_as_support_pattern`）
- `lz-r3-packaging-support`：标题、发布文案和话题属于表达支持层，不能绕过内容证据独立成为方法。（`retain_as_expression_support`）
- `lz-r4-case-specific-observation`：剩余观察尚未收敛为跨场景机制，保留单例和反例证据。（`wait_for_more_evidence`）

## 仍然不能宣称

- 不能因已接入互动指标就宣称某方法必然带来爆款；当前分析未控制发布时间、投流、品牌预算和平台曝光。
- 不能用商业样本增加账号自然方法频次。
- 不能把合拍演员拆成独立目标账号。
- 正式账号中心和生产调用仍需独立审核。
