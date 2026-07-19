# 省钱也要喂饱自己（沪漂版）轻量数据源

这是为 NAS 断开时的查看、复查与证据回溯准备的自包含离线样本。

- 内容数：10
- 方向数：7
- 总体积：16.2 MB
- 每条内容包含 `学习卡.md`、`bundle_manifest.json` 与 `完整产出物/`。
- `完整产出物/` 保留源条目的视频/图片、逐字稿、抽帧、OCR/视觉分析、元数据、状态和 manifest；仅排除 `.DS_Store` 等系统垃圾。
- 原始 NAS 资料只读，本目录是本地副本，不替代原始资料。

## 快速复查

| 方向 | source_id | 类型 | 体积 | 离线入口 |
| --- | --- | --- | ---: | --- |
| 一周合集 | `6a1ee0840000000035025a38` | image_text | 1.3 MB | `directions/一周合集/xhs_6a1ee0840000000035025a38/学习卡.md` |
| 一周合集 | `69c652a1000000002200cc7a` | image_text | 1.4 MB | `directions/一周合集/xhs_69c652a1000000002200cc7a/学习卡.md` |
| 商业植入 | `6932b804000000001e00514d` | image_text | 1.2 MB | `directions/商业植入/xhs_6932b804000000001e00514d/学习卡.md` |
| 商业植入 | `692bc6d2000000001e006493` | image_text | 2.0 MB | `directions/商业植入/xhs_692bc6d2000000001e006493/学习卡.md` |
| 备餐知识卡 | `6954faae000000001e002da4` | image_text | 1.8 MB | `directions/备餐知识卡/xhs_6954faae000000001e002da4/学习卡.md` |
| 平台项目 | `6a30fc7c000000002201a33a` | image_text | 2.6 MB | `directions/平台项目/xhs_6a30fc7c000000002201a33a/学习卡.md` |
| 成本透明一人食 | `6909cc3b00000000070217c4` | image_text | 1.5 MB | `directions/成本透明一人食/xhs_6909cc3b00000000070217c4/学习卡.md` |
| 成本透明一人食 | `68c29b30000000001d00d062` | image_text | 935.5 KB | `directions/成本透明一人食/xhs_68c29b30000000001d00d062/学习卡.md` |
| 自然一人食 | `68e4e6d200000000070158b5` | image_text | 1.2 MB | `directions/自然一人食/xhs_68e4e6d200000000070158b5/学习卡.md` |
| 设备效率餐 | `68d7b7e00000000012021a05` | image_text | 2.3 MB | `directions/设备效率餐/xhs_68d7b7e00000000012021a05/学习卡.md` |

## 更新方式

NAS 连接时，在知识库根目录运行：

```bash
.venv/bin/python -m tools.account_offline_source --root . --account "省钱也要喂饱自己（沪漂版）" --apply
```

如果目录已存在，使用 `--force` 明确覆盖旧的离线包。
