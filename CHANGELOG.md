# Version notes · 版本说明

**Version 2026.11.06** (tag `v2026.11.06`) — follows the release "Rename project to Biomni-Desk".

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
