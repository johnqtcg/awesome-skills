# Anti-Patterns — Worked Examples

Load this when you suspect your draft is hitting one of the failure modes in `SKILL.md`. Each example below is a real-shape input followed by the BAD draft, the diagnosis, and the rewritten GOOD version.

Eight examples: four in English, four in Chinese, covering the five frames.

---

## Example 1 — Decision frame, English, "Tilt-less brief"

**Raw input** (what the user dumped):

> We've been evaluating two options for the analytics warehouse: BigQuery and Snowflake. BigQuery is cheaper at our current volume and integrates with our existing GCP setup. Snowflake has better support for the multi-cloud strategy the CTO mentioned last quarter and the SQL experience is more familiar to our analysts. We have a decision meeting Thursday.

**BAD draft**:

```
【BLUF】 We have evaluated BigQuery and Snowflake; both have merits.
【Frame】 Decision between two warehouse options.
【Crux】 Cost vs. portability.
【Key Nodes】
1. BigQuery: cheaper, GCP-integrated
2. Snowflake: portable, familiar SQL
3. Both options are credible
【Tilt】 We should discuss the priorities and decide together.
【Reasoning】
- Cost matters
- Portability also matters
- Team experience matters
```

**Diagnosis**: Failed Gate 4 — no commitment. Reasoning is a list of topics, not arguments. Crux is a topic ("X vs Y") not a tension.

**GOOD draft**:

```
【BLUF】 Pick BigQuery; accept the multi-cloud lock-in risk.
【Frame】 Decision — analytics warehouse for the next 24 months.
【Crux】 BigQuery is 40% cheaper at our current volume, but locks us deeper into GCP just as the CTO is pushing multi-cloud.
【Key Nodes】
1. Cost: BigQuery $180k/yr vs Snowflake $300k/yr at current volume
2. Multi-cloud: Snowflake works on AWS/Azure; BigQuery is GCP-only
3. Migration cost if we change later: ~6 weeks of analyst time
【Tilt】 Adopt BigQuery now; revisit at 3× current volume or if a multi-cloud requirement becomes binding.
【Reasoning】
- $120k/yr saved is real and recurring; multi-cloud is currently strategic intent, not a contract
- Migration cost is bounded (6 weeks) and we control when to pay it
- Risk I accept: if the multi-cloud mandate becomes hard within 18 months, we eat the migration
```

---

## Example 2 — Status frame, English, "Listing every workstream"

**Raw input**:

> Weekly update for the platform migration. Auth service is 80% migrated. Search service is 60%. Notification service is at 30% and the team is now blocked on the message queue procurement. The new dashboard is being designed. Documentation is being updated. We have a vendor demo on Wednesday for the queue.

**BAD draft**:

```
【BLUF】 Platform migration is progressing.
【Frame】 Status — platform migration weekly.
【Crux】 Multiple workstreams in flight.
【Key Nodes】
1. Auth: 80%
2. Search: 60%
3. Notification: 30%, blocked
4. Dashboard: in design
5. Docs: in progress
6. Vendor demo Wed
【Tilt】 We'll keep going.
【Reasoning】
- All workstreams are tracked
```

**Diagnosis**: Failed Gate 3 — Crux is "multiple workstreams in flight" which is a topic, not the binding constraint. The brief lists every workstream's % complete; only one of them changes the status verdict (Notification is blocked). Six Nodes — exceeded the limit and lost compression.

**GOOD draft**:

```
【BLUF】 Migration is on track except Notification, which needs a queue-vendor call by Wednesday.
【Frame】 Status — platform migration, week 6 of 12.
【Crux】 Notification is blocked on queue procurement; the dependency was external and we did not see it coming.
【Key Nodes】
1. Auth + Search are on schedule (80% / 60%); on track to finish by week 10
2. Notification is at 30% and frozen until queue vendor is picked
3. Wednesday vendor demo decides whether we can recover by week 12 or slip to week 14
【Tilt】 No action needed today; flag a re-baseline decision for Thursday after the demo.
【Reasoning】
- Two of three workstreams are healthy and self-running
- The one risk is binary: queue vendor selection by Wednesday or not
- Risk I accept: a 2-week slip is the worst case, not catastrophic
```

---

## Example 3 — Diagnosis frame, English, "Symptoms as causes"

**Raw input**:

> Our checkout API has been slow this week. p99 went from 200ms to 1.2s. Engineering has been investigating. They found that the database is slow. The team is looking into query optimization. We're getting customer complaints.

**BAD draft**:

```
【BLUF】 Checkout is slow because the database is slow.
【Frame】 Diagnosis — checkout latency.
【Crux】 Database performance has degraded.
【Key Nodes】
1. p99 went from 200ms to 1.2s
2. Database is slow
3. Engineering is investigating
4. Customers complaining
【Tilt】 Continue investigation.
【Reasoning】
- Need more data
- Team is on it
- We'll fix it
```

**Diagnosis**: Failed Gate 3 — "Database is slow" is a symptom, not a Crux. The Crux must name a *mechanism*. "Continue investigation" is a Tilt that means nothing — it's the default state.

**GOOD draft**:

```
【BLUF】 Roll back yesterday's query change; ship a hotfix index by EOD.
【Frame】 Diagnosis — checkout p99 regression since Tuesday.
【Crux】 The query change in PR #4421 dropped an index hint, forcing a full-table scan on every checkout — the DB looks "slow" but the actual mechanism is one bad plan choice.
【Key Nodes】
1. p99 regression started 14:00 Tue, matches PR #4421 deploy time
2. Query plan went from index scan (5ms) to seq scan (800ms)
3. Same query, same data — only the optimizer hint changed
【Tilt】 Revert PR #4421 within the hour; add a query-plan check to CI before reshipping.
【Reasoning】
- Mechanism is identified and reproducible — no investigation residual risk
- Rollback is small, isolated, and reversible
- Risk I accept: the feature in #4421 ships a week late
```

---

## Example 4 — Proposal frame, English, "Burying the ask"

**Raw input**:

> I've been thinking about our incident response process. We had three incidents last month that took longer to resolve than they should have because the on-call engineer didn't have access to certain dashboards. I think we need a dedicated SRE function. Or at least better tooling. The current model isn't sustainable.

**BAD draft**:

```
【BLUF】 Incident response has been suboptimal recently.
【Frame】 Proposal — improve incident response.
【Crux】 Current model has gaps.
【Key Nodes】
1. Three slow incidents last month
2. On-call missing dashboard access
3. Could use SRE or tooling
【Tilt】 We should explore options.
【Reasoning】
- Things could be better
- Several paths exist
```

**Diagnosis**: Buried the ask. No commitment. Reasoning has no substance. Crux is empty.

**GOOD draft**:

```
【BLUF】 Charter a 3-person SRE team in Q2; expected cost $750k/yr, MTTR cut from 4h to 1h.
【Frame】 Proposal — dedicated SRE function for FY26.
【Crux】 Three incidents in October took 4+ hours each because on-call lacked dashboards and runbooks; the cost of those incidents ($1.2M revenue impact) exceeds the cost of building the function.
【Key Nodes】
1. Cost: 3 hires (~$750k loaded), 1 quarter to stand up
2. Expected gain: MTTR cut from 4h to 1h based on benchmarks from comparable cos
3. Alternative considered: better tooling alone — rejected, doesn't solve the access/runbook gap
【Tilt】 Approve the headcount; I'll have JDs ready in two weeks.
【Reasoning】
- ROI is positive in 5 months at current incident rate
- The capability compounds — every future product launch gets it for free
- Risk I accept: if incident rate drops, we may over-staff by one role
```

---

## 示例 5 — Escalation frame，中文，"听起来像状态更新"

**原始输入**：

> 跟你同步一下 X 项目。我们和 Y 部门合作了 6 周，他们的接口一直没交付出来。我催了好几次。我们 11 月 1 日要上线，再不来就上不了线了。我也不知道怎么办，他们的老大不理我。

**BAD 草稿**：

```
【顶层结论】 X 项目和 Y 部门合作出了一些问题。
【框架】 状态 —— X 项目进展同步。
【核心矛盾】 Y 部门接口未交付。
【关键节点】
1. 合作 6 周
2. 接口未到
3. 11 月 1 日要上线
4. 我催过几次
【倾向方案】 继续推进，看看能不能解决。
【理由】
- 上线日期紧
- 需要协调
```

**诊断**：Frame 选错了。这不是状态更新，是升级请求 —— 用户需要的是领导出面，而不是只让领导知道。Tilt 没有 commit。Crux 没有指出"为什么需要这个人"。

**GOOD 草稿**：

```
【顶层结论】 需要你今天直接打电话给 Y 部门负责人 Z 总，否则 X 项目 11 月 1 日上线一定 miss。
【框架】 升级 —— X 项目跨部门依赖卡住，需要你的层级介入。
【核心矛盾】 我能联系到的 Y 部门最高级别是部门经理，他无权调整资源；只有 Z 总能决定把这个接口插到他们的优先级队列前面，我没法越级。
【关键节点】
1. 卡点：Y 部门接口完整开发需要 3 周，距离 11/1 还剩 14 天
2. 我已经做的：催了 4 次（周报、邮件、IM、当面），最近一次是上周四
3. 不动手的代价：上线 miss，承诺给 A 客户的功能延后，可能损失续约
【倾向方案】 今天给 Z 总打个电话，目标是让他在本周给这个接口分配两个工程师。
【理由】
- 这件事只有你能解 —— Z 总在你的层级，不在我的
- 等不起 —— 每过一天，技术风险都上升
- 我接受的代价：你需要花你 15 分钟时间和一点人情；不动手的代价是 miss 上线
```

---

## 示例 6 — Status frame，中文，"罗列一切，没有判断"

**原始输入**：

> 月度汇报。这个月我们完成了用户系统重构，搜索功能上线了，新加了 5 个埋点，修复了 23 个 bug，发布了 2 个 hotfix。团队新来了 2 个人。下个月计划做支付系统的优化、消息中心的迭代，还有一个研究性项目。整体在节奏上。

**BAD 草稿**：

```
【顶层结论】 团队这个月进展顺利。
【框架】 状态 —— 月度团队汇报。
【核心矛盾】 多项工作并行推进。
【关键节点】
1. 完成用户系统重构
2. 搜索上线
3. 5 个埋点
4. 23 个 bug 修复
5. 2 个 hotfix
6. 新增 2 人
7. 下月计划支付优化
8. 消息中心迭代
9. 研究性项目
【倾向方案】 继续按计划推进。
【理由】
- 工作量饱和
- 团队稳定
```

**诊断**：9 个节点 —— 失去了压缩的意义。Crux 又是"多项工作并行"这种废话。领导从这份汇报里得不到任何判断信号 —— 哪个是关键？哪个有风险？哪个值得他多问一句？

**GOOD 草稿**：

```
【顶层结论】 本月按计划完成；下月最大风险是支付系统优化的范围未定。
【框架】 状态 —— 团队月度回顾，下月展望。
【核心矛盾】 支付系统优化的需求方还没给出明确边界，我们要不要硬定个范围开始动？
【关键节点】
1. 本月完成项：用户系统重构（最大件，已稳定运行 2 周）+ 搜索上线
2. 团队产能：刚入职 2 人，未来一个月战斗力按 80% 计算
3. 下月最不确定项：支付系统优化 —— 业务侧需求还在变，技术影响面看起来比预期大
【倾向方案】 下周和业务侧定一个 must-have / nice-to-have 的范围决议；定不下来我们就只做 must-have。
【理由】
- 范围不定下来，3 个工程师投进去就是漂在水里
- 我们承担不起做了一半返工的成本
- 我接受的代价：业务侧可能不满意 nice-to-have 砍掉了 —— 我准备好这个对话
```

---

## 示例 7 — Decision frame，中文，"对仗工整但没有结论"

**原始输入**：

> 我们的 CI 系统现在跑得很慢，每次提交要等 40 分钟。我看了两个方案：方案 A 是自建一套 CI，预计开发 2 个月，每年省 50 万。方案 B 是换一家更快的云 CI 服务，每年多花 30 万，但下周就能切换。开发同学每天被堵着也很难受。

**BAD 草稿**：

```
【顶层结论】 CI 问题有两个方案。
【框架】 决策 —— CI 系统改造。
【核心矛盾】 自建 vs. 外购。
【关键节点】
1. 方案 A：自建，2 个月开发，省 50 万/年
2. 方案 B：换厂商，下周切换，多花 30 万/年
3. 现状：每次提交等 40 分钟
【倾向方案】 两个方案各有利弊，需要权衡。
【理由】
- A 长期省钱
- B 见效快
- 各有道理
```

**诊断**：经典的"对仗工整"格式 —— 把两个方案摆出来，然后不下结论。这不是汇报，是把决策皮球踢给领导。Gate 4 失败。

**GOOD 草稿**：

```
【顶层结论】 下周切到外部 CI 服务（方案 B）；自建方案先放一年再评估。
【框架】 决策 —— CI 慢导致每天 1.5 小时人均闲置，立刻处理。
【核心矛盾】 自建一年能省 20 万（50 万收益 - 30 万外购成本），但这 2 个月每天还要继续浪费 15 个工程师 × 1.5 小时。
【关键节点】
1. 现在的成本：15 人 × 1.5 小时/天 × 20 天 = 450 工时/月被浪费
2. 方案 B 的可逆性：合同一年制，明年可以再决定要不要自建
3. 自建的隐藏成本：2 个月开发后还要持续维护，不在 50 万收益的账里
【倾向方案】 下周切换到方案 B；今年内不启动自建，明年此时基于一年使用数据再评估。
【理由】
- 立刻消除每月 450 工时浪费 —— 这是真金白银
- 自建方案的"省钱"账里没算维护成本，结论不可靠
- 我接受的代价：未来一年多付 30 万；如果一年后还想自建，我们再花 2 个月
```

---

## 示例 8 — Proposal frame，中文，"理由太软"

**原始输入**：

> 我想申请招一个数据工程师。我们现在数据分析做得很零散，每个团队都自己拉数据。如果有专门的人负责，会规范很多。预算大概 80 万一年。

**BAD 草稿**：

```
【顶层结论】 建议招一个数据工程师。
【框架】 提案 —— 数据工程师 HC 申请。
【核心矛盾】 数据分析零散。
【关键节点】
1. 现状：每个团队自己拉数据
2. 成本：80 万/年
3. 效果：会规范很多
【倾向方案】 招一个数据工程师。
【理由】
- 数据更规范
- 提升效率
- 对齐行业最佳实践
```

**诊断**：理由是三句空话，没有任何具体损益。Crux 没有 tension，只是描述了现状。领导没法从这份提案里看到为什么要批。

**GOOD 草稿**：

```
【顶层结论】 批一个数据工程师 HC，预算 80 万/年，预计 6 个月内回本。
【框架】 提案 —— FY26 Q1 招聘一名专职数据工程师。
【核心矛盾】 5 个产品团队各自维护数据 ETL，重复劳动每月吃掉 ~15 个工程师人日，但任何单个团队都不愿意承担这个跨团队工作。
【关键节点】
1. 现状成本：15 工程师人日/月 × 12 个月 ≈ 180 工程师人日/年浪费
2. 招聘 ROI：80 万投入 ≈ 100 工程师人日（按 8000 元/人日），节省 180 人日 = 第一年净赚 80 人日
3. 隐藏收益：数据口径统一后，跨团队分析的扯皮和返工会消失（无法量化但每周发生）
【倾向方案】 批 HC；我下周开始走流程，6-8 周入职。
【理由】
- 投入产出比第一年就是正的，第二年起纯收益
- 这件事再拖一年，5 个团队继续重复劳动，机会成本越来越大
- 我接受的代价：未来 2-3 个月这位同学上手期间，分析需求响应可能略慢
```

---

## 模式总结：8 个例子里反复出现的 4 种失败

按出现频率排序：

### 1. 没有 commit 的 Tilt（示例 1、4、7）

最常见，也最致命。形式：「权衡一下」「需要讨论」「看情况」「两个方案各有利弊」。

**修复方法**：强迫自己写出一个动词开头的句子，比如「采用 X」「砍掉 Y」「批准 Z」「升级 W」。即使你不完全确信，写出来的位置是可以被反驳的，比模糊的「需要权衡」对决策有用 10 倍。

### 2. Crux 是问题空间，不是张力（示例 2、3、8）

形式：「X 和 Y 的取舍」「多项工作并行」「现状有问题」。

**修复方法**：Crux 里必须有一个隐含或显式的「but / 但是」。如果你的 Crux 句子里没有矛盾点，它就是个 topic，不是 Crux。

### 3. 节点罗列代替节点选择（示例 2、6）

形式：把所有信息都塞进节点，6 个、9 个、甚至更多。

**修复方法**：每加一个节点，问自己「这个节点删掉了，领导的决策会变吗？」如果不会，删掉。3-5 个就是上限。

### 4. 理由是空话，没有具体损益和接受的风险（示例 1 BAD、4 BAD、8 BAD）

形式：「更好」「更规范」「提升效率」「对齐最佳实践」。

**修复方法**：理由里必须出现具体的数字、时间或事件。最后一条理由必须是「我接受的代价是 X」。承认代价让汇报立刻可信。

---

**记住一条总原则**：领导要的是判断，不是材料。如果你的汇报读完以后他还得自己再思考一遍，那你的汇报失败了。