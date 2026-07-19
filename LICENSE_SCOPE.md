# 许可证适用范围

SPDX-License-Identifier: Apache-2.0

根目录 `LICENSE` 中的 Apache License 2.0 **只适用于可迁移知识库系统包**。系统包的机器权威清单是：

`00_System/shareable/share_manifest.json`

该清单选中的系统代码、通用 Skill、配置契约、验证器、测试、系统文档和发布工程文件构成 Apache-2.0 中定义的 Work。

## 不在 Apache-2.0 授权范围内

以下内容不是上述 Work 的组成部分，不因本仓库包含 `LICENSE` 而获得复制、修改、分发或商用授权：

- `10_Knowledge/`：正式知识、候选知识、账号 Skill、账号资产和证据；
- `20_User/`：账号注册、生产记忆、反馈、私密内容和本机配置；
- `数据/`、`00_Inbox/`：原始资料和导入数据；
- `00_System/runtime/`、`90_Temp/`、`99_Archive/`：运行状态、临时结果和历史归档；
- 账号专属文字、图片、音频、视频、字幕、平台数据和第三方材料。

上述排除内容保留其原权利状态；除非其自身文件另有明确许可证或权利人另行书面授权，否则视为未授予许可。第三方材料继续适用其各自的权利和许可证。

## 分发要求

公开发布系统包时必须通过 `distribution-audit`，确保导出范围与 `share_manifest.json` 一致，并同时包含 `LICENSE`、`NOTICE` 和本文件。不得把排除目录复制进系统分发包。
