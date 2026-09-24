# E00：MaaS 与 TUI 模型配置

JiuwenSwarm TUI/backend 和 AutoOps 模型连通性检查共用 JiuwenSwarm 标准配置文件：`~/.jiuwenswarm/config/.env`。MaaS 配置字段为 `API_BASE`、`API_KEY`、`MODEL_NAME`、`MODEL_PROVIDER`。默认推荐模型 `deepseek-v4.1-flash`，使用华为云 MaaS OpenAI 兼容 endpoint；请确认该模型对当前账号可用。

向导只更新这四个字段，保留同一 `.env` 中的其他 JiuwenSwarm 配置；API Key 隐藏输入，文件设为 `0600`。这也是本项目所有组件使用的唯一模型配置入口。

## 首次安装

安装 JiuwenSwarm 后，以安装/TUI 操作用户执行 AutoOps 安装。推荐在 sudo 安装时启用向导，向导会根据 `SUDO_USER` 写入该用户的 JiuwenSwarm 配置：

```bash
sudo ./scripts/install-autoops.sh --bin-dir /usr/local/bin --configure-model
```

AutoOps 已安装时可单独运行向导：

```bash
sudo /opt/Jiuwenswarm_AutoOps/scripts/configure-model.py
```

若当前用户有该文件写权限，可直接执行并省略 `sudo`。已有 MaaS Key 留空会继续保留；覆盖配置前会询问确认。`--force` 可用于明确跳过确认。

配置样例位于 `config/model.env.example`。已有 `.env` 可能包含 JiuwenSwarm 的其他 API、MCP、媒体或运行设置，不要用样例整文件覆盖；手动修改时只编辑以下四个变量：

```dotenv
API_BASE="https://api-ap-southeast-1.modelarts-maas.com/openai/v1"
API_KEY="从密钥管理系统提供的 Key"
MODEL_NAME="deepseek-v4.1-flash"
MODEL_PROVIDER="OpenAI"
```

不要把真实 Key 写入 Git、PRD、任务提示或 shell 命令参数。若通过 sudo 向导写入，配置文件会归属执行 sudo 的原用户；TUI 和 smoke test 应由该用户运行。

## 连通性检查

以下命令使用当前用户的同一 `.env`：

```bash
scripts/maas-smoke-test.sh
scripts/maas-chat-smoke-test.sh
scripts/jiuwenswarm-tui-preflight.sh
```

第一个脚本查询账户可用模型，第二个脚本用当前 `MODEL_NAME` 发出短请求。脚本只输出 endpoint 主机和模型名，不打印 Key。预检确认 JiuwenSwarm CLI 和配置可用，不会启动或修改上游源码。

配置模型后重启 JiuwenSwarm backend，让它重新载入 `.env`，再启动 TUI：

```bash
jiuwenswarm-start --restart default
Jiuwen_autoops_tui
```

如果当前 JiuwenSwarm 安装的默认实例不叫 `default`，先用 `jiuwenswarm-start --list` 查看实例名。日后更换模型时继续使用同一个 `configure-model.py` 向导，不要另建 `HUAWEI_MAAS_*` 变量文件。
