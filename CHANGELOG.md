## Version 2026.11.06.2 (tag `v2026.11.06.2`)

### What is new

- **DGIdb drug-gene interactions.** Which drugs act on a gene, ranked by how well each is supported, with the sources named. It has its own switch under Settings → Databases.
- **Consent for automatic tasks.** Automatic tasks cannot ask, so a database used by them needs your consent. In Settings → Databases each database now has "Allow in automatic tasks too". Before this version, a switched-on database that had not been granted was refused in automatic tasks without any sign of why; the refusal now says what to do.
- **PDB searches are exact.** A gene (human entries only) or a UniProt accession is matched exactly, and the total number of entries is shown. The earlier text search could return unrelated structures.
- **Faster repeated lookups.** Successful database answers are kept for 30 minutes, so asking again for the same gene or accession is instant. A failed lookup is tried again next time, and a switched-off database is never answered from the cache.
- **No back doors around a refusal.** When a database is refused, the agent is told not to reach the same service another way (for example with curl or a script). During testing the agent had done exactly that.

### How it was checked

- A live run with three sub-agents: all three started within the same second and ran side by side, finishing 42–45 seconds later. The main model made another call while they ran, so its reasoning overlapped with theirs; it waits only when it has nothing else to do.
- 741 backend unit tests pass, including the new grant behaviour, the precise PDB search, DGIdb parsing and the cache.
- DGIdb and the precise PDB search were checked against the live services.
- Not checked live: an automatic task using a granted database. That needs a grant set by you in Settings.

---

## 版本 2026.11.06.2（标签 `v2026.11.06.2`）

### 新增

- **DGIdb 药物-基因相互作用。** 查询哪些药物作用于某个基因，按证据强度排序，并注明来源。在 设置 → 数据库 中可单独开关。
- **自动任务的授权。** 自动任务无法提问，因此它用到的数据库需要你事先授权。现在 设置 → 数据库 中每个数据库都有“自动任务中也允许”的开关。在此版本之前，开着的但未授权的数据库在自动任务中会被拒绝，而且不说明原因；现在拒绝信息会说明怎么办。
- **PDB 查询更精确。** 按基因（只限人类条目）或 UniProt 登录号精确匹配，并显示总条目数。之前的文本搜索可能返回不相关的结构。
- **重复查询更快。** 成功的数据库结果保留 30 分钟，再次查询同一个基因或登录号会立即返回。失败的查询下次会重新尝试，已关闭的数据库不会从缓存中回答。
- **不能绕过拒绝。** 数据库被拒绝时，智能体被告知不得用其他方式（例如 curl 或脚本）访问同一服务。测试中智能体确实曾这样绕过。

### 验证情况

- 三个子智能体的实际运行：三个几乎同时启动，并行运行，约 42–45 秒后全部完成。主智能体在它们运行期间又完成了一次模型调用，即它的推理与子智能体重叠；只有在没有其他工作时才等待。
- 后端单元测试 741 项全部通过，包括新的授权行为、精确的 PDB 查询、DGIdb 解析和缓存。
- DGIdb 与精确 PDB 查询已对照在线服务检查。
- 未实际检验：已授权数据库在自动任务中的使用。这需要你在设置中授权。

## Version 2026.11.06.1 (tag `v2026.11.06.1`)

### What is new

- **Five more database tools**, checked against their live services: Ensembl (human gene records), PDB (experimental structures), AlphaFold DB (predicted structures with confidence), PubChem (compounds by name), and OpenAlex (scholarly works beyond PubMed). Each has its own switch under Settings → Databases. OpenAlex uses an optional personal key (`BIOMNI_OPENALEX_KEY`); without one it shares a small free daily budget.
- **Save a finished task as a skill.** Under an answer, "Save as a skill" drafts a reusable run-book from that task: its method, with the specific gene or file replaced by placeholders. You read and edit it, then save it to your skills. Nothing is saved without your review.

### Fixes

- The scanner of the community hub no longer flags `model.eval()`, a normal method call.

### How it was checked

- 730 backend unit tests pass, including the new database tools (parsing, not-found and network errors, registry consistency), the skill drafting, and the scanner rules.
- Live checks against the real services: all five new database tools returned data; the picture tool was tested with a free vision model and read a chart's title and axis label correctly; the planning model returned a plan and a clarifying question; resume was tested with a real backend restart in the middle of a task, and "continue" finished the task with the correct accessions; the skill-update check ran against GitHub.

---

## 版本 2026.11.06.1（标签 `v2026.11.06.1`）

### 新增

- **五个新的数据库工具**，均已对照其在线服务测试：Ensembl（人类基因记录）、PDB（实验结构）、AlphaFold DB（预测结构及置信度）、PubChem（按名称查化合物）、OpenAlex（PubMed 之外的学术文献）。每个都可以在 设置 → 数据库 中单独开关。OpenAlex 可选填个人密钥（环境变量 `BIOMNI_OPENALEX_KEY`）；不填时与网络上其他人共享一个很小的免费每日额度。
- **把完成的任务存为技能。** 在答案下方点击“存为技能”，会把该任务的方法起草成可复用的操作说明，具体的基因或文件替换为占位符。你阅读并修改后保存到你的技能中。不经你审阅，不会保存任何东西。

### 修复

- 社区中心的扫描不再把 `model.eval()`（普通的方法调用）判为风险。

### 验证情况

- 后端单元测试 730 项全部通过，包括新增的数据库工具（解析、未找到和网络错误、注册表一致性）、技能起草和扫描规则。
- 对真实服务的实际测试：五个新数据库工具均返回了数据；图片工具用一个免费视觉模型测试，正确读出了图表的标题和坐标轴标签；规划模型返回了计划和澄清问题；续接在真实重启后端的任务中途进行测试，发送“继续”后任务以正确的登录号完成；技能更新检查已对照 GitHub 运行。

---

## English

### What is new

- **Sub-agents run side by side.** Independent parts of a question start as sub-agents at once and run in the background while the main agent keeps working. Results come back as messages when they finish; `wait_subagents` lets the agent wait for a named result. The number that run at once is set in Settings → Helper models (1–6, default 3). Sub-agents use the medium thinking strength unless you set another. A sub-agent cannot start sub-agents of its own.
- **Helper models.** Settings → Helper models sets a model and thinking strength for planning, sub-agents and the reviewer, separately from the main model.
- **Pictures.** A new `look_at_image` tool sends a picture to the picture model (set in Settings) and returns its text answer. It is offered only when a picture model is set.
- **Continue after a stop or a restart.** The work of a task is saved as it goes. If the task is cut short, send "continue" in the same conversation and the agent picks it up. A tool call that never got its result is dropped, because the model could not resume it.
- **Project work log.** Each finished task records what it did (the question and the start of the answer), without an extra model call. Later tasks in the same project receive the entries that match their question, also in a new conversation. The log can be viewed and cleared in Settings → Memory. Turning memory off for a project stops both recording and use.
- **Memory settings on their own page.** Settings → Memory holds the suggestions switch (suggested notes after a task, approved by you), the amount of remembered text a task may carry, the work log, and the notes. Databases (connectors and standing permissions) are on Settings → Databases.
- **Community hub.** The library is now a hub, in the way Hermes' skills hub works. An index of about 950 skills from three GitHub sources is searched without calling GitHub each time. Each skill has a trust level (trusted or community). Before a skill is added it is scanned: a dangerous verdict is never installed, a caution verdict needs your confirmation, and every attempt is written to an audit log. Tools (MCP servers), databases and software are curated and shown for reference.

### Fixes

- Deleting a skill also clears its GitHub source record, so later update checks no longer point at a skill that is gone.
- A skill whose front matter names it with `name` (as community skills do) imports under that name.

### How it was checked

- 713 backend unit tests pass. They cover sub-agents running side by side, the main loop going on while a sub-agent runs, `wait_subagents`, resuming, the work log, the picture tool, the vision call, the scanner and install policy, and the index.
- A live run asked the agent for three independent UniProt lookups; the three sub-agents started within a second of each other and finished in about eight seconds.
- Not yet checked against a live model: the picture tool and the planning model.

### Upgrading

Settings that were stored before this version keep working. Keys and the ChatGPT login are not part of the release and must be entered again on a new computer.

---

## 中文

### 新增

- **子智能体并行推进。** 问题中相互独立的部分会立即作为子智能体启动，在后台运行，主智能体继续自己的部分。结果完成后以消息形式返回；`wait_subagents` 可让智能体等待指定的结果。同时运行的数量在 设置 → 辅助模型 中设置（1–6，默认 3）。子智能体默认使用中等思考强度，可在设置中改为其他档位。子智能体不能再启动子智能体。
- **辅助模型。** 设置 → 辅助模型 可以为规划、子智能体和审查分别设置模型和思考强度，与主模型互不影响。
- **图片。** 新增 `look_at_image` 工具：把图片交给图片模型（在设置中选择），只返回它的文字结果。只有设置了图片模型时才会提供这个工具。
- **中断后继续。** 任务的工作过程会边做边保存。任务被打断后，在同一对话里发送“继续”即可接着做。没有等到结果的工具调用会被丢弃，因为模型无法续接它。
- **项目工作记录。** 每个完成的任务都会记录它做过什么（问题和答案开头），不额外调用模型。同一项目的后续任务（即使在新对话里）会取到与其问题相关的记录。工作记录可在 设置 → 记忆 中查看和清空。关闭某项目的记忆，会同时停止记录和使用。
- **记忆设置独立成页。** 设置 → 记忆 包含：任务结束后建议记住事项的开关（建议需你批准）、每个任务最多带入的记忆文字量、工作记录和记住的事项。数据库（连接器和长期授权）移至 设置 → 数据库。
- **社区中心。** 原来的“社区库”改为社区中心，按 Hermes 技能中心的方式工作：约 950 个技能的索引（来自三个 GitHub 来源），搜索时不必每次访问 GitHub。每个技能都有来源可信度（可信来源或社区来源）。添加前会扫描：判定为危险的一律不安装；判定为需注意的需要你确认；每次尝试都写入审计日志。工具（MCP 服务器）、数据库和软件为精选的参考条目。

### 修复

- 删除技能时同时清除它的 GitHub 来源记录，之后的更新检查不再指向已不存在的技能。
- 使用 `name` 字段标题的技能（社区技能的常见写法）现在能正常导入。

### 验证情况

- 后端单元测试 713 项全部通过。覆盖子智能体并行、主循环在子智能体运行时继续、`wait_subagents`、续接、工作记录、图片工具、视觉调用、扫描与安装策略、索引。
- 实际运行中，让智能体同时做三个相互独立的 UniProt 查询：三个子智能体几乎同时启动，约 8 秒全部完成。
- 尚未用真实模型验证的：图片工具和规划模型。

### 升级

升级前保存的设置仍然有效。密钥和 ChatGPT 登录信息不包含在发布版本中，在新电脑上需要重新填写。
