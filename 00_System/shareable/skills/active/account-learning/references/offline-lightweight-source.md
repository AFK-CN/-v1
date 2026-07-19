# 轻量数据源后置交付

本流程是账号学习七阶段完成、用户审核通过、正式账号中心写入和用户层注册验证通过后的后置交付。它不是第八个学习阶段，不改变阶段 6 的候选态。

本目录承担“方向均衡离线复查”。视觉分支另在阶段 6 按 `visual-reference-learning.md` 形成“生产角色 + 视觉风险”参考候选。两者是并列轻量层：前者证明全方向可回查，后者证明生产前有少量可用原始参考；不得用前者的数量代替后者的覆盖。

## 触发门

只有同时满足以下条件才可写入：

1. 账号学习七阶段验证通过。
2. 用户已明确批准账号 Skill 正式生效。
3. 正式账号目录、Skill 五件套、中文视图、manifest 和用户层注册表已验证。

候选学习、批次复查或阶段 6 交付不能触发正式轻量数据源写入。

## 选择规则

- 以单个账号 Skill 为单位。
- 覆盖所有正式方向，每方向先选 1 条。
- 为达到总量要求可均匀增加，单方向最多 5 条。
- 单账号总量 10–20 条；方向数超过 10 时优先保证各方向 1 条。
- 只选正式学习卡已关联的可便携源目录。
- 优先证据完整、可离线回查且体积较小的条目。
- 任一正式方向无可用源时，状态必须为未完成并返回缺口。

## 单条包契约

```text
10_Knowledge/formal/accounts/{账号}/轻量数据源/
├── README.md
├── manifest.json
└── directions/{方向}/{platform}_{source_id}/
    ├── 学习卡.md
    ├── bundle_manifest.json
    └── 完整产出物/
```

`学习卡.md` 不能只用批次报告或候选 JSON 替代。`完整产出物/` 复制该 `source_id` 已有的整棵产出树：

- 视频：源视频、封面、音频、逐字稿、抽帧、视频信息、状态和 manifest。
- 图文：原图、封面、OCR、视觉分析、组图摘要、状态和 manifest。
- 只排除 `.DS_Store`、`._*` 等系统垃圾。

## 执行

首次组建：

```bash
.venv/bin/python -m tools.account_offline_source --root . --account "{账号}" --apply
```

旧包已存在时，默认运行同一命令只返回 `selection_diff`，不覆盖。用户审核差异并明确批准后才能执行：

```bash
.venv/bin/python -m tools.account_offline_source --root . --account "{账号}" --apply --force
```

离线验证：

```bash
.venv/bin/python -m tools.account_offline_source --root . --account "{账号}" --verify
```

## NAS 不可用

- 已有包：返回 `nas_unavailable_existing_bundle_preserved`，原包保持不变。
- 新账号：写入状态清单 `pending_nas_sync`，正式账号 Skill 不因此回滚。
- 不用候选资产、缓存报告或不完整卡片填充缺口。

## 验收

必须返回：

- `offline_source_status`
- `selected_count`
- `direction_count` 与 `direction_counts`
- `total_bytes` 或 `planned_bytes`
- `manifest`
- `selection_diff`
- `gaps` 与 `errors`

完成态必须证明：数量契约、全方向覆盖、完整媒体与处理产出、无 NAS 符号链接、文件字节数与 SHA-256 全部通过。

视觉账号还必须单独返回生产视觉参考包状态、角色覆盖、风险覆盖和 source_kind 隔离结果；该结果来自阶段 6 候选及正式复制验证，不由本工具按方向样本数量推断。
