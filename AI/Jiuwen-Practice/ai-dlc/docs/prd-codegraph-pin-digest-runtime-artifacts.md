# PRD · pin 摘要计算应该只看 git 追踪的文件，不该把运行时产物算进去

> pin 想守住的是"这份技能说明有没有被人偷偷改过"。node_modules 从来
>不是那份说明的一部分——它是运行这份说明时顺手长出来的东西。

- 目标仓库：`<workspace-root>`（`bin/plan.py`）
- 关联：`docs/prd-codegraph-understand-anything-backend.md`（C1，pin
  机制的原始设计）
- 文档日期：2026-09-04
- 优先级：P1（不是功能性 bug——pin 校验本身工作正常——但每次真实建图
  之后 pin 都会自动失效，靠人工重装才能恢复，不可持续）

---

## 01 真实复现（这次连续两次真实派发独立复现同一现象）

这一轮 live 验证（验证 A/B 两个修复是否生效，并观察 graph 对开发效率
的实际帮助）里，第一次真实建图派发（`verify-ab`，全量分析，669 秒）
成功后，**紧接着第二次派发**（同一台机器、同一个 pin，没有任何人
手动碰过 `/opt/understand-anything`）就撞上了 pin 校验失败：

```json
{
  "ok": false,
  "pinned_tree_sha256": "31f821306c09cb...",
  "measured_tree_sha256": "7e1ea57bfe49f4e7...",
  "why": "the tree's measured digest no longer matches the pin"
}
```

排查发现：`understand-anything-plugin/` 子树下重新出现了一整个
`node_modules/`（含 `tree-sitter-python`、`tree-sitter-ruby`、
`tree-sitter-go` 等原生语法绑定）——而 `git -C /opt/understand-anything
status --porcelain -uall -- understand-anything-plugin` 在同一时刻
**报告零变化**（该子树下没有任何 git 追踪的文件被改动过）。

这不是本次会话第一次遇到这个现象——更早一次真实端到端实测（Phase
C2 落地时那次"382 秒建图"实测）同样留下过 `node_modules`，当时被当作
"这次实测的副作用，修一次就好"处理（见更早的 pin 修复记录）。**这次
是第二次独立复现，且间隔仅一次真实派发**，说明这不是偶发环境问题，
是**每次真正跑起 Understand-Anything 的分析流水线，都会必然复现**的
系统性问题——大概率是 `packages/core` 依赖的 tree-sitter 原生语法
绑定在首次真正解析代码时被懒加载安装进 `node_modules`（这正是
`node_modules/@types`、`node_modules/.pnpm` 一类 pnpm 管理产物出现
的典型模式）。

## 02 根因

`understand_anything_tree_digest()`（`bin/plan.py:5877`）的实现：

```python
def understand_anything_tree_digest(root: Path) -> str:
    for sub in UNDERSTAND_ANYTHING_PATHS:
        base = root / sub
        for p in base.rglob("*"):     # ← 扫文件系统，不看 git 状态
            if p.is_file():
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
                lines.append(f"{digest}  {p.relative_to(root).as_posix()}")
    ...
```

`base.rglob("*")` 是纯文件系统遍历，**不区分"git 追踪的源文件"和
"运行时/构建产物"**——`node_modules`、`dist`、`__pycache__`、
`*.tsbuildinfo`、`coverage/` 这些，Understand-Anything 上游仓库自己的
`.gitignore`（`/opt/understand-anything/.gitignore`，pin 住的 sparse
clone 里这个文件本身就在——顶层文件属于 sparse-checkout cone 的
`/*` 那一条）早就列得清清楚楚：

```
node_modules
dist
.understand-anything
*.tsbuildinfo
.DS_Store
.env
.env.*
coverage/
*.log
__pycache__/
...
```

但我们的摘要函数从来没读过这个文件，也没有自己的排除列表——任何
落在 `understand-anything-plugin/` 子树下的文件，不管是不是 git 追踪
的源码，都被算进了摘要。**pin 想守住的不变式是"这份技能说明没被人
偷偷改过"（I3/INV-10），但摘要函数实际测量的是"这个目录下的字节没有
任何变化"——两者在"运行时产物"这一类文件上不是同一件事**：跑一次真实
分析、装出一个 `node_modules`，摘要就变了，但没有任何"技能说明被
改过"的事实发生。

## 03 目标架构

**只改一个函数**：`understand_anything_tree_digest()`。不自己维护一份
排除列表去照抄 `.gitignore` 的语义（glob 语义容易抄错、以后
`.gitignore` 改了这边又要跟着改）——改成**直接问 git 本身**：

```python
def understand_anything_tree_digest(root: Path) -> str:
    """..."""
    root = Path(root)
    lines = []
    for sub in UNDERSTAND_ANYTHING_PATHS:
        # git 追踪的文件列表本身就是权威的"这是源码，不是运行时产物"
        # 判定——不必自己抄一份 .gitignore 语义（glob 规则容易抄错，
        # 且 .gitignore 以后变了这里要跟着变）。sparse-checkout cone
        # 完整包含每个 UNDERSTAND_ANYTHING_PATHS 条目，ls-files 和磁盘
        # 内容因此是一一对应的，不存在 skip-worktree 的文件被漏算。
        proc = run(["git", "-C", str(root), "ls-files", "-z", "--", sub])
        if proc.returncode != 0:
            continue
        for rel in proc.stdout.split("\0"):
            if not rel:
                continue
            p = root / rel
            if not p.is_file():
                continue
            try:
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
            except OSError:
                continue
            lines.append(f"{digest}  {rel}")
    h = hashlib.sha256()
    for line in sorted(lines):
        h.update(line.encode("utf-8") + b"\n")
    return h.hexdigest()
```

要点：
- 用 `git ls-files -z` 拿 NUL 分隔的追踪文件列表（避免文件名带空格/
  特殊字符时用换行分隔出错），限定在每个 `UNDERSTAND_ANYTHING_PATHS`
  条目下（跟现有行为一致，不擴大范围）。
- 每个文件仍然读**当前磁盘上的实际字节**去算 sha256（不是读 git
  blob）——这保留了原有设计要守住的真实威胁模型：如果有人真的改了
  一个**被追踪的**源文件的磁盘内容（哪怕没 commit），摘要照样能测出
  来，I3/INV-10 的保护能力不打折扣。改变的只是"不再把从未被 git
  追踪过的文件（运行时产物）算进测量范围"。
- `git ls-files` 是只读操作，pin 住的树是 `555`/`0444` 只读权限，不
  影响这条命令执行（`git describe --tags`/`git status` 已经在既有
  安装脚本里对同一棵只读树跑过，验证过只读权限不妨碍读类 git 命令）。
- 复用仓库已有的 `run()` helper（`subprocess.run` 的既有封装，
  `bin/plan.py` 里到处在用），不新增子进程调用的模式。

**不改的地方**：`UNDERSTAND_ANYTHING_PATHS`、`understand_anything_pin_state()`
的其余逻辑、`cmd_codegraph_pin`、安装脚本
`scripts/install-understand-anything.sh` 本身——这些都不需要动，
`--write-pin` 调用的还是同一个 `understand_anything_tree_digest()`，
自动获得新的、不受运行时产物影响的计算方式。

## 04 不变式

- **INV-19**：`understand_anything_tree_digest` 的测量范围收窄为
  "pin 住的子树下、git 追踪的文件"——一个从未被 git 追踪过的文件
  （不论是运行时产物、还是任何原因产生的杂散文件）不再影响摘要，
  不再触发误报的"pin 不匹配"。
- 延续既有 I3/INV-10：任何被 git 追踪的源文件，其**磁盘内容**只要
  跟 pin 记录的摘要对不上，依然正确判定为"树被改过"——保护能力不
  变，只是不再被无关的运行时产物误伤。

## 05 反向门

延续既有：`understand_anything_pin_state` 的四种失败分支（树不存在/
无 pin 文件/pin 缺字段/pinned 路径缺失/摘要不匹配）都不变——本 PRD
只改摘要**怎么算**，不改校验失败时的处理方式（依然是 exit 26，依然
拒绝派发，不静默放行）。

## 06 验收

- 单元测试（新增或扩展合适的 pin 相关测试文件——检索
  `understand_anything_tree_digest`/`understand_anything_pin_state`
  当前有没有专门的测试文件，没有就新建
  `tests/test_understand_anything_pin.py`）：
  1. 造一个临时 git 仓库，`understand-anything-plugin/` 下放几个
     "源文件"（git add + commit）和一个模拟的 `node_modules/foo.js`
     （**不** git add，保持未追踪）。计算摘要，记录下来。
  2. 往 `node_modules/foo.js` 里追加内容（模拟运行时产物变化）——
     再算一次摘要，断言**摘要不变**（这是修复前会失败的用例——回归
     测试：确认这次改动前会失败，改动后通过）。
  3. 修改一个**被追踪**的源文件内容（不 commit，只改磁盘）——再算
     一次摘要，断言**摘要变了**（确认 I3 的真实威胁模型仍然被正确
     检测——这条在修复前后都应该通过，防止"修复"矫枉过正到摘要对
     任何改动都不敏感）。
  4. 新增一个**未追踪**的文件到子树下——摘要不变（同 2，另一种运行
     时产物落地方式）。
  5. 删除一个被追踪的源文件——摘要变了（确认删除也能被测出来，
     不是只测内容修改和新增）。
- 回归：全量 `pytest` + `tests/collapse/dt1_gates.sh`。
- 手动复现验证（实施者跑一次，不用写进自动化测试）：`bash
  scripts/install-understand-anything.sh --uninstall && bash
  scripts/install-understand-anything.sh --write-pin`，然后针对一个
  真实仓库跑一次 `plan.py codegraph build`（会真正触发 tree-sitter
  绑定懒加载，历史上两次都复现了 node_modules 落地），再跑
  `plan.py codegraph-pin` 确认**这次不再报 mismatch**。这是本 PRD
  要解决的真实症状，比任何单元测试都更直接的验收标准。

## 07 风险与残余

- `git ls-files` 依赖 pin 住的树本身是一个健康的 git 仓库（`.git`
  目录完整）——这本来就是安装脚本的前提（sparse clone 出来的就是
  一个真实 git 仓库），不是本 PRD 新引入的依赖。
- 如果上游 Understand-Anything 未来把某个真正的源文件加进它自己的
  `.gitignore`（这种情况理论上可能发生但极不寻常——源文件通常不会被
  忽略），那个文件也会从我们的摘要测量范围里消失。这是"信任 git 自己
  的追踪状态"这个设计选择的自然结果，跟"抄一份自己的排除列表"比起来，
  信任 git 本身更不容易出错、维护成本更低——权衡后选择信任 git。
- 不修复"为什么 tree-sitter 绑定会被懒加载安装"这件事本身（那是
  Understand-Anything 自己的实现细节，不是我们能控制或应该控制的
  范围）——本 PRD 只是让 pin 校验不再被这类无害的运行时行为误伤。

## 08 回滚

只改了 `understand_anything_tree_digest` 一个函数体——回滚即恢复到
"扫整个文件系统，不看 git 追踪状态"的现状，行为退回本 PRD 修复之前：
pin 校验能力不受影响（依然能测出被追踪文件的真实改动），只是重新
容易被运行时产物误伤，需要靠人工在每次真实派发后重装修复。
