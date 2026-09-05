# PRD：allowedTools 链式命令绕过与并发 git 锁竞态——工具白名单的真实安全边界

> 状态：Ready for review
> 涉及组件：`claude-maas-delegate` skill（`scripts/delegate`, `SKILL.md`, `references/SECURITY.md`）
> 前置：无（本 PRD 是对 `DELEGATE_ALLOWED_TOOLS` 机制的独立调研结论）
> 文档日期：2026-09-06
> 优先级：P2

## 0. 结论

Claude Code 的 `acceptEdits` 权限模式只自动批准 Write/Edit 类文件编辑，
**从不自动批准 Bash 命令**（包括 `git add`/`git commit`/测试执行），无论
命令本身是否危险。在 headless（`-p` print 模式）下没有人能回答这个批准
询问，所以每一次 Bash 调用都会静默失败，报错文本是
`This command requires approval`。这不是 bug，是设计上的安全边界。

进一步实测发现：`DELEGATE_ALLOWED_TOOLS` 里的 **Bash 白名单——不管是裸
`Bash`、前缀通配 `Bash(git add:*)`、还是精确全字符串
`Bash(bash tests/collapse/ok_gate.sh)`——一旦放行，就等于对那一整条
（可能被 `&&`/`;` 拼接过的）命令行放行，白名单只检查命令开头、不检查
后续拼接，不构成能防命令拼接注入的沙箱边界。**因此 Bash 白名单应被当作
"本次会话获得完整 shell 信任"来看待，真正的安全边界必须来自 routing-policy
（只委托低风险 task_type）和委托方对产出的事后核实，而不是这套工具白名单
机制本身。**

## 1. 背景：`DELEGATE_ALLOWED_TOOLS` 的传递路径

`scripts/delegate` 读取 `DELEGATE_ALLOWED_TOOLS` 环境变量（约第 460/494
行），原样传给底层 `claude` 的 `--allowedTools` 参数。`SKILL.md` 目前给出
两个预设：

- 探索档：`Read,Bash,Glob,Grep`
- 实现档：`Read,Write,Edit,Bash,Glob,Grep`

两者都是**裸工具名**，不带圆括号里的命令模式。

## 2. 发现 1 —— 现有两档预设的真实含义

裸 `Bash`（不带命令模式）在 Claude Code 里等于**放开整个 Bash 工具、不
限制具体命令**——也就是说"Implementation"这一档任务，今天就已经是
**无限制 shell 执行**，本来就能跑 `git commit`/`pytest`，不需要额外修复。

`SKILL.md` 把这两档描述成有粗细之分，但只要两者都带裸 `Bash`，在 shell
能力上其实等价；差别只在有没有 `Write`/`Edit`。这一点需要在文档里讲清楚，
避免给人"实现档比探索档更危险是因为多了 Write"之外的、关于 Bash 收紧的
错觉。

## 3. 发现 2 —— 更细粒度的写法确实存在，但有严重限制（已实测）

Claude Code 的 `--allowedTools` 支持带命令模式的写法，但实测下来有三个
硬限制：

### 3.1 前缀通配可以收紧命令族

`--allowedTools 'Bash(git add:*)'` 之类"字面前缀 + 冒号星号"的写法可以
只放行特定命令族（如 `git add`/`git commit`），比裸 `Bash` 收紧。这是
有用的一层，但只防"跑了完全没列过的命令"，不防下一节说的拼接。

### 3.2 路径中间的 `*` 不是通配符

路径中间的 `*`（比如 `Bash(bash tests/collapse/*.sh:*)`）**不是通配符，
是字面字符**，永远匹配不上真实文件名。要匹配一组脚本，只能一个个写精确
全字符串（`Bash(bash tests/collapse/dt1_gates.sh)`），**没有目录级通配**。
这让"放行一整个测试目录"这类诉求在白名单层面无法简洁表达。

### 3.3 最关键的限制：白名单只查前缀，不查拼接

**这套白名单只检查命令是不是以某个允许的字符串开头，完全不检查后面有没有
拼接别的命令。** 实测复现：

- 白名单只写 `Bash(python3.12 -m pytest:*)`，模型跑
  `python3.12 -m pytest -q tests/ && rm -rf /tmp/xxx/keep`，**照样整条
  命令直接执行**，`rm -rf` 部分完全没有被拦截、没有二次询问。
- 换成**精确全字符串**匹配（不带任何通配符的
  `Bash(bash tests/collapse/ok_gate.sh)`）结果一样——命令拼接同样能绕过。

**所以无论裸 Bash、前缀通配、还是精确字符串，只要是 Bash 白名单，一旦被
允许就等于对那一整条（可能被拼接过的）命令行放行，不构成能防拼接注入的
沙箱边界。**

## 4. 发现 3 —— 并发派发多个 Claude-MaaS 子任务时的 git 锁竞态（已实测）

考虑"分解一个大任务成多个子任务、并发派发给多个 Claude-MaaS 实例，每个
子任务各自完成后自己 `git commit`"这种编排模式，有一个真实风险：

git 的 `.git/index.lock` **没有任何自动重试机制**——两个并发的
`git commit` 一旦真撞上，后来的那个是硬失败
（`fatal: Unable to create '.git/index.lock': File exists.`，exit 128）。
Claude Code 的 Bash 工具本身不会自动重试，除非明确在 prompt 里要求模型
自己重试（这本身也只是软保证，不是硬保证）。

实测中 3 个子任务因为各自 LLM 往返耗时天然错开侥幸没撞上，但用人为制造的
锁冲突验证了"真撞上就是硬失败、没有重试"这个事实。也就是说：**并发
`git commit` 在概率上可能侥幸跑通，但在机制上没有保障，规模一上来迟早
撞锁硬失败。**

## 5. 建议与结论

本 PRD 只记录发现和建议，不规定对 `scripts/delegate` 的具体代码改动。

### 5.1 Bash 白名单不是沙箱

`Bash` 白名单（不管裸的还是精细的）应该被当作"这次会话获得完整 shell
信任"来看待，不是细粒度沙箱。真正的安全边界必须来自：

1. **routing-policy**——只委托低风险 `task_type`，从源头控制"这个任务
   本来就不该需要危险 shell"；
2. **委托方对 acceptance 命令结果的事后核实**——提交前独立看产出，而不是
   依赖工具白名单在执行时拦住什么。

`references/SECURITY.md` 应明确写出这条：`--allowedTools` 的 Bash 条目
不防命令拼接，不要把它当成能隔离危险操作的机制。

### 5.2 并发编排的正确形状

如果要用"分解 EPIC、并发派发给多个 Claude-MaaS 子任务"这种编排方式，
正确的形状是：

- **每个子任务只给 `Write`/`Edit` 权限、不给任何 git/Bash 权限**，只管
  写文件、汇报完成；
- **由编排方在所有子任务完成之后统一串行地做 `git add`/`commit`**。

这样并发只发生在慢的部分（LLM 写作/生成），而 git 操作保持单线程，天然
避开 `.git/index.lock` 竞态，顺带也保留了"编排方在提交前独立核实每个
子任务产出"这层把关——这恰好就是 5.1 要求的那层事后核实，两个结论在这里
汇合：把 git 收回到编排方手里，既解决了锁竞态，又把安全边界从"信任每个
子任务不拼命令"挪到了"编排方统一看一遍再提交"。

## 6. 回滚

本 PRD 为纯文档，不改动任何代码，无回滚动作。
