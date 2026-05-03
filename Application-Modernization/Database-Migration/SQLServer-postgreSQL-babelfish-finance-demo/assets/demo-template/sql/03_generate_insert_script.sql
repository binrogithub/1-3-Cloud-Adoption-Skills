SET NOCOUNT ON;

SELECT 'USE FinanceDemo';
SELECT 'GO';

SELECT 'SET IDENTITY_INSERT dbo.Customers ON';
SELECT 'GO';

SELECT
    'INSERT INTO dbo.Customers (CustomerID, CustomerName, Segment, RiskRating, OnboardDate, Status) VALUES ('
    + CAST(CustomerID AS VARCHAR(20))
    + ', N''' + REPLACE(CustomerName, '''', '''''') + ''''
    + ', ''' + REPLACE(Segment, '''', '''''') + ''''
    + ', ''' + REPLACE(RiskRating, '''', '''''') + ''''
    + ', ''' + CONVERT(VARCHAR(10), OnboardDate, 23) + ''''
    + ', ''' + REPLACE(Status, '''', '''''') + ''')'
FROM dbo.Customers
ORDER BY CustomerID;

SELECT 'GO';
SELECT 'SET IDENTITY_INSERT dbo.Customers OFF';
SELECT 'GO';

SELECT 'SET IDENTITY_INSERT dbo.Accounts ON';
SELECT 'GO';

SELECT
    'INSERT INTO dbo.Accounts (AccountID, CustomerID, AccountNo, ProductCode, CurrencyCode, OpenDate, Balance, Status) VALUES ('
    + CAST(AccountID AS VARCHAR(20))
    + ', ' + CAST(CustomerID AS VARCHAR(20))
    + ', ''' + REPLACE(AccountNo, '''', '''''') + ''''
    + ', ''' + REPLACE(ProductCode, '''', '''''') + ''''
    + ', ''' + REPLACE(CurrencyCode, '''', '''''') + ''''
    + ', ''' + CONVERT(VARCHAR(10), OpenDate, 23) + ''''
    + ', ' + CAST(Balance AS VARCHAR(30))
    + ', ''' + REPLACE(Status, '''', '''''') + ''')'
FROM dbo.Accounts
ORDER BY AccountID;

SELECT 'GO';
SELECT 'SET IDENTITY_INSERT dbo.Accounts OFF';
SELECT 'GO';

SELECT 'SET IDENTITY_INSERT dbo.Payments ON';
SELECT 'GO';

SELECT
    'INSERT INTO dbo.Payments (PaymentID, DebitAccountID, CreditAccountID, PaymentTime, Amount, Channel, PaymentStatus, ReferenceNo) VALUES ('
    + CAST(PaymentID AS VARCHAR(20))
    + ', ' + CAST(DebitAccountID AS VARCHAR(20))
    + ', ' + CAST(CreditAccountID AS VARCHAR(20))
    + ', ''' + CONVERT(VARCHAR(30), PaymentTime, 126) + ''''
    + ', ' + CAST(Amount AS VARCHAR(30))
    + ', ''' + REPLACE(Channel, '''', '''''') + ''''
    + ', ''' + REPLACE(PaymentStatus, '''', '''''') + ''''
    + ', ''' + REPLACE(ReferenceNo, '''', '''''') + ''')'
FROM dbo.Payments
ORDER BY PaymentID;

SELECT 'GO';
SELECT 'SET IDENTITY_INSERT dbo.Payments OFF';
SELECT 'GO';

SELECT 'SET IDENTITY_INSERT dbo.RiskAlerts ON';
SELECT 'GO';

SELECT
    'INSERT INTO dbo.RiskAlerts (AlertID, PaymentID, AlertType, Severity, AlertStatus, CreatedAt) VALUES ('
    + CAST(AlertID AS VARCHAR(20))
    + ', ' + CAST(PaymentID AS VARCHAR(20))
    + ', ''' + REPLACE(AlertType, '''', '''''') + ''''
    + ', ''' + REPLACE(Severity, '''', '''''') + ''''
    + ', ''' + REPLACE(AlertStatus, '''', '''''') + ''''
    + ', ''' + CONVERT(VARCHAR(30), CreatedAt, 126) + ''')'
FROM dbo.RiskAlerts
ORDER BY AlertID;

SELECT 'GO';
SELECT 'SET IDENTITY_INSERT dbo.RiskAlerts OFF';
SELECT 'GO';
