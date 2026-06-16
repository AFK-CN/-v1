<title>【教程】用Codex+Obsidian搭建卡帕西同款自生长知识库</title>

<callout emoji="🍌">
本文档为Xuan酱 2026.5.29  用Codex+Obsidian搭建卡帕西同款自生长知识库 教程文档
</callout>

# **全平台@Xuan酱，关注我，和我一起探索AI的更多玩法**

  
B站：https://space.bilibili.com/14848367?  
抖音： https://v.douyin.com/i5Jqby5f/  
小红书：https://www.xiaohongshu.com/user/profile/583ab2525e87e729b60e3564  
YouTube：https://www.youtube.com/@Xuan2333

视频号、公众号：直接搜索 Xuan酱，或扫码关注👇

![图片是一个二维码，中间嵌有一张女性的头像。。该图片位于文档底部，与上文提到的“视频号、公众号：直接搜索Xuan酱，或扫码关注”相呼应，是公众号关注的二维码。通过扫描此二维码，可快速关注Xuan酱的公众号，获取更多往期视频的教程文档等资料。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YTVkZWU2OTE3NzQ4NDRlOTBkZmYwMmZlM2ZlZmZkZmFfZGYxZDkxYzMwYzU0NmE3YjRmMzVhY2JkZGQ4ZjdhZDFfSUQ6NzY0NDA1NzA4ODgyNTkyMDQ3M18xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)

公众号获取所有资料链接更快哦

# 其他往期视频的教程文档都在👉 <cite doc-id="RxmAw9xGhiFx0CkptXFcGxFNn8c" file-type="wiki" title="Xuan酱的AI知识库" type="doc"></cite>



# 什么是“自生长”知识库？

<callout emoji="⭐">
AI大神卡帕西的“自生长”理论：https://x.com/karpathy/status/2039805659525644595
</callout>

![图片是自生长知识库原理图，位于文档中介绍AI大神卡帕西“自生长”理论核心逻辑部分。图中展示了知识库的循环迭代过程，包括不断吸收原始资料、AI定期消化](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NjhmOTllOWI0ZGM3NjE4YTliZjZlYzk1ZjMxNjMyN2FfNzcyZmE4OGUzZWZhZjc2ZjM5NDI1MjU2NWQ3OWNmNWVfSUQ6NzY0NDA2NjYyNjI5NTM4NTA2Ml8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)

核心逻辑：

1. 所有未经处理的原始资料，包括网页、论文、截图、视频、会议纪要等，都会统一进入原始文件夹 A；
2. AI 会定期对这些资料进行消化和复盘，筛选出真正有价值的内容，并将其提炼成更泛化的概念，归档到处理后的文件夹 B；
3. 用户可以根据不同任务和使用场景，让 AI 进一步把这些概念沉淀成可复用的方法模板，存放在 Skill 库或方法库文件夹 C 中；
4. 每一次实际产出的文章、报告、脚本或复盘结果，都会进入输出文件夹 D，并在下一轮 AI 定期复盘时重新回流进知识库，成为后续迭代和创作的新素材。



# 安装过程

下载Codex：https://openai.com/zh-Hans-CN/codex/

下载Obsidian：https://obsidian.md/



## 为什么是Codex+Obsidian？

Obsidian 本身是基于 Markdown 文件的本地笔记工具，所有内容都以开放、可读写的文本形式存储，这使得 AI 可以直接读取、分析并修改本地文件，减少大量手动整理成本。

与此同时，Obsidian 拥有成熟的插件生态，能够根据不同使用需求灵活扩展功能。当 Obsidian 接入 Codex 后，相当于为知识库引入了更强的 Agent 执行能力，再结合 Codex 的 Skill 和定时任务机制，就可以进一步实现知识整理、方法沉淀和自动化复盘等更丰富的玩法。



## 安装配置

```Markdown
- 安装 Obsidian
- 创建你的第一个知识库
- 安装 Claudian 插件
- 找到 Codex CLI 路径
- 在 Obsidian 中连接 Codex
- 在 Codex 中打开 Obsidian 项目文件夹
```

1. 安装Obsidian后，点击下方齿轮按钮，选择第三方插件，关闭安全模式，浏览插件市场，搜索Claudian，安装和启用
2. 然后点击选项卡，找到Codex，打开开关。这里需要填写 Codex CLI 的路径，用来连接桌面端 Codex。如果不知道路径，可以直接问 Codex。
3. 最后在Codex里面，打开项目工作按钮，选择你在 Obsidian 里创建的知识库文件夹。这样之后即使你在 Codex 里处理文件，因为本地仓库是打通的，回到 Obsidian 里也会同步更新。

<grid><column width-ratio="0.330937"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MjczMmE2OGIyZDMyNDI0NmM2NjkwNzlmNTQ5NTE1MGFfNDg2ODYyMzk4YWNmNDIyN2MxOWVmYWY3Nzc1MmQ5MzFfSUQ6NzY0NDA1ODM1MDY0ODg3MjEyMl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="HkWtbaixWoJ5Daxr3FackBDFnIh"/></figure><p>安装插件，联通Codex</p></column><column width-ratio="0.330937"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZmYxMTUwODgxMDY3ODk5OTc3ZWY3NzMxOTY1YTBlZmFfMmIwYjdmMzMwZDIyMmFjODkwODRiMmY3ZGMwZmQwMmRfSUQ6NzY0NDA1ODM1MTAzODcyOTQyOV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="R6UXb94HWo97xhx7Qr7cIn9lnSf"/></figure><p>找到Codex Cli Path</p></column><column width-ratio="0.338126"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OTM4ZTVhZDI5YzI3NmRjMThhZDZiOWVmNmQ2MGVmOTRfOThkM2JiYjhhZDRhZWU4NjkyZjQ2MDBjMWFlOGRhYzFfSUQ6NzY0NDA1ODM1MDg2NjgyODUwNF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3448.000000" token="L9eTbNbYioJvpyxhwvPcRsZ0nDd"/></figure><p>Codex直接联通</p></column></grid>



## 🌟一键架构图

<callout emoji="⭐">
把这两张图直接丢给codex，授予相关权限，就能一键配置
</callout>

<grid>
<column width-ratio="0.500000">
![图片是AI + Obsidian通用知识库结构蓝图，介绍只需填写“我的研究领域”，Codex就能搭建专属知识库。图中展示了Obsidian Vault文件夹结构，包括00_Inbox、01_Sources、02_Knowledge等六个文件夹，以及Codex自动检查规则，涵盖相关性、新鲜度、价值度等五个方面。底部有信息流转流程图，标注了S、A、B、C、D五个步骤。该图与上下文紧密相关，直观呈现了知识库的构建思路和内容分类。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YWVlZDE2MzVhNzc1YmUxYTg1Y2ZhMzU1ODkzZWRjZTdfYTEyMDY0YjY4YzdlZDY1ZjM3YjI4OTkzYzU0YzE1MGNfSUQ6NzY0NTY4Mjk5MzYyMDcwMDM2NF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)
</column>
<column width-ratio="0.500000">
![图片是“Obsidian 自动知识库插件与工具配置图”，展示了从信息来源到保存到Obsidian仓库的配置流程。信息来源包括行业新闻、GitHub、RSS等，操作工具涵盖GitHub、Claudian、Web Clipper等，保存到Obsidian仓库的路径为00_inbox、01_Sources等。图片还强调一键交给Codex配置，需提供信息来源、操作工具、保存到哪里等，Codex需确认API Key、版图权限、仓库路径等，还有一键提示词。该图与文档中一键架构图内容相关，是配置知识库的流程图。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MDExZjY3ZDI0Njk4OWNlNmI3YzIxYjg4MjVhMTg1ZWJfNjkwOGQ1NWU4MzRhMzc1ZjFhYzk0ZDYyZjg1OTJjOTNfSUQ6NzY0NTY4Mjk5NDQzMDEwMjc0OF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)
</column>
</grid>



# 信息搜集

## 定时抓取外部信息

1. 复制以下github项目地址发给codex，AI 会提示你需要提供哪些密钥，比如 DeepSeek、GitHub，或者某些信息源平台的 API Key

```Plain Text
项目名称：Horizon
项目地址：https://github.com/Thysrael/Horizon.git

参考提示词：我是一名AI博主，帮我配置这个AI信息收集系统：https://github.com/Thysrael/Horizon.git，需要我向你提供密钥或者其他内容的部分，你可以引导我。其余你能做的你可以提前做好
```

![图片展示的是一个GitHub项目地址及说明。地址为https://github.com/Thysrael/Horizon，下方文字说明该AI博主需提供密钥等信息，以配置AI信息收集系统，其余可提前做好。该图片位于文档“信息搜集”部分，是向AI博主发送的GitHub项目地址及需求说明，用于引导其配置AI信息收集系统，是搭建自生长知识库过程中获取外部信息的步骤之一。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ODRjMTQxMTg4MzhiMmMyN2IzNzg3M2UzYzU2ZTY3MTZfYTgzMmQ3ODZkNDMwNGU5NjhhNmE1NmYxNzViYzBjMjRfSUQ6NzY0NDA1OTYwMzk2Njk1NDQ2OF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)

![图片展示了在使用Codex+Obsidian搭建卡帕西同款自生长知识库时，需在tools/Horizon/.env文件中填写的密钥信息。至少填写DEEPSEEK_API_KEY（你的DeepSeek Key）和GITHUB_TOKEN（你的GitHub Token），其中GITHUB_TOKEN强烈建议再填，因匿名限流只有60次/小时，有Token是5000次/小时。可选APIFY_TOKEN用于启用Twitter/X抓取，HORIZON_WEBHOOK_URL为可选配置项。该图片与上下文紧密相关，是完成信息搜集步骤中配置密钥的关键指引。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZDc2OTEzN2ViYTg5MGQ2Zjc5ZTkwNTBiMTdmNWIwMjdfNGM1Yzc0Njc0ZjQzNDFjNGVhN2RkZmMzMWIwOTczZmVfSUQ6NzY0NDA1OTYwMTk4NTkzMjQ5OF8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM)



1. 直接问AI，这密钥要去哪注册，我们申请好密钥之后，把密钥直接发给AI，AI就能直接配置好

<grid>
<column width-ratio="0.526829">
![图片展示的是Codex在信息搜集时获取的DeepSeek和GitHub密钥配置地址。上方提示获取DeepSeek API Key的地址为https://platform.deepseek.com/api_keys，官方API文档为https://api-docs.deepseek.com/，拿到后填到tools/Horizon/.env中的DEEPSEEK_API_KEY=你的_deepseek_key。下方是GitHub Token获取提示，推荐用Fine - trained token。该图片与上下文紧密相关，是完成信息搜集步骤中获取密钥配置地址的示例。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MjkyOWZhMDA4MGJkYjJhZWQ3MTIxYmNmNTJlZDFhNDFfOGFiMzNjMWQ0ZmZjMTJjYTg5YjZiN2NhYmRkMDhhNWRfSUQ6NzY0NDA1OTYwMzg2NDgzMzIzNV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)
</column>
<column width-ratio="0.473171">
![图片展示的是Codex配置密钥的反馈信息。上方显示“deepseek的密钥”“github的密”等密钥信息被遮挡。下方显示已配置完成，具体包括DeepSeek Key、GitHub Token、Apify / X Token已写入本地.env文件，且已开启Twitter/X抓取。该图片与上文提到的“直接问AI，这密钥要去哪注册，我们申请好密钥之后，把密钥直接发给AI，AI就能直接配置好”相呼应，展示了配置密钥后的反馈结果。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZTZiOWZjZjJmMzA4NzM1NmZmOTc5NzM4N2EzZmRiNzVfZTEwNGFlMTYxNTg0MmQzYjVkYjIzYmEwODlkYWZjNjRfSUQ6NzY0NTYwNDM5OTUxOTQ4NDg3NV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)
</column>
</grid>



1. 告诉它你的身份和需求，即可完成收集。

```Plain Text
我是 AI 自媒体博主，请每天帮我搜集 AI 行业热点，并把日报推送到指定文件夹
```

![图片展示的是一个AI助手与用户之间的对话界面。AI助手介绍自己是中文区AI博主，会搜集信息源和账号，推送日报并建立文件夹存放日报。接着AI助手表示会先配置适合中文AI博主的中英信息源/账号，改好Horizon配置，再在vault里建立“每日AI日报”文件夹和统一模板，准备一键生成/归档/推送脚本，如未给webhook会先做成“填入URL即启用”。下方有多个Bash命令操作记录，如cd、grep、sed、python等，显示了部分代码执行过程。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZmY3YjYwOWY3NzU2OWIwNDZiMzM2MjYyYjBiYzM4NThfMzNlNzc5Zjg5MTlhNTg1Njc5N2JjNDZhZDMyZjFlYzBfSUQ6NzY0NDA1OTYwNTI2OTY2MjkxNl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)



## 随时随地剪藏信息

### Xiaohongshu importer 插件

- 在Obsidian插件市场下载
- 插件功能：可以上传小红书笔记链接，从而导入小红书平台的数据

<grid><column width-ratio="0.461226"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MjcxMjg5MmFlNmFlZWZmYWIwYTRiZWI3Yzc1Y2UzYTZfNmUxYjIyNGQ4YmM4Njk5NzdmODA4YjdjOWE0ZTg3ZDdfSUQ6NzY0NDA2MTMxODYxNzkyNjg2MF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="TBWZbYYrqoGPgBxMi9sclcJhnYg"/></figure></column><column width-ratio="0.538774"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZjM2YTMxNDNhOGJlOThiYmUxMTJkNjk1ZjdkYWI5ZTRfNTQ0NDE0MDA0YjZkNzI5MTQzMjBkNTRiNzg1MGRkNzRfSUQ6NzY0NDA2MTMxOTgzNDE5MzA3N18xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2012.000000" origin-width="3840.000000" token="SAiNbyiHoogUZSxkB6McyRysnih"/></figure></column></grid>



### Clipper 插件

- 在Obsidian插件市场下载
- 插件功能：在任意网页选中意向内容段落，点击插件，就能剪切收藏进Obsidian，甚至还可以收藏一些视频，提取字幕，直接一键存入Obsidian。

<grid><column width-ratio="0.500000"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MWFmMzNjM2Y5MTY3NDE4OGY3M2RkYjBkZWQyOTU0ZDlfMzM3NzFiNjVlY2NkZmRhMjg4MzE0YmQyOWE1NWVkNzZfSUQ6NzY0NDA2MTc3MzEwODE1MzU0Nl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3444.000000" token="YaTiblmAxoL9HoxbO6OcanYPn5e"/></figure></column><column width-ratio="0.500000"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NDk1M2U3MGY5OGJiNTdjMjM0ZTMyYjIwNzkxYzBhZTJfNjk4MjZhMmI2NmY5NTcwMTk1ZDZjZTdlN2FlYTljNjNfSUQ6NzY0NDA2MTc3MTc0NjkyMTY3Ml8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3472.000000" token="HSadbmqreoiNWYxC0bscpm5snmc"/></figure></column></grid>



## 已有信息迁移

### 飞书

> 飞书Cli官方安装指南：https://www.feishu.cn/feishu-cli

1. 让Codex直接安装飞书Cli
2. 让Codex帮忙完成授权过程，按照提示要求复制链接，点击授权即可
3. 完成配置后，就可以在Codex里直接下载对应的文件夹链接了

```Plain Text
帮我安装飞书 CLI：https://open.feishu.cn/document/no_class/mcp-archive/feishu-cli-installation-guide.md

帮我配置飞书应用授权

帮我下载这个文件夹中的飞书文档：xxxxxx【文档/文件夹链接】
```

<grid><column width-ratio="0.371868"><img name="安装和配置飞书Cli.png" alt="图片展示了Codex处理飞书CLI安装请求的回复。内容包括已安装完成的提示，飞书CLI版本号、可执行命令位置等信息，还提示已安装AI Agent Skills，共25个。最后检查结果为CLI可用，但未配置飞书应用授权，需运行“lark -cli config init --new”进行配置。下方有“帮我配置飞书应用授权”按钮。该图片与上文让Codex安装飞书CLI并完成授权的上下文对应，展示了具体操作结果。" caption="安装飞书Cli&#xA;" href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MmE1OTM0YjJmYjM4MDlhZTI5MTA2OTFjNjFlYWQwODFfNTQ2NjMwMjhiMTM3MjE2MDQwYmQyOWEzNTdlZWU4NjNfSUQ6NzY0NDA2MDM2NzkzMjkxODcyNl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="image/png" scale="1.000000" src="FWtub3XqjodgR6xOlX7cFapxnTc"/></column><column width-ratio="0.371868"><img name="image.png" alt="图片展示的是让Codex帮忙配置飞书应用授权的对话内容。Codex先说明已处理5分钟44秒，接着详细说明授权流程，包括在浏览器打开链接完成配置，配置文件写入本机后检查认证状态，以及登录授权等步骤。其中，关键信息是给出了一个链接（https://open.feishu.cn/page/cli/user...），并提示在浏览器打开该链接并按页面提示完成配置，页面完成后CLI会自动继续写入本机配置。该图片与上下文紧密相关，是完成飞书应用授权操作的指导说明。" caption="配置飞书授权&#xA;" href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NjUyYWMzNWQyODMxYjE1MjVlNmE1N2YxZjllNTEzZmJfOGE5NWIxYWM2MjUzNTA4NjYzNjlhOTdjMjBmODMwM2VfSUQ6NzY0NTE1NzQzNzI5NzMzMTM4MF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="image/png" scale="1.000000" src="O9kEbvwr5oMU48xL7CNcSfKknye"/></column><column width-ratio="0.256263"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OTM0YzhiZWQyNDg1OTY2ZDMzMmIwMGI3NTYwMTU2YTVfMWYwNTA1NTg3M2M2MmQ4YTFmMThmMjgzMjllNWYyMDlfSUQ6NzY0NDA2MDM2NjEwODM4MDM2OV8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3432.000000" token="Uuvzbqa0go0cIwx34cfcqzD9nGd"/></figure><img name="image.png" alt="图片展示的是飞书文档界面，显示文档名称为“EaO4fUVqYllk47dlOecZAfPnff”。界面中有“返回/前进”“显示”“群组”“共享”“编辑标签”“操作”“搜索”等操作按钮。下方表格列出4个文档，名称分别为“Xuan 酱工作室-脚本写作指南.docx”“Xuan 酱工作室——...作流程&amp;作息.docx”“Xuan 酱工作室——选题&amp;脚本规范.docx”“Xuan 酱工作室——封面设计规范.docx”，修改日期均为“今天 11:11”，大小分别为4KB、7KB、2.6MB、16.1MB，种类均为Microsoft Word文档。该图与文档中介绍飞书文档的内容相关。" caption="下载飞书文档&#xA;" href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YTkxY2Y5YjRkMGFlNGE1Y2M5ODg2MWRkMjMwM2Y2ZjZfZTI5NTE0MmI5YmFmOWExMmQ4MjMyZDliYjZmMzFjMDdfSUQ6NzY0NDA2MDM2Njc5NjA4MjM4MF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="image/png" scale="1.000000" src="XWBtbnZyeoWU4KxFQ9RciYU8nzh"/></column></grid>



### Importer插件

- 在Obsidian插件市场下载
- 插件功能：可以导入不同平台的数据

<grid><column width-ratio="0.444236"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YmU5NmM1MDU0ODY5ODU5M2U0YTUzMmNkMDJmOThmODZfODc4OTg4MTZkZjFjYzA5NTczNDM3MjI0YjVjZmI5MGRfSUQ6NzY0NDA2MDkzNTg2NjYwMDM5N18xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="CclZbLHxqofDk8xYpLpccI5Andb"/></figure><p>安装插件</p></column><column width-ratio="0.222431"><img name="image.png" alt="图片展示的是Codex插件中“Export”功能的下拉菜单。菜单中列出了多种导出格式，包括Apple Notes、Apple Journal（HTML导出）、Bear（.bear2bk）、CSV（.csv）、Evernote（.enex）、Google Keep（.zip/.json）、HTML（.html）、Microsoft OneNote、Notion（API）、Notion（.zip）、Roam Research（.json）、Textbundle（.textbundle, .textpack）和Tomboy/Gnote（.note）。其中，Apple Notes被蓝色背景和白色勾选符号突出显示。该图片与文档中介绍Codex插件功能的内容相关，展示了其导出功能的多种选择。" href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NDhhNzc3MjMwMTA1ZTdhYWMyNDQ0YWNmMTg1MTE4MWZfNmNhOGU1ZWE5NjRkNWIyYmIzNmJjODFlMzY1OGI2M2ZfSUQ6NzY0NDA2MDkzNzE3MTI3NDcxOV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="image/png" scale="1.000000" src="Y8iUbsQ8po2zjbx2xO9c9JfOn5c"/><p>适用平台</p></column><column width-ratio="0.333333"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZmY0OGJkMTA0NDI0NzEwNzdkNTFhNmVmZDY5MDViNzdfODg4Mzk2NDA2ZWE1NjRjMGI1YzAxNWYzZTA4YjMyMzJfSUQ6NzY0NDA2MDkzNzQ1NjI3NDY0NF8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="CcH1bZZR2o2EafxQu7CcmzfZn29"/></figure><p>导入数据（Notion为例）</p></column></grid>



### Docxer插件

- 在Obsidian插件市场下载
- 插件功能：可以将Word文件转换成Markdown格式

![图片展示了Docxer插件的相关信息。版本为2.3.0，作者是Developer-Mike。其功能是轻松导入Word文件，添加了预览模式，支持将.docx文件转换为.md文件。图片右上角有三个图标，分别是设置、删除和开关，开关处于开启状态。该图片与文档中介绍Docxer插件的内容相关，直观呈现了插件的版本、作者及功能等关键信息。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZDhjNzUwYjEzMmQxYWJmMDM5OTM5ZWJiZDJlODgzNDJfZTgyMTRhYmQ2NWFhY2JkNmM5Y2Y3OWQxZGI2OWY3ZWRfSUQ6NzY0NDA2MDczNjE2NTA4ODQ1NV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM)

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NWU4Yzc4ZGI2NzU2MzBhZGY5MzEwODE4ODdjZTY5NTBfNmM5OTdjMDg1NmNlYmY4ZDUzMzMxYjdjODJkZjA4ZThfSUQ6NzY0NDA2MDczNjE1NjUzNTc0OF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3728.000000" token="LPGMbNtOsob46nxgtoHc4xxZnJc"/></figure>





# 信息处理与迭代

## 搭建知识迭代系统

- 直接把卡帕西的思路丢给Codex，告诉它：“结合我的知识库，定制一个知识迭代系统”

```Plain Text
仔细研读这篇博主的帖子https://x.com/karpathy/status/2039805659525644595，结合他的核心思路，帮我制定一份知识库迭代机制方案。
```

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZDY2NmU4NTBiOTE3N2ZmNzRhODIzOWQyNjllMjkxYzZfNDFjNjRlMGNlODg4ZmY1MWYwMzc5NWM4ZjY3ZTc3ZjdfSUQ6NzY0NDA2MjIzOTUwMjM3MTc5Nl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="BYvAbK2Jioeu9yxyNVUcj2s8njd"/></figure>



## 定期自动任务

<callout emoji="⭐">
为进一步提升自动化程度，可以借助 Codex 的自动化能力，将这些重复性的知识处理流程拆解成一系列定时、定期执行的任务。
</callout>

### 定期蒸馏

1. 让AI写出这个蒸馏任务的提示词。你也可以让AI帮你写其他定时任务～

```Plain Text
请你基于知识库迭代机制，帮我延伸出一个prompt，这个prompt我要放在codex的自动化功能里，让它在每周五帮我自动执行。每次执行后的文件都会存在“每周蒸馏”文件夹中，方便我后续查看。
```

1. 在Codex的自动化功能里，粘贴好生成的提示词。
2. 定时每天下午五点，它就会自动干活了
3. 每次蒸馏完之后，它会自动生成一份总结文件，存回 Obsidian 对应的项目文件夹里

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OTE4ZDYxZDE2NzRlNmNmZGFkOGM3NmMwZjgxYmQyMWFfZjgwMmI4Yzc1NWNiMmUyZWU0MTYxODI1MGE5YTRkMTRfSUQ6NzY0NDA2Mjg5ODQ2NTQ3NTUxNl8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="U7Dhbv6qqovI6Dxy0bicazaZnzb"/></figure>



### 飞书会议复盘

1. 确认已经安装飞书Cli，并做好授权
2. 参考“定期蒸馏”的操作流程
3. 给Codex输入以下提示词。如果有其他需求，可以让AI帮忙改提示词。

```Plain Text
帮我复盘一下我这一周的飞书会议/群聊内有哪些要点和重点事项，然后整理成一个文档放进obsidian里
```

1. 可以定期在Codex里整理飞书会议纪要、重要消息，生成的文件再放进Obsidian里，相当于直接完成了一次周报

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NmMyYTNiYTE0YWU2ZmRjNDAyZTBlNWFlODJkYmFmNTJfMmI5MjkxODU5ZmQ2Y2NjZGM4Mjk2NjVjY2U2MzA3N2VfSUQ6NzY0NDA2MzQ1NDczODk0MzE3Ml8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="A1YYbsm2uoR7lnxmG0gccruFnOg"/></figure>



### HTML复盘看板

```Plain Text
将知识库中的XX笔记，输出为html格式，以便于复盘，输出的内容包括：生活、阅读、项目总结
```

![图片展示的是一个生活与项目可视化周报界面。上方显示日期为2024年10月28日，标题为“生活与项目可视化周报”。下方有四个数据板块，分别是47/56、155、672、5。中间部分有“生活节奏”板块，列出多项任务及完成情况。右侧有“财务概览”板块，显示收入、支出等数据。底部有“阅读记录”“进行中项目进展”“本周计划”“数据来源”等板块，呈现相关任务和数据。该图与文档中搭建知识迭代系统的内容相关，展示了周报的样式。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MjNjNTM3ZTkyMDNlZTFlYTQ5MzE2NThjYjdlNzgzMGVfZTg4Y2QzZDFlNzBkYTlkM2FlYWEwZDMzNTk3NzI1MDdfSUQ6NzY0NDA5MTYyNjk1NjU3MzY0OF8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM)



## 沉淀方法论与Skill

<callout emoji="⭐">
前面这些提示词、文档和操作流程，本质上都可以沉淀成 Skill。你可以让 AI 把高频使用的工作流、判断标准和方法论，整理成一套专属于自己的可复用能力模块。
之后再处理类似任务时，就不用反复描述需求，直接调用 Skill，就能让 AI 按照你的既定方法管理和运用知识库。
</callout>

### 可直接用的Skill包

<figure view-type="Card"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=MjFhMjA5ZjkwY2JhM2RlN2Y4NjVlZjg4ODUyZjVjMmFfZDhiZjBlMDdjZDdjNDRjYmU3NTRkMjdlNjk1ZjY1NWJfSUQ6NzY0NDA2NTAyMjU3ODU5MjcxMV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="application/zip" token="RtbkbzUW1oCvqHx1VoecSy8unmb"/></figure>

**使用方法：**

- 解压后，将Skill包拖动到Obsidian项目文件夹即可



### 选题价值判断Skill

```Plain Text
请你基于选题价值判断Skill，帮我全局分析现在资源库里各个来源搜集到的所有资料，针对“用AI做知识库”这个选题，进行完整的信息判断。并且整合成一个完整的判断报告
```

<grid><column width-ratio="0.500000"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=Mzk2YzE5YjY4ODU5YTQ3ODc2ZjQ0MDMzNjI4MDQ5MDZfMThjZWUyOGE1N2I4NDA5ZTJjMmM2N2M2YTJiMzExYTZfSUQ6NzY0NDA2MzgwMzcxMzUyMjYxOV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3448.000000" token="HQhxbndVjoPl5GxG3QbcXIYNnGf"/></figure></column><column width-ratio="0.500000"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZTM4ZjQzODNlYzAwNDA2ZDAzMWE5ZWFhYTcyMzYzZjZfNzY1MjY4MWMxNjMzMTcwYWRjMjQwNDQwZmRhZGQ2YjNfSUQ6NzY0NDA2MzgwMzkwNjY5MDAwOV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="BGoDbUjK8oD7ncxealucPXqMnXb"/></figure></column></grid>



### 文风蒸馏Skill

```Plain Text
请你基于xx文件夹中的文档，沉淀出一个脚本文风Skill
```

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZTUzMmIzOTBlN2UyNjNkMjBmZjlhNmJiOTBlMjkzOTVfYzkzOTEzNjllZjdmZjgwNzg5YWE4NDNkY2QzMGZkNDlfSUQ6NzY0NDA2NDM3NTM0MjgxMjEwOV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="PFJ1bQpgwoVbIZxfU38cIT5wnor"/></figure>



# 信息输出

## 做Skill灵活输出



```Plain Text
请你调用文风Skill，结合已经搜集到的相关资料，把这篇“用AI+Obsidian搭建知识库”的初稿写出来。
```

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=YTM2YjNjNjE2NzI1NWVjMjdiMmQ3NWRiODA3NGYyMWFfODdlMjhmYjQ0NWE0MWQ2OWI2OGEzZTFmZTVkZTI4YTdfSUQ6NzY0NDA2NTI0ODI2Mjc1MzQ3MV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="Kqy3b5BggoDAsRxPB3icMBi0nlh"/></figure>



## 做可视化输出

### 配图Skill

```Plain Text
我想做一个公众号配图Skill，可以根据正文自动判断哪里需要配图、生成图片提示词、整理素材；也可以根据剧本继续拆角色、拆分镜、做视觉参考等。比如我们写完公众号后，可以让Codex自动识别配图需求，生成图片提示词，并调用 Image 2 生成文章插图，图片生成后自动保存到本地素材目录，并以 Markdown 图片链接插入正文。

用配图Skill，给这篇公众号生成相符合的配图，用image2模型。
```

<grid><column width-ratio="0.393650"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=OWQyNTU4YzVjZWJmZGRkZmMyMDFkODc5ZDIyMzRhZmZfNjdlZjRmZWRhNGUzN2RmZGQ1N2M0ZDU1NmUxMDAwNzVfSUQ6NzY0NDA2NTU4NzczNTc1OTgxMF8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="2196.000000" token="G6o0bQa7Foy1kUxY9uOcED8Jnah"/></figure><p>生成配图Skill</p></column><column width-ratio="0.606350"><figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZGZkNDI4NjJhYTE2NDU5ZmU1Njk5ZDk4YjA5Mjk3MTNfMWUwMTdlMjg1M2M2MDA2ZGMwM2NhODRjMDMzMzE0NWVfSUQ6NzY0NDA2NTU4ODMzMTQ2NTY3Nl8xNzgxMzU4MDIyOjE3ODEzNjE2MjJfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="IASAbM45Ko6ysMxUD1vctxoYnid"/></figure><p>使用配图Skill</p></column></grid>

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ODRlNTNhYjZkMDY0YTBmYmY5YjViNjUzZThmM2Q1MThfYmI3NmM4ZjMxMDIxM2JmY2UzYWMyNDEyM2RiZjYxNzBfSUQ6NzY0NDA2NTU4NzYyNjk3MDMwMl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="CgTVblq6RonnnUxQw2wc7kDmnDg"/></figure>



### PPT制作

- 在Codex里调用Presentations插件，一句话直出PPT

```Plain Text
@Presentations 请你把《用 AI 做知识库：选题价值判断报告》这篇文档做成一份专业美观的ppt
```

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=ZmY1M2ZkOWMwZGYxYmI5MDY4NThkMDM3NGUwYzcwMGFfZDI0Yjc0MjY4NDZkMWYyY2E2ODYzY2UxNWRlZmMzNGNfSUQ6NzY0NDA2NjM3NDcyNTE3NjI1MV8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3440.000000" token="LRg1bW0BEofUSdxE5JjcwPm5nld"/></figure>



### 视频

- 在Codex里调用hyperframes插件，一句话直出视频

```Plain Text
调用hyperframes插件将xx文章制作成讲解视频，4k分辨率
```

<figure view-type="Preview"><source href="https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NjljM2I5MmE1MzE5OTQwYjZmN2E3MzU2ZThjYWNjMjNfNGQzZWE5YTIxOWExYmNlOWY0NTQ4NmU1ODIzMjRkNmJfSUQ6NzY0NDA5MTkwMDgwNjYxNDIyNl8xNzgxMzU4MDIxOjE3ODEzNjE2MjFfVjM" mime="video/mp4" origin-height="2160.000000" origin-width="3840.000000" token="XAasbZUb8oTjK9x5Y97c8h5knSh"/></figure>