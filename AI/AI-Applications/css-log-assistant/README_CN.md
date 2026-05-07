# CSS Log Query Assistant

基于华为云 CSS (Cloud Search Service) + MAAS (Model as a Service) 的拉美外卖日志查询助手。

通过自然语言提问，助手自动生成 Elasticsearch 查询、执行并返回分析结果，思考过程实时可见。

[English Documentation](./README.md)

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         用户浏览器                                  │
│                    Streamlit Web UI (localhost:8501)                │
│   ┌───────────────────────────────────────────────────────────┐     │
│   │  💬 自然语言问题                                          │     │
│   │  🧠 实时思考过程 (Thinking)                               │     │
│   │  📊 查询结果 + ES Query DSL                              │     │
│   └───────────────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌─────────────────────────┐ ┌─────────────────────────────────────┐
│   华为云 CSS 集群        │ │   华为云 MAAS (香港 ap-southeast-1) │
│   (拉美 la-north-2)      │ │                                     │
│                         │ │   ┌─────────────────────────────┐   │
│   Elasticsearch 7.10.2  │ │   │   GLM 5.1 大语言模型        │   │
│   3 × ess.spec-4u8g     │ │   │                             │   │
│   HTTPS + 安全认证       │ │   │  ① NL → ES Query DSL       │   │
│                         │ │   │  ② 结果分析与摘要           │   │
│   索引: food_delivery_   │ │   └─────────────────────────────┘   │
│   logs-YYYY.MM.dd       │ │                                     │
│                         │ │   Anthropic 兼容 API               │
│   ~181万条外卖日志       │ │   /anthropic/v1/messages           │
│   10个拉美国家           │ │                                     │
│   6个月时间跨度          │ │                                     │
└─────────────────────────┘ └─────────────────────────────────────┘
              ▲
              │ Terraform 自动创建
              │
┌─────────────┴─────────────────────────────────────────────────────┐
│                        基础设施层 (Terraform)                      │
│                                                                    │
│   ┌──────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│   │   VPC    │→│    Subnet    │→│  Security Group            │  │
│   │192.168.  │  │192.168.0.0/24│  │  9200 (ES REST API)      │  │
│   │0.0/16   │  │              │  │  5601 (Kibana)            │  │
│   └──────────┘  └──────────────┘  │  8000 (MCP SSE)          │  │
│                                     │  9300 (ES Transport)     │  │
│                                     └────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## 数据流

```
用户提问 ──→ MAAS GLM 5.1 ──→ ES Query DSL ──→ CSS 集群 ──→ 查询结果 ──→ MAAS GLM 5.1 ──→ 自然语言回答
              (生成查询)         (JSON)          (Elasticsearch)  (JSON)      (分析结果)        (Markdown)
              [实时Thinking]                                                   [实时Thinking]
```

## 日志数据覆盖

| 国家 | 代码 | 货币 | 主要城市 |
|------|------|------|----------|
| Mexico | MX | MXN | Mexico City, Guadalajara, Monterrey |
| Brazil | BR | BRL | Sao Paulo, Rio de Janeiro, Brasilia |
| Argentina | AR | ARS | Buenos Aires, Cordoba, Rosario |
| Colombia | CO | COP | Bogota, Medellin, Cali |
| Chile | CL | CLP | Santiago, Valparaiso, Concepcion |
| Peru | PE | PEN | Lima, Arequipa, Cusco |
| Ecuador | EC | USD | Quito, Guayaquil, Cuenca |
| Uruguay | UY | UYU | Montevideo, Punta del Este |
| Panama | PA | USD | Panama City, Colon, David |
| Costa Rica | CR | CRC | San Jose, Alajuela, Heredia |

---

## 前置条件

| 工具 | 版本要求 | 用途 |
|------|----------|------|
| Python | >= 3.9 | 运行脚本和 Streamlit |
| Terraform | >= 1.0 | 自动创建华为云基础设施 |
| pip | 任意 | 安装 Python 依赖 |
| 华为云账号 | 有 CSS 和 MAAS 权限 | 提供云服务 |

---

## 快速开始

### Step 1: 克隆项目

```bash
git clone https://github.com/ngtsunhian-lab/css-log-assistant.git
cd css-log-assistant
```

### Step 2: 安装 Python 依赖

```bash
pip3 install -r scripts/requirements.txt
```

安装的包：

| 包 | 用途 |
|----|------|
| elasticsearch (7.x) | 连接 CSS 集群 |
| faker | 生成模拟日志数据 |
| python-dotenv | 加载 .env 配置 |
| httpx | 调用 MAAS API |
| streamlit | Web UI 界面 |

### Step 3: 配置华为云凭证

#### 3a. 获取 AK/SK

登录 [华为云控制台](https://console.huaweicloud.com/)，进入 **统一身份认证服务 (IAM)**：

```
控制台 → IAM → 访问密钥 → 新增访问密钥
```

```
┌──────────────────────────────────────────────┐
│  华为云控制台                                  │
│                                                │
│  ┌─────────────────────────────────────────┐   │
│  │  IAM → 访问密钥                          │   │
│  │                                          │   │
│  │  [新增访问密钥]                            │   │
│  │                                          │   │
│  │  Access Key ID:  HPUAxxxxxxxxxxx         │   │
│  │  Secret Key:      ************************ │   │
│  └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

> **注意**: AK/SK 需要有 CSS、VPC、SecurityGroup 的创建权限。

#### 3b. 获取 MAAS API Key

登录华为云 MAAS 控制台 (香港区域 `ap-southeast-1`)，获取 API Key：

```
控制台 → ModelArts Studio → API Key 管理 → 创建 API Key
```

#### 3c. 填写 Terraform 变量

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

编辑 `terraform/terraform.tfvars`，填入你的凭证：

```hcl
huaweicloud_access_key = "你的AccessKeyID"
huaweicloud_secret_key = "你的SecretAccessKey"
css_region             = "la-north-2"
maas_region            = "ap-southeast-1"
css_admin_password     = "你的CSS密码"    # 8-32位，含大写+小写+数字+特殊字符
maas_api_key           = "你的MAAS_API_KEY"
```

密码要求示例：`CssL0g@ssistant2026`

### Step 4: 创建基础设施

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Terraform 将创建以下资源：

```
┌─────────────────────────────────────────────┐
│  Terraform 将创建 9 个资源:                   │
│                                               │
│  ① huaweicloud_vpc.css                       │
│     └─ 192.168.0.0/16                        │
│                                               │
│  ② huaweicloud_vpc_subnet.css                │
│     └─ 192.168.0.0/24                        │
│                                               │
│  ③ huaweicloud_networking_secgroup.css        │
│     ├─ ④ 规则: TCP 9200 (ES REST API)        │
│     ├─ ⑤ 规则: TCP 5601 (Kibana)             │
│     ├─ ⑥ 规则: TCP 8000 (MCP SSE)            │
│     ├─ ⑦ 规则: TCP 9300 (ES Transport, 内部) │
│     └─ ⑧ 规则: TCP 9200-9400 (内部通信)      │
│                                               │
│  ⑨ huaweicloud_css_cluster.log_assistant     │
│     ├─ Elasticsearch 7.10.2                  │
│     ├─ 3 × ess.spec-4u8g 节点                │
│     ├─ HTTPS + 安全认证                       │
│     └─ 公网访问 (10 Mbit/s)                   │
└─────────────────────────────────────────────┘
```

CSS 集群创建约需 **5-10 分钟**。

创建完成后，获取集群公网 IP：

```bash
terraform output css_public_ip
# 输出示例: 122.8.182.132:9200
```

### Step 5: 生成模拟日志

```bash
cd ../scripts
python3 generate_logs.py \
  --start-date 2025-11-01 \
  --end-date 2026-05-01 \
  --logs-per-day 10000 \
  --output-dir ../output
```

将生成约 **181 万条**日志，存储在 `output/` 目录的 37 个批次文件中：

```
output/
├── logs_batch_0001.json   (50,000 条)
├── logs_batch_0002.json   (50,000 条)
├── ...
└── logs_batch_0037.json   (10,000 条)
```

每条日志格式示例：

```json
{
  "timestamp": "2026-03-15T12:30:45Z",
  "order_id": "ORD-A3F2B1C4D5",
  "country": "Mexico",
  "country_code": "MX",
  "city": "Mexico City",
  "restaurant_name": "Taco Palace",
  "order_status": "delivered",
  "total_amount": 234.50,
  "currency": "MXN",
  "delivery_time_minutes": 32,
  "payment_method": "credit_card",
  "platform": "android"
}
```

### Step 6: 导入日志到 CSS

```bash
python3 upload_to_es.py \
  --es-url "https://<CSS_PUBLIC_IP>:9200" \
  --username admin \
  --password "<你的CSS密码>" \
  --insecure \
  --input-dir ../output \
  --index-prefix food_delivery_logs
```

将 `<CSS_PUBLIC_IP>` 替换为 Step 4 中 `terraform output css_public_ip` 的值（去掉 `:9200` 后缀）。

导入过程约需 **10-20 分钟**，日志将按天存储在索引 `food_delivery_logs-YYYY.MM.dd` 中。

### Step 7: 配置运行环境

在项目根目录创建 `.env` 文件：

```bash
cd ..
cp .env.example .env
```

编辑 `.env`，填入你的 CSS 集群和 MAAS 信息：

```bash
ES_URL=https://<CSS_PUBLIC_IP>:9200
ES_USERNAME=admin
ES_PASSWORD=<你的CSS密码>
ES_INSECURE=true
ES_INDEX_PATTERN=food_delivery_logs-*
MAAS_API_KEY=<你的MAAS_API_KEY>
MAAS_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/anthropic/v1
MAAS_MODEL=glm-5.1
```

### Step 8: 启动查询助手

```bash
cd app
python3 -m streamlit run app.py
```

浏览器将自动打开 http://localhost:8501

```
┌──────────────────────────────────────────────────────────────┐
│  CSS Log Query Assistant                                      │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ 💬 Ask a question about food delivery logs             │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  示例问题:                                                      │
│  • What were the top 5 cities by order volume in March?       │
│  • Show me the cancellation rate by country for April 2026    │
│  • What is the average delivery time in Sao Paulo?            │
│  • Which restaurants had the most orders in Lima?             │
│  • What are the peak ordering hours across all countries?     │
└──────────────────────────────────────────────────────────────┘
```

### Step 9: 开始提问！

在输入框中输入自然语言问题，助手将：

```
┌─────────────────────────────────────────────────────────────┐
│  🧑 What were the top 5 cities by order volume in March?     │
├─────────────────────────────────────────────────────────────┤
│  🤖                                                          │
│                                                               │
│  Generating Elasticsearch query...                           │
│                                                               │
│  ▼ Thinking                                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ The user wants top 5 cities by order volume in March.   │ │
│  │ I need to use a terms aggregation on the "city" field   │ │
│  │ with a date range filter for March 2026...              │ │
│  │ → 实时逐字显示思考过程                                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Executing query...                                          │
│                                                               │
│  Analyzing results...                                        │
│                                                               │
│  ▼ Thinking                                                  │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Looking at the aggregation results, the top 5 cities    │ │
│  │ by order volume are...                                  │ │
│  │ → 实时逐字显示思考过程                                     │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  Here are the top 5 cities by order volume in March 2026:    │
│                                                               │
│  1. Mexico City - 31,245 orders                              │
│  2. Sao Paulo - 28,891 orders                                │
│  3. Buenos Aires - 25,634 orders                             │
│  4. Bogota - 22,118 orders                                   │
│  5. Santiago - 19,872 orders                                 │
│                                                               │
│  ▼ Elasticsearch Query DSL    ▼ Sample hits                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
css-log-assistant/
├── .env.example                    # 环境变量模板
├── .env                            # 环境变量 (需创建, git-ignored)
├── .gitignore
│
├── app/                            # Streamlit 查询助手应用
│   ├── app.py                      #   主界面 - 流式展示思考+回答
│   ├── config.py                   #   配置加载 (自动读 .env)
│   ├── es_mcp_client.py            #   Elasticsearch 客户端
│   └── maas_client.py              #   MAAS GLM 5.1 客户端 (流式)
│
├── scripts/                        # 数据生成和导入脚本
│   ├── generate_logs.py            #   生成 10 国外卖日志
│   ├── upload_to_es.py             #   批量导入到 CSS
│   └── requirements.txt            #   Python 依赖
│
├── terraform/                      # 基础设施即代码
│   ├── providers.tf                #   华为云 Provider 配置
│   ├── variables.tf                #   变量定义
│   ├── network.tf                  #   VPC + Subnet + SecurityGroup
│   ├── css.tf                      #   CSS 集群资源
│   ├── outputs.tf                  #   输出 (集群 IP, 状态等)
│   └── terraform.tfvars.example    #   凭证模板
│
└── output/                         # 生成的日志文件 (git-ignored)
    ├── logs_batch_0001.json
    └── ...
```

---

## 销毁资源

演示完成后，销毁华为云资源以避免持续计费：

```bash
cd terraform
terraform destroy
```

---

## 常见问题

### Q: terraform apply 报错 "Insufficient permissions"

AK/SK 对应的 IAM 用户需要以下权限：
- VPC Administrator
- CSS Administrator
- Security Group Administrator

在 IAM 控制台为用户添加对应权限策略。

### Q: terraform apply 报错 "Illegal period"

CSS 集群默认使用按需计费 (postPaid)，无需指定包周期。确保 `css.tf` 中没有 `charging_mode`、`period`、`period_unit` 参数。

### Q: Streamlit 报错 "ES_URL is required"

确保项目根目录有 `.env` 文件且包含 `ES_URL`。`config.py` 会自动加载 `../.env`（相对于 app 目录）。

### Q: Streamlit 报错 "'text'"

GLM 5.1 的响应中包含 `thinking` 和 `text` 两种 content block。`maas_client.py` 已处理此情况，遍历查找 `type == "text"` 的块。

### Q: ES 查询报错 "No mapping found for [@timestamp]"

GLM 5.1 可能按 Elastic Common Schema 惯例生成 `@timestamp`，但本项目的索引字段是 `timestamp`（无 `@` 前缀）。system prompt 中已明确声明字段名，如仍出错可在提问时补充说明。

### Q: CSS 集群创建需要多久？

通常 5-10 分钟。可通过 `terraform output css_cluster_status` 查看状态，`200` 表示可用。

### Q: 如何调整日志数据量？

修改 `generate_logs.py` 的 `--logs-per-day` 参数。默认 10,000 条/天 × 181 天 ≈ 181 万条。减少到 1,000 条/天可快速演示。
