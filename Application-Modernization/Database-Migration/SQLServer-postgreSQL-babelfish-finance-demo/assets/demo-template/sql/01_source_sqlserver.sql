IF DB_ID(N'FinanceDemo') IS NOT NULL
BEGIN
    ALTER DATABASE FinanceDemo SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
    DROP DATABASE FinanceDemo;
END
GO

CREATE DATABASE FinanceDemo;
GO

USE FinanceDemo;
GO

CREATE TABLE dbo.Customers (
    CustomerID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    CustomerName NVARCHAR(120) NOT NULL,
    Segment VARCHAR(20) NOT NULL,
    RiskRating VARCHAR(12) NOT NULL,
    OnboardDate DATE NOT NULL,
    Status VARCHAR(12) NOT NULL
);

CREATE TABLE dbo.Accounts (
    AccountID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    CustomerID INT NOT NULL,
    AccountNo VARCHAR(24) NOT NULL,
    ProductCode VARCHAR(20) NOT NULL,
    CurrencyCode CHAR(3) NOT NULL,
    OpenDate DATE NOT NULL,
    Balance DECIMAL(18,2) NOT NULL,
    Status VARCHAR(12) NOT NULL,
    CONSTRAINT UQ_Accounts_AccountNo UNIQUE (AccountNo),
    CONSTRAINT FK_Accounts_Customers FOREIGN KEY (CustomerID) REFERENCES dbo.Customers(CustomerID)
);

CREATE TABLE dbo.Payments (
    PaymentID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    DebitAccountID INT NOT NULL,
    CreditAccountID INT NOT NULL,
    PaymentTime DATETIME2 NOT NULL,
    Amount DECIMAL(18,2) NOT NULL,
    Channel VARCHAR(20) NOT NULL,
    PaymentStatus VARCHAR(20) NOT NULL,
    ReferenceNo VARCHAR(32) NOT NULL,
    CONSTRAINT UQ_Payments_ReferenceNo UNIQUE (ReferenceNo),
    CONSTRAINT FK_Payments_DebitAccount FOREIGN KEY (DebitAccountID) REFERENCES dbo.Accounts(AccountID),
    CONSTRAINT FK_Payments_CreditAccount FOREIGN KEY (CreditAccountID) REFERENCES dbo.Accounts(AccountID)
);

CREATE TABLE dbo.RiskAlerts (
    AlertID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    PaymentID INT NOT NULL,
    AlertType VARCHAR(30) NOT NULL,
    Severity VARCHAR(10) NOT NULL,
    AlertStatus VARCHAR(20) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_RiskAlerts_Payments FOREIGN KEY (PaymentID) REFERENCES dbo.Payments(PaymentID)
);
GO

INSERT INTO dbo.Customers (CustomerName, Segment, RiskRating, OnboardDate, Status) VALUES
(N'Hua An Manufacturing', 'Corporate', 'Medium', '2021-03-12', 'Active'),
(N'Li Wei', 'Retail', 'Low', '2022-08-19', 'Active'),
(N'Blue Harbor Trading', 'Corporate', 'High', '2020-11-05', 'Review'),
(N'Chen Yu', 'Private', 'Medium', '2023-01-21', 'Active');

INSERT INTO dbo.Accounts (CustomerID, AccountNo, ProductCode, CurrencyCode, OpenDate, Balance, Status) VALUES
(1, '62290000010001', 'CORP_CURRENT', 'CNY', '2021-03-12', 5800000.00, 'Open'),
(1, '62290000010002', 'CORP_USD', 'USD', '2021-04-02', 260000.00, 'Open'),
(2, '62290000020001', 'RETAIL_SAVING', 'CNY', '2022-08-19', 86000.50, 'Open'),
(3, '62290000030001', 'TRADE_SETTLE', 'CNY', '2020-11-05', 1250000.00, 'Open'),
(4, '62290000040001', 'PRIVATE_BANK', 'CNY', '2023-01-21', 760000.00, 'Open');

INSERT INTO dbo.Payments (DebitAccountID, CreditAccountID, PaymentTime, Amount, Channel, PaymentStatus, ReferenceNo) VALUES
(1, 4, '2026-04-26T09:15:03', 250000.00, 'CorporateOnline', 'Settled', 'PAY202604260001'),
(4, 3, '2026-04-26T10:44:18', 86000.00, 'Counter', 'Settled', 'PAY202604260002'),
(3, 1, '2026-04-27T14:02:35', 680000.00, 'SWIFT', 'Settled', 'PAY202604270001'),
(5, 2, '2026-04-27T16:33:20', 120000.00, 'Mobile', 'PendingReview', 'PAY202604270002'),
(1, 3, '2026-04-28T11:08:59', 980000.00, 'CorporateOnline', 'Settled', 'PAY202604280001');

INSERT INTO dbo.RiskAlerts (PaymentID, AlertType, Severity, AlertStatus, CreatedAt) VALUES
(3, 'HighValueTransfer', 'High', 'Open', '2026-04-27T14:03:10'),
(4, 'CustomerRiskMismatch', 'Medium', 'Investigating', '2026-04-27T16:34:02'),
(5, 'HighValueTransfer', 'High', 'Open', '2026-04-28T11:09:21');
GO

CREATE OR ALTER VIEW dbo.v_customer_exposure AS
SELECT
    c.CustomerID,
    c.CustomerName,
    c.Segment,
    c.RiskRating,
    COUNT(DISTINCT a.AccountID) AS AccountCount,
    SUM(a.Balance) AS TotalBalance,
    SUM(CASE WHEN p.PaymentID IS NULL THEN 0 ELSE p.Amount END) AS OutgoingAmount,
    COUNT(DISTINCT r.AlertID) AS OpenAlertCount
FROM dbo.Customers AS c
JOIN dbo.Accounts AS a ON a.CustomerID = c.CustomerID
LEFT JOIN dbo.Payments AS p ON p.DebitAccountID = a.AccountID
LEFT JOIN dbo.RiskAlerts AS r ON r.PaymentID = p.PaymentID AND r.AlertStatus <> 'Closed'
GROUP BY c.CustomerID, c.CustomerName, c.Segment, c.RiskRating;
GO

CREATE OR ALTER VIEW dbo.v_daily_payment_liquidity AS
SELECT
    CAST(p.PaymentTime AS DATE) AS BusinessDate,
    a.CurrencyCode,
    COUNT(p.PaymentID) AS PaymentCount,
    SUM(p.Amount) AS TotalDebitAmount,
    SUM(CASE WHEN p.Amount >= 500000 THEN 1 ELSE 0 END) AS HighValuePaymentCount
FROM dbo.Payments AS p
JOIN dbo.Accounts AS a ON a.AccountID = p.DebitAccountID
GROUP BY CAST(p.PaymentTime AS DATE), a.CurrencyCode;
GO

CREATE OR ALTER PROCEDURE dbo.usp_customer_exposure @RiskRating VARCHAR(12) = NULL AS
BEGIN
    SET NOCOUNT ON;

    SELECT CustomerID, CustomerName, Segment, RiskRating, AccountCount, TotalBalance, OutgoingAmount, OpenAlertCount
    FROM dbo.v_customer_exposure
    WHERE @RiskRating IS NULL OR RiskRating = @RiskRating
    ORDER BY OpenAlertCount DESC, OutgoingAmount DESC;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_daily_payment_liquidity @BusinessDate DATE = NULL AS
BEGIN
    SET NOCOUNT ON;

    SELECT BusinessDate, CurrencyCode, PaymentCount, TotalDebitAmount, HighValuePaymentCount
    FROM dbo.v_daily_payment_liquidity
    WHERE @BusinessDate IS NULL OR BusinessDate = @BusinessDate
    ORDER BY BusinessDate, CurrencyCode;
END;
GO
