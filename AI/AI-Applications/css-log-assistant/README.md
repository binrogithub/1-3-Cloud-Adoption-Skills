# CSS Log Query Assistant

A food delivery log query assistant for Latin America, powered by Huawei Cloud CSS (Cloud Search Service) + MAAS (Model as a Service).

Ask questions in natural language — the assistant generates Elasticsearch queries, executes them, and returns analysis results with real-time visible thinking process.

[中文文档](./README_CN.md)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         User Browser                                │
│                    Streamlit Web UI (localhost:8501)                 │
│   ┌───────────────────────────────────────────────────────────┐     │
│   │  💬 Natural language question                             │     │
│   │  🧠 Real-time thinking process                           │     │
│   │  📊 Query results + ES Query DSL                         │     │
│   └───────────────────────────────────────────────────────────┘     │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
┌─────────────────────────┐ ┌─────────────────────────────────────┐
│   Huawei Cloud CSS       │ │   Huawei Cloud MAAS                │
│   (LA la-north-2)        │ │   (HK ap-southeast-1)             │
│                          │ │                                     │
│   Elasticsearch 7.10.2   │ │   ┌─────────────────────────────┐ │
│   3 × ess.spec-4u8g      │ │   │   GLM 5.1 LLM              │ │
│   HTTPS + Auth           │ │   │                             │ │
│                          │ │   │  ① NL → ES Query DSL       │ │
│   Indices: food_delivery_│ │   │  ② Result analysis         │ │
│   logs-YYYY.MM.dd        │ │   └─────────────────────────────┘ │
│                          │ │                                     │
│   ~1.81M delivery logs   │ │   Anthropic-compatible API        │
│   10 LATAM countries     │ │   /anthropic/v1/messages          │
│   6-month timespan       │ │                                     │
└─────────────────────────┘ └─────────────────────────────────────┘
              ▲
              │ Terraform provisioned
              │
┌─────────────┴─────────────────────────────────────────────────────┐
│                     Infrastructure Layer (Terraform)               │
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

## Data Flow

```
User Question ──→ MAAS GLM 5.1 ──→ ES Query DSL ──→ CSS Cluster ──→ Query Results ──→ MAAS GLM 5.1 ──→ NL Answer
                  (generate query)    (JSON)          (Elasticsearch)  (JSON)          (analyze results)   (Markdown)
                  [real-time Thinking]                                                 [real-time Thinking]
```

## Log Data Coverage

| Country | Code | Currency | Key Cities |
|---------|------|----------|------------|
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

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | >= 3.9 | Run scripts and Streamlit |
| Terraform | >= 1.0 | Provision Huawei Cloud infrastructure |
| pip | any | Install Python dependencies |
| Huawei Cloud account | CSS + MAAS access | Cloud services |

---

## Quick Start

### Step 1: Clone the project

```bash
git clone https://github.com/ngtsunhian-lab/css-log-assistant.git
cd css-log-assistant
```

### Step 2: Install Python dependencies

```bash
pip3 install -r scripts/requirements.txt
```

Packages installed:

| Package | Purpose |
|---------|---------|
| elasticsearch (7.x) | Connect to CSS cluster |
| faker | Generate synthetic log data |
| python-dotenv | Load .env configuration |
| httpx | Call MAAS API |
| streamlit | Web UI interface |

### Step 3: Configure Huawei Cloud credentials

#### 3a. Get AK/SK

Log in to [Huawei Cloud Console](https://console.huaweicloud.com/), navigate to **IAM**:

```
Console → IAM → Access Keys → Create Access Key
```

```
┌──────────────────────────────────────────────┐
│  Huawei Cloud Console                         │
│                                                │
│  ┌─────────────────────────────────────────┐   │
│  │  IAM → Access Keys                      │   │
│  │                                          │   │
│  │  [Create Access Key]                     │   │
│  │                                          │   │
│  │  Access Key ID:  HPUAxxxxxxxxxxx         │   │
│  │  Secret Key:      ************************ │   │
│  └─────────────────────────────────────────┘   │
└──────────────────────────────────────────────┘
```

> **Note**: The AK/SK needs permissions for CSS, VPC, and Security Group creation.

#### 3b. Get MAAS API Key

Log in to Huawei Cloud MAAS console (Hong Kong region `ap-southeast-1`), get your API Key:

```
Console → ModelArts Studio → API Key Management → Create API Key
```

#### 3c. Fill in Terraform variables

```bash
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
```

Edit `terraform/terraform.tfvars` with your credentials:

```hcl
huaweicloud_access_key = "YOUR_ACCESS_KEY_ID"
huaweicloud_secret_key = "YOUR_SECRET_ACCESS_KEY"
css_region             = "la-north-2"
maas_region            = "ap-southeast-1"
css_admin_password     = "YOUR_CSS_PASSWORD"    # 8-32 chars, uppercase+lowercase+digit+special
maas_api_key           = "YOUR_MAAS_API_KEY"
```

Password example: `CssL0g@ssistant2026`

### Step 4: Provision infrastructure

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Terraform will create these resources:

```
┌─────────────────────────────────────────────┐
│  Terraform creates 9 resources:              │
│                                               │
│  ① huaweicloud_vpc.css                       │
│     └─ 192.168.0.0/16                        │
│                                               │
│  ② huaweicloud_vpc_subnet.css                │
│     └─ 192.168.0.0/24                        │
│                                               │
│  ③ huaweicloud_networking_secgroup.css        │
│     ├─ ④ Rule: TCP 9200 (ES REST API)        │
│     ├─ ⑤ Rule: TCP 5601 (Kibana)             │
│     ├─ ⑥ Rule: TCP 8000 (MCP SSE)            │
│     ├─ ⑦ Rule: TCP 9300 (ES Transport, int)  │
│     └─ ⑧ Rule: TCP 9200-9400 (internal comm) │
│                                               │
│  ⑨ huaweicloud_css_cluster.log_assistant     │
│     ├─ Elasticsearch 7.10.2                  │
│     ├─ 3 × ess.spec-4u8g nodes               │
│     ├─ HTTPS + authentication                │
│     └─ Public access (10 Mbit/s)             │
└─────────────────────────────────────────────┘
```

CSS cluster creation takes approximately **5-10 minutes**.

After creation, get the cluster public IP:

```bash
terraform output css_public_ip
# Example output: 122.8.182.132:9200
```

### Step 5: Generate synthetic logs

```bash
cd ../scripts
python3 generate_logs.py \
  --start-date 2025-11-01 \
  --end-date 2026-05-01 \
  --logs-per-day 10000 \
  --output-dir ../output
```

This generates approximately **1.81 million** logs stored in 37 batch files under `output/`:

```
output/
├── logs_batch_0001.json   (50,000 entries)
├── logs_batch_0002.json   (50,000 entries)
├── ...
└── logs_batch_0037.json   (10,000 entries)
```

Sample log entry:

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

### Step 6: Ingest logs into CSS

```bash
python3 upload_to_es.py \
  --es-url "https://<CSS_PUBLIC_IP>:9200" \
  --username admin \
  --password "<YOUR_CSS_PASSWORD>" \
  --insecure \
  --input-dir ../output \
  --index-prefix food_delivery_logs
```

Replace `<CSS_PUBLIC_IP>` with the value from Step 4 (omit the `:9200` suffix).

Ingestion takes approximately **10-20 minutes**. Logs are stored in daily indices `food_delivery_logs-YYYY.MM.dd`.

### Step 7: Configure runtime environment

Create a `.env` file in the project root:

```bash
cd ..
cp .env.example .env
```

Edit `.env` with your CSS cluster and MAAS details:

```bash
ES_URL=https://<CSS_PUBLIC_IP>:9200
ES_USERNAME=admin
ES_PASSWORD=<YOUR_CSS_PASSWORD>
ES_INSECURE=true
ES_INDEX_PATTERN=food_delivery_logs-*
MAAS_API_KEY=<YOUR_MAAS_API_KEY>
MAAS_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/anthropic/v1
MAAS_MODEL=glm-5.1
```

### Step 8: Launch the query assistant

```bash
cd app
python3 -m streamlit run app.py
```

Your browser will open http://localhost:8501

```
┌──────────────────────────────────────────────────────────────┐
│  CSS Log Query Assistant                                      │
│                                                                │
│  ┌────────────────────────────────────────────────────────┐   │
│  │ 💬 Ask a question about food delivery logs             │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                │
│  Example questions:                                            │
│  • What were the top 5 cities by order volume in March?       │
│  • Show me the cancellation rate by country for April 2026    │
│  • What is the average delivery time in Sao Paulo?            │
│  • Which restaurants had the most orders in Lima?             │
│  • What are the peak ordering hours across all countries?     │
└──────────────────────────────────────────────────────────────┘
```

### Step 9: Start asking!

Type a natural language question in the input box. The assistant will:

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
│  │ → Streaming token by token in real time                 │ │
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
│  │ → Streaming token by token in real time                 │ │
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

## Project Structure

```
css-log-assistant/
├── .env.example                    # Environment variable template
├── .env                            # Environment variables (create, git-ignored)
├── .gitignore
│
├── app/                            # Streamlit query assistant app
│   ├── app.py                      #   Main UI - streaming thinking + answer
│   ├── config.py                   #   Config loader (auto-reads .env)
│   ├── es_mcp_client.py            #   Elasticsearch client
│   └── maas_client.py              #   MAAS GLM 5.1 client (streaming)
│
├── scripts/                        # Data generation and ingestion scripts
│   ├── generate_logs.py            #   Generate 10-country delivery logs
│   ├── upload_to_es.py             #   Bulk ingest into CSS
│   └── requirements.txt            #   Python dependencies
│
├── terraform/                      # Infrastructure as code
│   ├── providers.tf                #   Huawei Cloud provider config
│   ├── variables.tf                #   Variable definitions
│   ├── network.tf                  #   VPC + Subnet + SecurityGroup
│   ├── css.tf                      #   CSS cluster resource
│   ├── outputs.tf                  #   Outputs (cluster IP, status, etc.)
│   └── terraform.tfvars.example    #   Credential template
│
└── output/                         # Generated log files (git-ignored)
    ├── logs_batch_0001.json
    └── ...
```

---

## Teardown

After the demo, destroy Huawei Cloud resources to avoid ongoing charges:

```bash
cd terraform
terraform destroy
```

---

## FAQ

### Q: terraform apply fails with "Insufficient permissions"

The IAM user for the AK/SK needs these permissions:
- VPC Administrator
- CSS Administrator
- Security Group Administrator

Add the corresponding permission policies in the IAM console.

### Q: terraform apply fails with "Illegal period"

The CSS cluster defaults to pay-per-use (postPaid). Ensure `css.tf` does not include `charging_mode`, `period`, or `period_unit` parameters.

### Q: Streamlit error "ES_URL is required"

Ensure a `.env` file exists in the project root with `ES_URL` set. `config.py` auto-loads `../.env` (relative to the app directory).

### Q: Streamlit error "'text'"

GLM 5.1 responses contain both `thinking` and `text` content blocks. `maas_client.py` handles this by iterating to find the `type == "text"` block.

### Q: ES query error "No mapping found for [@timestamp]"

GLM 5.1 may generate `@timestamp` following Elastic Common Schema convention, but our index field is `timestamp` (no `@` prefix). The system prompt explicitly declares field names. If the error persists, mention the correct field name in your question.

### Q: How long does CSS cluster creation take?

Typically 5-10 minutes. Check status with `terraform output css_cluster_status` — `200` means available.

### Q: How to adjust log data volume?

Modify the `--logs-per-day` parameter of `generate_logs.py`. Default is 10,000/day × 181 days ≈ 1.81M entries. Reduce to 1,000/day for a quick demo.
