# 李宗恒 batch_12 v2重学成果审核包

## 审核结论

- 批次门禁：`pass`
- 学习方法版本：`cluster_ready_noncallable_v2_3`
- 用户审核：`pending`（机器门禁通过不等于用户确认）
- 视频条数：10
- 逐条五视角通过：10/10
- ASR引用质量筛查：10/10
- 批次错误：0
- 旧版卡片：只作为来源证据，不自动继承完成状态。
- 正式入库：锁定。

## 核心成果：统一十二段学习卡

- [《如此查寝》 @大伟老三 #李宗恒 #每日精选爆款](cards/7490030238697540918.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《愚人节快乐》 #李宗恒](cards/7488197351031475475.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《当00后成为了老板》 #李宗恒#零跑汽车 #零跑C16](cards/7486789767821036863.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《“病例式”简历》 #李宗恒 #她们的精选 #每日精选爆款](cards/7484836888973528361.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《准时下班！》 #李宗恒](cards/7484218738481401100.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《00后拒绝请假羞耻症》 #李宗恒](cards/7483454376640548107.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《在公司又没在公司》 #李宗恒](cards/7483103390625516839.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《普通话培训》 #李宗恒](cards/7482309665527844115.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《谁说天下没有免费的午餐》 #李宗恒](cards/7481613117500165439.md) - 契约 `unified_three_layer_v2`，验证 `pass`
- [《你们要的续集来了》 #李宗恒](cards/7479382209451871542.md) - 契约 `unified_three_layer_v2`，验证 `pass`

## 逐条五视角学习

### 1. 《如此查寝》 @大伟老三 #李宗恒 #每日精选爆款

- source_id：`7490030238697540918`
- 原分类：合拍/同框剧情 / 同学/校园 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：被查寝的学生用更繁琐的寝室规定夺取检查审批权。
- 证据点：先登记再安检；寝室长拒绝周日签字
- 关联候选：`b12-pos-rule-reversal`

#### topics

- 判断：`supports_candidate`
- 结论：反向查寝将安检测温和审批全部施加给学生会干部。
- 证据点：不明液体需当场证明；最后还要寝室长批准
- 关联候选：`b12-top-reverse-dorm-inspection`

#### structures

- 判断：`supports_candidate`
- 结论：手续从登记递进到最终签字，每轮都延后真正查寝。
- 证据点：检查门槛逐轮提高；寝室长身份最后揭晓
- 关联候选：`b12-str-bureaucracy-reversal`

#### expression

- 判断：`supports_candidate`
- 结论：如此查寝延续反常系列命名，艾特只说明共演关系。
- 证据点：标题保留权力反转；大伟老三为共演者
- 关联候选：`b12-exp-coactor-series-label`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：共演者不能被当成新账号，方言ASR错词也不能直接引用。
- 证据点：素材位于李宗恒目录；查寝被转写为茶姐
- 关联候选：`b12-counter-coactor-not-account`、`b12-counter-asr-quality`

### 2. 《愚人节快乐》 #李宗恒

- source_id：`7488197351031475475`
- 原分类：合拍/同框剧情 / 同学/校园 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：愚人节让每个人都能随时撤回真实立场，最后造成信任失效。
- 证据点：表白和录音连续反转；真消息也被当成骗局
- 关联候选：`b12-pos-rule-reversal`

#### topics

- 判断：`supports_candidate`
- 结论：多个独立恶作剧连续透支同学信任，真话在结尾无法生效。
- 证据点：鞋带拉链骗局失败；最后真出事无人相信
- 关联候选：`b12-top-april-fools-trust`

#### structures

- 判断：`supports_candidate`
- 结论：每个骗局都以被识破或再反转收尾，累积成信用崩塌。
- 证据点：骗局单元反复迭加；真消息承担总结后果
- 关联候选：`b12-str-prank-trust-collapse`

#### expression

- 判断：`supports_candidate`
- 结论：愚人节快乐作为中性节日文案，由视频提供信任代价。
- 证据点：标题不提具体骗局；结尾反向解释快乐
- 关联候选：`b12-exp-event-title`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：愚人节骗局是剧情编排，转写中的余仁节不能作正式引语。
- 证据点：恶作剧只服务喜剧；节日名存在ASR错词
- 关联候选：`b12-counter-asr-quality`

### 3. 《当00后成为了老板》 #李宗恒#零跑汽车 #零跑C16

- source_id：`7486789767821036863`
- 原分类：剧情段子 / 职场/商务 / 广告强绑定/广告主导

#### positioning

- 判断：`boundary_evidence`
- 结论：二代老板的组织错位只是外壳，零跑C16已成为明确解决方案。
- 证据点：员工反向开除老板；车辆卖点集中解决通勤办公
- 关联候选：`b12-pos-organizational-outsider`、`b12-pos-ad-product-solution`

#### topics

- 判断：`boundary_evidence`
- 结论：00后老板和被开除只作广告剧情轴，车辆功能不进自然选题。
- 证据点：小老板不懂管理；零跑C16标签和功能完整
- 关联候选：`b12-top-genz-boss-car-ad`

#### structures

- 判断：`boundary_evidence`
- 结论：管理剧情中段转入车辆口播，卖点结束后再回到老板被开除。
- 证据点：产品段有独立功能清单；结尾由父亲确认开除
- 关联候选：`b12-str-ad-bridge-to-firing`

#### expression

- 判断：`boundary_evidence`
- 结论：人设标题和零跑C16标签并列，内容入口与商业归属都很清楚。
- 证据点：标题写00后老板；话题写零跑汽车和C16
- 关联候选：`b12-exp-explicit-car-tags`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：剧情完整不能抵消品牌型号和多个卖点形成的广告主导。
- 证据点：六座后排屏智驾连续出现；小桌板被用作办公卖点
- 关联候选：`b12-counter-ad-heavy`、`b12-counter-asr-quality`

### 4. 《“病例式”简历》 #李宗恒 #她们的精选 #每日精选爆款

- source_id：`7484836888973528361`
- 原分类：剧情段子 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：求职者用近音和重新解释把病症包装为理想员工能力。
- 证据点：海鲜过敏被解释为加班；工作成瘾被解释为必须工作
- 关联候选：`b12-pos-language-role-gap`

#### topics

- 判断：`supports_candidate`
- 结论：简历写成病历后，每种症状都恰好匹配公司想要的奉献。
- 证据点：恐惧和洁癖对应加班扫除；失忆症最后暴露现编
- 关联候选：`b12-top-medical-resume`

#### structures

- 判断：`supports_candidate`
- 结论：病症清单逐项建立字面兑现，最后用失忆症拆穿整份简历。
- 证据点：多个症状共享解释格式；结尾忘记刚才说过的话
- 关联候选：`b12-str-list-literal-payoff`

#### expression

- 判断：`supports_candidate`
- 结论：病例式三字直接把简历与病历的近音机关放进标题。
- 证据点：引号提醒词义异常；正文逐项执行病症逻辑
- 关联候选：`b12-exp-pun-title`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：虚构病症不是医疗建议，且快速台词中多处ASR错词需审核。
- 证据点：病名仅服务职场谐音；简历被转写成命令
- 关联候选：`b12-counter-asr-quality`

### 5. 《准时下班！》 #李宗恒

- source_id：`7484218738481401100`
- 原分类：剧情段子 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：员工用到点就下班的事实逻辑拒绝道德施压。
- 证据点：六点到点离开；九点到岗与到家对称
- 关联候选：`b12-pos-workplace-boundary`

#### topics

- 判断：`supports_candidate`
- 结论：准时下班和不加班被还原为正常工时边界。
- 证据点：老板反复追问；员工只回答下班了
- 关联候选：`b12-top-workplace-boundary-trio`

#### structures

- 判断：`supports_candidate`
- 结论：多轮字面回答后用上班和到家时间收口。
- 证据点：问答格式反复；时间对称作结论
- 关联候选：`b12-str-list-literal-payoff`

#### expression

- 判断：`supports_candidate`
- 结论：准时下班加感叹号把正常行为写成稀缺事件。
- 证据点：标题只有四字立场；感叹号强化态度
- 关联候选：`b12-exp-literal-workplace-title`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：剧情对话不能代替真实劳动协商或法律建议。
- 证据点：台词为喜剧编排；未提供具体劳动合同
- 关联候选：`b12-counter-fiction-not-advice`、`b12-counter-title-not-enough`

### 6. 《00后拒绝请假羞耻症》 #李宗恒

- source_id：`7483454376640548107`
- 原分类：剧情段子 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：00后员工用对等交换拒绝请假羞耻和提前干活。
- 证据点：提前做工作就要提前发工资；私事不向老板展开
- 关联候选：`b12-pos-workplace-boundary`

#### topics

- 判断：`supports_candidate`
- 结论：请假羞耻、结婚返岗和七天无理由共同构成边界试验。
- 证据点：同事结婚当天返岗；员工申请连休七天
- 关联候选：`b12-top-workplace-boundary-trio`

#### structures

- 判断：`supports_candidate`
- 结论：老板每次施压都被员工用同一句式字面返回。
- 证据点：工资与未来工作对等；七天无理由最后收口
- 关联候选：`b12-str-list-literal-payoff`

#### expression

- 判断：`supports_candidate`
- 结论：00后和拒绝请假羞耻症先定义人设立场。
- 证据点：代际标签位于标题；拒绝二字明确态度
- 关联候选：`b12-exp-literal-workplace-title`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：七天无理由是消费话术包袱，不是真实请假规则。
- 证据点：对话为喜剧设计；没有公司制度证据
- 关联候选：`b12-counter-fiction-not-advice`

### 7. 《在公司又没在公司》 #李宗恒

- source_id：`7483103390625516839`
- 原分类：剧情段子 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：面试者作为组织外部人反而被所有员工使唤。
- 证据点：未入职就被派活；经理连姓名也记错
- 关联候选：`b12-pos-organizational-outsider`

#### topics

- 判断：`supports_candidate`
- 结论：倒水填表拍照连续让面试者在公司又不属于公司。
- 证据点：不在公司群里；最后才被记起来面试
- 关联候选：`b12-top-interviewee-used-as-staff`

#### structures

- 判断：`supports_candidate`
- 结论：打杂任务逐轮加深身份误认，澄清后仍保留错名。
- 证据点：任务从倒水升级到拍照；小李被反复叫小王
- 关联候选：`b12-str-identity-misuse-escalation`

#### expression

- 判断：`supports_candidate`
- 结论：在公司又没在公司同时表达场所与组织身份。
- 证据点：人在办公场所；身份仍是面试者
- 关联候选：`b12-exp-paradox-title`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：ASR将姓名和职位多处转写错误，不可当人物事实。
- 证据点：姓名在对话中反复错位；引用必须做ASR筛查
- 关联候选：`b12-counter-asr-quality`

### 8. 《普通话培训》 #李宗恒

- source_id：`7482309665527844115`
- 原分类：剧情段子 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：普通话培训者以专业身份纠正员工，却不断暴露更重方言。
- 证据点：纠正员工东北话；培训者自己方言密集
- 关联候选：`b12-pos-language-role-gap`

#### topics

- 判断：`supports_candidate`
- 结论：口音最重的人主持培训，每次纠正都让自己更像反例。
- 证据点：客人投诉触发培训；结尾明白仍带口音
- 关联候选：`b12-top-dialect-trainer`

#### structures

- 判断：`supports_candidate`
- 结论：纠正轮次越多，培训者自曝的方言密度越高。
- 证据点：从厕所热水逐项纠正；后段连续输出东北话
- 关联候选：`b12-str-corrector-self-exposure`

#### expression

- 判断：`supports_candidate`
- 结论：普通话培训的中性标题隐去了培训者才是最大反例。
- 证据点：标题不写东北口音；反转全由台词表演完成
- 关联候选：`b12-exp-normal-label-hidden-reversal`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：方言密集区域的ASR不可直接当作普通话教程或稳定引语。
- 证据点：多句方言被错转；内容本质是喜剧反例
- 关联候选：`b12-counter-asr-quality`、`b12-counter-title-not-enough`

### 9. 《谁说天下没有免费的午餐》 #李宗恒

- source_id：`7481613117500165439`
- 原分类：剧情段子 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：员工利用面试承诺和过敏边界，把二十五分钟工作兑现为工资与饭。
- 证据点：按分钟计算工资；用过敏升级员工餐
- 关联候选：`b12-pos-workplace-boundary`

#### topics

- 判断：`supports_candidate`
- 结论：秒辞、分钟工资和免费午餐共同建立对承诺的极端兑现。
- 证据点：上班二十五分钟就辞职；吃完员工餐又留下
- 关联候选：`b12-top-workplace-boundary-trio`

#### structures

- 判断：`supports_candidate`
- 结论：利益从十元工资递进到牛肉柠檬茶，最后撤回辞职。
- 证据点：计算分钟工资；免费餐逐步升级
- 关联候选：`b12-str-benefit-escalation-return`

#### expression

- 判断：`supports_candidate`
- 结论：反问标题先给出免费午餐结果，正文再解释获取过程。
- 证据点：标题先推翻常识；剧情逐步兑现结果
- 关联候选：`b12-exp-result-first-question`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：秒辞套餐是剧情夸张，土豆等ASR错词不能直接引用。
- 证据点：不是真实劳动建议；土豆被转写为吐豆
- 关联候选：`b12-counter-fiction-not-advice`、`b12-counter-asr-quality`

### 10. 《你们要的续集来了》 #李宗恒

- source_id：`7479382209451871542`
- 原分类：合拍/同框剧情 / 职场/商务 / 正常内容

#### positioning

- 判断：`supports_candidate`
- 结论：新人汽车销售以专业身份接待顾客，却不懂车型、价格和提成。
- 证据点：连续翻看销售话术；将优惠与提成说反
- 关联候选：`b12-pos-language-role-gap`

#### topics

- 判断：`supports_candidate`
- 结论：能力不足的销售因同事全部零销量，仅卖一台就成为销冠。
- 证据点：新人多次说错产品信息；全店只有他卖出一台
- 关联候选：`b12-top-incompetent-car-sales`

#### structures

- 判断：`supports_candidate`
- 结论：销售失败从车型知识升级到数字计算，最后用相对销冠收尾。
- 证据点：错误逐轮增加；销冠来自集体更差
- 关联候选：`b12-str-incompetence-to-relative-champion`

#### expression

- 判断：`supports_candidate`
- 结论：你们要的续集不说场景，必须由片头和展厅画面恢复系列。
- 证据点：片头写00后成为销售续；三帧确认汽车门店
- 关联候选：`b12-exp-sequel-needs-visual-context`

#### counterexamples

- 判断：`boundary_evidence`
- 结论：汽车展厅和价格话术不自动等于广告，三帧未见品牌功能转化。
- 证据点：无清晰品牌型号；展车只服务销售剧情
- 关联候选：`b12-counter-car-scene-not-ad`、`b12-counter-asr-quality`、`b12-counter-title-not-enough`

## 五类候选池

### positioning

- **让被管理者用更繁琐规则反向审批管理者**（`b12-pos-rule-reversal`）
  - 摘要：查寝与愚人节都通过反复改变规则，让原本掌控局面的人失去判断权。
  - 证据：`7490030238697540918`、`7488197351031475475`
- **用00后字面逻辑拆解职场道德施压**（`b12-pos-workplace-boundary`）
  - 摘要：准时下班、正常请假和面试承诺都被重新还原为对等的交易边界。
  - 证据：`7484218738481401100`、`7483454376640548107`、`7481613117500165439`
- **让专业身份与语言能力持续错位**（`b12-pos-language-role-gap`）
  - 摘要：求职者、普通话培训者和汽车销售都用过度自信暴露自身专业偏差。
  - 证据：`7484836888973528361`、`7482309665527844115`、`7479382209451871542`
- **从组织边缘人视角观察公司身份混乱**（`b12-pos-organizational-outsider`）
  - 摘要：面试者被当员工和二代老板被员工开除，都反转了正式组织身份。
  - 证据：`7483103390625516839`、`7486789767821036863`
- **产品成为角色通勤与办公解决方案时判广告主导**（`b12-pos-ad-product-solution`）
  - 摘要：零跑C16的六座、后排屏、智驾和小桌板集中解决小老板通勤办公需求。
  - 证据：`7486789767821036863`

### topics

- **寝室用登记安检和审批反向阻止查寝**（`b12-top-reverse-dorm-inspection`）
  - 摘要：查寝者必须逐项通过寝室规定，最后才发现寝室长就是面前的学生。
  - 证据：`7490030238697540918`
- **愚人节多轮骗局透支信任后真话也失效**（`b12-top-april-fools-trust`）
  - 摘要：迟到、衣着、表白和录音连续反转，最后真出事仍被当成玩笑。
  - 证据：`7488197351031475475`
- **00后二代老板靠六座车通勤办公却被开除**（`b12-top-genz-boss-car-ad`）
  - 摘要：不成熟管理与零跑C16功能口播结合，员工最后以不养闲人开除老板。
  - 证据：`7486789767821036863`
- **求职者把简历写成恰好满足公司的病历**（`b12-top-medical-resume`）
  - 摘要：过敏、成瘾、恐惧和洁癖等症状被逐项翻译成加班与奉献。
  - 证据：`7484836888973528361`
- **准时下班、请假与秒辞职的对等边界**（`b12-top-workplace-boundary-trio`）
  - 摘要：员工用时间、工资和面试承诺反问老板，拒绝单向延长义务。
  - 证据：`7484218738481401100`、`7483454376640548107`、`7481613117500165439`
- **面试者因坐在公司而被所有人当成员工**（`b12-top-interviewee-used-as-staff`）
  - 摘要：倒水、填表和拍会议照逐步加深误认，经理最后连姓名也叫错。
  - 证据：`7483103390625516839`
- **东北口音最重的人主持普通话培训**（`b12-top-dialect-trainer`）
  - 摘要：培训者越要求员工别说东北话，自己的方言反而越密集。
  - 证据：`7482309665527844115`
- **不懂车价优惠和提成的新人成为零销量销冠**（`b12-top-incompetent-car-sales`）
  - 摘要：新人汽车销售持续翻话术并说反数字，最终因同事一台未卖而获奖。
  - 证据：`7479382209451871542`

### structures

- **登记安检测温审批逐步抬高查寝门槛**（`b12-str-bureaucracy-reversal`）
  - 摘要：每个手续都以寝室规定为由中断检查，最后由寝室长身份揭晓收束。
  - 证据：`7490030238697540918`
- **恶作剧单元连续反转直到真消息失去信用**（`b12-str-prank-trust-collapse`）
  - 摘要：每轮都可用愚人节撤回立场，重复后果在结尾转成无人相信真话。
  - 证据：`7488197351031475475`
- **老板荒诞管理途中插入汽车功能后回到开除反转**（`b12-str-ad-bridge-to-firing`）
  - 摘要：零跑C16口播用通勤办公连接人设，卖点结束后由员工和父亲完成开除。
  - 证据：`7486789767821036863`
- **病症或边界话术清单逐项字面兑现**（`b12-str-list-literal-payoff`）
  - 摘要：多轮同样句式先建立稳定节奏，最后用失忆、到家时间或七天无理由收口。
  - 证据：`7484836888973528361`、`7484218738481401100`、`7483454376640548107`
- **面试者被连续派活后才被记起真实身份**（`b12-str-identity-misuse-escalation`）
  - 摘要：倒水、表格和拍照任务逐步让外部人员像员工，姓名错误保留边缘感。
  - 证据：`7483103390625516839`
- **纠正者每讲一条规则就提供更强反例**（`b12-str-corrector-self-exposure`）
  - 摘要：员工的口音只是引子，培训者的方言密度随纠正轮次持续提高。
  - 证据：`7482309665527844115`
- **秒辞职从分钟工资升级到员工餐后撤回**（`b12-str-benefit-escalation-return`）
  - 摘要：先计算二十五分钟工资，再用过敏升级餐食，吃完后又宣布继续努力。
  - 证据：`7481613117500165439`
- **销售能力持续失败后用全员零销量制造相对销冠**（`b12-str-incompetence-to-relative-champion`）
  - 摘要：从车型介绍到优惠提成逐步暴露无知，最后用更差集体衬托唯一销量。
  - 证据：`7479382209451871542`

### expression

- **如此系列和共演艾特不改变账号归属**（`b12-exp-coactor-series-label`）
  - 摘要：‘如此查寝’延续反常服务命名，大伟老三只是共演者标注。
  - 证据：`7490030238697540918`
- **节日祝福标题用多轮骗局完成反向兑现**（`b12-exp-event-title`）
  - 摘要：愚人节快乐不说具体骗局，让每次撤回真话和最后信任失效来解释。
  - 证据：`7488197351031475475`
- **人设标题与零跑C16品牌型号标签并列**（`b12-exp-explicit-car-tags`）
  - 摘要：00后老板承担内容入口，零跑汽车与C16标签承担明确商业召回。
  - 证据：`7486789767821036863`
- **用简历与病历的近音直接命名整篇机关**（`b12-exp-pun-title`）
  - 摘要：‘病例式’加引号后既说明写作格式，也提醒观众病症会被重新解释。
  - 证据：`7484836888973528361`
- **短职场命题用感叹号或代际标签预告立场**（`b12-exp-literal-workplace-title`）
  - 摘要：准时下班将正常行为写成事件，00后请假则先给出不内耗的人设。
  - 证据：`7484218738481401100`、`7483454376640548107`
- **用在公司又没在公司表达地理与身份矛盾**（`b12-exp-paradox-title`）
  - 摘要：同一句中的两个公司分别指实体场所和组织成员身份。
  - 证据：`7483103390625516839`
- **用普通话培训的正常名称遮蔽培训者反例**（`b12-exp-normal-label-hidden-reversal`）
  - 摘要：标题不说东北口音和人物矛盾，让培训者越讲越露馅。
  - 证据：`7482309665527844115`
- **反问标题先宣布免费午餐结果再补获取过程**（`b12-exp-result-first-question`）
  - 摘要：谁说没有免费午餐先推翻常识，正文用秒辞和过敏升级证明。
  - 证据：`7481613117500165439`
- **续集文案依赖片头和画面恢复汽车销售语境**（`b12-exp-sequel-needs-visual-context`）
  - 摘要：发布文案只说续集来了，由片头00后销售和门店画面说明系列。
  - 证据：`7479382209451871542`

### counterexamples

- **品牌型号与多个功能卖点连续出现时必须隔离**（`b12-counter-ad-heavy`）
  - 摘要：零跑C16同时有品牌标签、六座、屏幕、智驾和小桌板，剧情完整也不能算自然内容。
  - 证据：`7486789767821036863`
- **汽车展厅和价格话术本身不足以证明广告**（`b12-counter-car-scene-not-ad`）
  - 摘要：三帧只确认新人销售剧情，没有清晰品牌型号、功能特写或购买召唤。
  - 证据：`7479382209451871542`
- **共演者标注不得被拆成新的学习账号**（`b12-counter-coactor-not-account`）
  - 摘要：大伟老三只是如此查寝的共演者，素材发布与方法归属仍是李宗恒。
  - 证据：`7490030238697540918`
- **职场字面反击和秒辞套利不是真实劳动建议**（`b12-counter-fiction-not-advice`）
  - 摘要：对话为喜剧节奏而编排，可学习结构和人设，不能替代劳动法或现实协商。
  - 证据：`7484218738481401100`、`7483454376640548107`、`7481613117500165439`
- **方言与快速对话的ASR错词不得作正式引语**（`b12-counter-asr-quality`）
  - 摘要：检寝、愚人节、土豆和销冠等多处被转写错误，理解可纠错但引用必须审核。
  - 证据：`7490030238697540918`、`7488197351031475475`、`7486789767821036863`、`7484836888973528361`、`7483103390625516839`、`7482309665527844115`、`7481613117500165439`、`7479382209451871542`
- **续集、培训和准时等短标题不能独立完成分类**（`b12-counter-title-not-enough`）
  - 摘要：必须结合对话、画面与角色关系，才能区分职场边界、方言反例和汽车销售。
  - 证据：`7484218738481401100`、`7482309665527844115`、`7479382209451871542`
