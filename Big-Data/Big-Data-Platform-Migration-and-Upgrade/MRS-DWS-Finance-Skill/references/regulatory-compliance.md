# Regulatory Compliance

## Mexico Financial Regulatory Framework

### CNBV (Comisión Nacional Bancaria y de Valores)

**Circular 15/2020** establishes transaction limits and reporting requirements for financial institutions in Mexico.

#### Transaction Limits

| Limit Type | Individual (MXN) | Business (MXN) | Regulatory Basis |
|------------|------------------|----------------|------------------|
| Daily Limit | 50,000 | 500,000 | UDIS-based threshold |
| Monthly Limit | 500,000 | 5,000,000 | AML monitoring |
| Suspicious Threshold | 15,000 | 15,000 | Mandatory reporting |
| Large Transaction | 100,000 | 100,000 | Enhanced due diligence |

#### Implementation in DWS

```sql
-- Check individual daily limit
SELECT COUNT(*) AS violations
FROM dw.fact_transaction f
JOIN dw.dim_customer c ON f.customer_key = c.customer_key
WHERE f.amount > 50000
  AND c.kyc_status IN ('LEVEL_1', 'LEVEL_2');

-- Check suspicious transaction reporting
SELECT COUNT(*) AS reportable
FROM dw.fact_transaction
WHERE amount >= 15000 AND is_fraud = 1;
```

---

### Banxico (Bank of Mexico) SPEI Regulations

**SPEI** (Sistema de Pagos Electrónicos Interbancarios) is Mexico's real-time payment system operated by Banxico.

#### SPEI Types and Limits

| SPEI Type | Limit (MXN) | Settlement Time | Use Case |
|-----------|-------------|-----------------|----------|
| **SPEI Instantáneo** | 8,000 | < 30 seconds | Real-time payments |
| **SPEI Regular** | 500,000 | Same day | Standard transfers |
| **SPEI Business (SPID)** | 5,000,000 | Same day | Corporate transfers |

#### Implementation in MRS Spark

```python
# SPEI routing logic
def route_spei(amount, customer_type):
    if amount <= 8000:
        return "SPEI_INSTANTANEO"
    elif amount <= 500000:
        return "SPEI_REGULAR"
    elif customer_type == "CORPORATE" and amount <= 5000000:
        return "SPID"
    else:
        return "REJECTED"  # Exceeds all limits
```

#### Implementation in DWS

```sql
-- Validate SPEI limits
SELECT
    payment_method,
    COUNT(*) AS total,
    SUM(CASE
        WHEN payment_method = 'SPEI' AND amount > 500000 THEN 1
        WHEN payment_method = 'SPID' AND amount > 5000000 THEN 1
        ELSE 0
    END) AS violations
FROM dw.fact_transaction
GROUP BY payment_method;
```

---

### Ley Fintech (AML/KYC Requirements)

Mexico's **Ley Fintech** (Fintech Law) defines three KYC levels with corresponding transaction limits.

#### KYC Levels

| KYC Level | Transaction Limit (MXN) | Requirements | Typical Use |
|-----------|------------------------|--------------|-------------|
| **Level 1** | ≤ 7,500 | Basic identification (name, DOB) | Micro-transactions |
| **Level 2** | ≤ 30,000 | Enhanced verification (ID, address) | Standard banking |
| **Level 3** | Unlimited | Full due diligence (income, source) | All transactions |

#### Implementation in DWS

```sql
-- KYC level compliance check
SELECT
    kyc_level,
    COUNT(*) AS total_transactions,
    SUM(CASE
        WHEN kyc_level = 'LEVEL_1' AND amount > 7500 THEN 1
        WHEN kyc_level = 'LEVEL_2' AND amount > 30000 THEN 1
        ELSE 0
    END) AS violations
FROM dw.fact_transaction
WHERE kyc_level IN ('LEVEL_1', 'LEVEL_2')
GROUP BY kyc_level;
```

---

### FATF (Financial Action Task Force) Recommendations

Mexico is a FATF member and must implement the 40 Recommendations.

#### Key Recommendations for OpenBank

| Recommendation | Requirement | Implementation |
|----------------|-------------|----------------|
| R10 - Customer Due Diligence | Identify and verify customers | KYC Level 1/2/3 |
| R11 - Record Keeping | Maintain records for 5 years | DWS RPT layer retention |
| R12 - Politically Exposed Persons | Enhanced due diligence for PEPs | PEP flag in dim_customer |
| R15 - New Technologies | Assess ML/TF risks of new technologies | Fintech risk assessment |
| R16 - Wire Transfers | Originator/beneficiary information | Cross-border monitoring |
| R20 - Suspicious Transactions | Report to FIU | Automated SAR generation |
| R24 - Beneficial Ownership | Identify ultimate beneficial owners | UBO tracking |

---

## Mandatory Reporting Thresholds

| Event Type | Threshold | Reporting Timeline | Authority |
|------------|-----------|-------------------|-----------|
| Suspicious Transaction | ≥ 15,000 MXN | 24 hours | CNBV / FIU |
| Large Cash Transaction | ≥ 100,000 MXN | 48 hours | CNBV |
| Cross-Border Transfer | ≥ 10,000 USD (~170,000 MXN) | 72 hours | Banxico |
| Structuring Pattern | Multiple < 15,000 MXN | 24 hours | FIU |
| PEP Transaction | Any amount | 48 hours | CNBV |

---

## Compliance Check Automation

### Automated Checks (DWS Scheduled Jobs)

1. **Every 15 minutes**: Real-time transaction limit monitoring
2. **Hourly**: KYC level violation detection
3. **Daily (00:00)**: Full CNBV compliance sweep
4. **Daily (01:00)**: AML/KYC compliance report
5. **Daily (02:00)**: Structuring pattern detection
6. **Weekly**: FATF recommendation review

### Alert Escalation

| Severity | Condition | Action | Timeline |
|----------|-----------|--------|----------|
| CRITICAL | SAR filing required | Auto-file + notify compliance | 1 hour |
| HIGH | Limit violation detected | Block transaction + notify | 4 hours |
| MEDIUM | Structuring pattern detected | Flag for review | 24 hours |
| LOW | Minor compliance gap | Log for audit | 72 hours |
