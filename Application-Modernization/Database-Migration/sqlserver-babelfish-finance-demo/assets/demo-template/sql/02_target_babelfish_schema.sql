IF DB_ID(N'FinanceDemo') IS NOT NULL DROP DATABASE FinanceDemo
GO

CREATE DATABASE FinanceDemo
GO

USE FinanceDemo
GO

CREATE TABLE dbo.Customers (
    CustomerID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    CustomerName NVARCHAR(120) NOT NULL,
    Segment VARCHAR(20) NOT NULL,
    RiskRating VARCHAR(12) NOT NULL,
    OnboardDate DATE NOT NULL,
    Status VARCHAR(12) NOT NULL
)
GO

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
)
GO

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
)
GO

CREATE TABLE dbo.RiskAlerts (
    AlertID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    PaymentID INT NOT NULL,
    AlertType VARCHAR(30) NOT NULL,
    Severity VARCHAR(10) NOT NULL,
    AlertStatus VARCHAR(20) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT FK_RiskAlerts_Payments FOREIGN KEY (PaymentID) REFERENCES dbo.Payments(PaymentID)
)
GO

CREATE VIEW dbo.v_customer_exposure AS
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
GROUP BY c.CustomerID, c.CustomerName, c.Segment, c.RiskRating
GO

CREATE VIEW dbo.v_daily_payment_liquidity AS
SELECT
    CAST(p.PaymentTime AS DATE) AS BusinessDate,
    a.CurrencyCode,
    COUNT(p.PaymentID) AS PaymentCount,
    SUM(p.Amount) AS TotalDebitAmount,
    SUM(CASE WHEN p.Amount >= 500000 THEN 1 ELSE 0 END) AS HighValuePaymentCount
FROM dbo.Payments AS p
JOIN dbo.Accounts AS a ON a.AccountID = p.DebitAccountID
GROUP BY CAST(p.PaymentTime AS DATE), a.CurrencyCode
GO

CREATE PROCEDURE dbo.usp_customer_exposure @RiskRating VARCHAR(12) = NULL AS
BEGIN
    SET NOCOUNT ON

    SELECT CustomerID, CustomerName, Segment, RiskRating, AccountCount, TotalBalance, OutgoingAmount, OpenAlertCount
    FROM dbo.v_customer_exposure
    WHERE @RiskRating IS NULL OR RiskRating = @RiskRating
    ORDER BY OpenAlertCount DESC, OutgoingAmount DESC
END
GO

CREATE PROCEDURE dbo.usp_daily_payment_liquidity @BusinessDate DATE = NULL AS
BEGIN
    SET NOCOUNT ON

    SELECT BusinessDate, CurrencyCode, PaymentCount, TotalDebitAmount, HighValuePaymentCount
    FROM dbo.v_daily_payment_liquidity
    WHERE @BusinessDate IS NULL OR BusinessDate = @BusinessDate
    ORDER BY BusinessDate, CurrencyCode
END
GO
