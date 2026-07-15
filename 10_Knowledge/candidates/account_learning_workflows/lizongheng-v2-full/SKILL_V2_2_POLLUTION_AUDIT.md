# 账号专业学习 Skill v2.2 污染审计

审计日期：2026-07-14

## 结论

通过。账号专业学习 v2.2 的 active Skill、通用配置、通用提取规范、流水线代码、系统校验器和生成后的知识库 Skill 包中，没有李宗恒账号专属内容。

## 扫描范围

- `00_System/shareable/skills/active/账号专业学习Skill_v2.md`
- `00_System/shareable/config/account_learning_pipeline.json`
- `00_System/shareable/rules/账号专业学习提取与验证规范.md`
- `tools/account_learning_pipeline.py`
- `tools/kb/validator.py`
- `00_System/shareable/skill_packages/知识库/`
- `00_System/shareable/skill_packages/knowledge-base/`

## 专属词扫描

以下词在上述通用执行面中命中数均为 0：

- 账号：李宗恒、`lizongheng`、`63700340656`
- 合拍演员：于洋、刘大悦、刘大悦er、大伟老三
- 具体段子：妈宝、爸宝、大喘气
- 具体品牌：伊利、Ulike、宝骏、海蓝之谜、LA MER

## 通用规则判定

“正常内容、商品广告、平台项目三轨”“合拍归属”“广告前剧情、引入桥、产品角色、广告后收束”“SRT 时间码”“表现数据不能代替因果验证”等内容保留在 v2.2 中，因为它们是跨账号质量门，不依赖李宗恒的人物、题材、品牌或方法结论。

`00_System/shareable/skills/history/proposal_账号学习真实验收与方法编排_v2_2_已生效.md` 会记录李宗恒作为升级证据，这是历史审批记录，不是 active Skill、通用规则或执行包，不参与账号学习调用。

## 边界

李宗恒专属内容只进入：

- `10_Knowledge/candidates/account_learning_workflows/lizongheng-v2-full/`
- `10_Knowledge/formal/accounts/知识成长自媒体方法论/账号中心/李宗恒/`
- 账号专用入库器 `tools/lizongheng_formal_ingest.py`

