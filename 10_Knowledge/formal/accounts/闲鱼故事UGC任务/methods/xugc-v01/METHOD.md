# 平台原生证据链

- 方法 ID：`xugc-v01`
- 状态：`formal_verified`
- 调用状态：`callable=true`
- 适用范围：闲鱼故事 UGC 任务级视觉生产

## 机制

用闲鱼商品/服务页、聊天或反馈截图与实物/结果照片共同完成可核验叙事。

## 触发

输入确有可公开的平台截图和对应实物、服务过程或结果照片。

## 固定项

- 每张图承担明确证据角色
- 截图只使用真实提供素材
- 敏感信息先脱敏

## 不触发与边界

缺少真实截图时不得生成仿造聊天、订单或商品页。

截图必须来自真实提供或已核验素材；不得生成仿造聊天、订单、评价或商品页。推荐图序不等于已核验发布轮播顺序。

## 证据

跨日期来源：`feishu_xianyu_20260713_s04`、`feishu_xianyu_20260713_s05`、`feishu_xianyu_20260713_s11`、`feishu_xianyu_20260714_s06`、`feishu_xianyu_20260714_s15`、`feishu_xianyu_20260715_s02`、`feishu_xianyu_20260715_s15`、`feishu_xianyu_20260716_s04`、`feishu_xianyu_20260716_s06`、`feishu_xianyu_20260717_s04`、`feishu_xianyu_20260717_s14`。

整体视觉复核和前向测试见 `../../evidence/VISUAL_REVIEW_SUMMARY.json` 与 `../../evidence/VISUAL_FORWARD_TEST_SUMMARY.json`。
