# PRD · 文档清理：codegraph 相关文档不再体现 CodeGraph/GitNexus

> 代码里已经没有 CodeGraph/GitNexus 的痕迹了——C2 那轮重写彻底换成了
> Understand-Anything 的会话派发设计，`CODEGRAPH_CLIENT` 这个变量本身
> 都不存在了。这次要清的是文档里留的选型过程叙事。

- 目标仓库：`<workspace-root>`（`docs/` 下两份 PRD）
- 文档日期：2026-09-04
- 优先级：P2（纯文档，不影响任何功能）

## 01 现状核查

先核实了代码侧确实干净——全仓库搜 `CodeGraph|GitNexus|CODEGRAPH_CLIENT|
codegraph-ai|abhigyanpatwari`，`bin/`、`scripts/`、`config/`、`tests/`、
`install.sh` 里只有 `bin/plan.py` 一处注释提到"no glibc dependency"（说明
选型理由，不点名具体工具），没有任何实际代码逻辑引用这两个工具。

文档侧命中两处：

- `docs/prd-codegraph-understand-anything-backend.md` 的 §01"选型过程"
  整节都在叙述"先试 CodeGraph 失败、再试 GitNexus 失败、修了 EPEL 镜像
  和 openssl3-libs、最后才选定 Understand-Anything"这条完整过程。
- `docs/prd-codegraph-role.md` 里三处提及 CodeGraph/GitNexus/
  CodeGraphContext，都是早期调研阶段（选定 Understand-Anything之前）
  的背景引用。

## 02 目标与非目标

**目标**

- `docs/prd-codegraph-understand-anything-backend.md` 的 §01 改写成
  直接陈述选型理由（"prompt/skill 驱动、无编译产物、不依赖特定 glibc
  版本，因此优先选择"），不点名 CodeGraph、GitNexus，不叙述"先试了什么
  又失败了"的过程。§02 起（Understand-Anything 本身的技术事实：MIT
  协议、`.claude-plugin` 插件格式、`understand`/`understand-diff` 技能
  方法论）原样保留——那些是描述"我们选的东西是什么"，不是"我们放弃了
  什么"，跟本次清理无关。
- `docs/prd-codegraph-role.md` 里三处提及 CodeGraph/GitNexus/
  CodeGraphContext 的地方，改成不点名具体工具的表述（"外部代码知识
  图谱工具"一类的通用说法），技术论点本身（token/工具调用节省比例等
  数据引用）不需要删，只改措辞不点名。
- 章节编号、其余内容结构不因为这次编辑而打乱——纯替换/精简，不重排。

**非目标**

- 不删除、不改写 EPEL 镜像重定向和 openssl3-libs 这两个真实环境修复的
  技术事实本身——那是这台机器包管理器的真实缺陷记录，跟"选没选
  CodeGraph/GitNexus"是两件事；只要改写后的措辞不再点名是"装
  CodeGraph/GitNexus 时发现的"，保留"这台机器的 EPEL 源配置有问题、
  已修复"这条事实即可（甚至可以完全略去，因为这两个包管理器修复已经
  是这台机器的既成事实，不需要在 PRD 里反复重述——具体去留由实施时
  判断，保留技术准确性优先于精简）。
- 不改动任何代码文件——本 PRD 范围只有 `docs/` 下这两份文件。
- 不改动 `docs/prd-jiuwenswarm-understand-anything-subagents.md`——那份
  从头到尾没提过 CodeGraph/GitNexus，不在范围内（已核实）。

## 03 验收

- `grep -rli "CodeGraph\|GitNexus" docs/` 只应该在
  `docs/prd-codegraph-docs-cleanup.md`（本文件自己，元描述）里出现，
  其余文档不再有这两个词。
- 改写后的 `docs/prd-codegraph-understand-anything-backend.md` 仍然是
  一份读得通、自洽的 PRD——不能因为删了选型过程叙事就留下悬空的
  引用（比如后文如果引用了"前面提到的两次失败"这类措辞，要一并清理）。

## 04 回滚

纯文本编辑，`git revert` 这一个提交即可完全恢复。
