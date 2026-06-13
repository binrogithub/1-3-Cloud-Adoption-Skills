# .NET Migration Guide

## Framework Migration Path

Recommended path: .NET Framework (4.x) -> .NET 6 (LTS) -> .NET 8 (LTS)

### .NET Framework to .NET 6/8

| Breaking Change | Impact | Migration Action |
|----------------|--------|------------------|
| `System.Web` removed | Critical | Replace with ASP.NET Core equivalents |
| `App.config`/`Web.config` -> `appsettings.json` | High | Migrate configuration format |
| `packages.config` -> `PackageReference` | Medium | Run `nuget convert` |
| `.csproj` format change | Medium | Run `dotnet migrate` or recreate project |
| Windows-only APIs removed | High | Replace with cross-platform alternatives |
| `System.Drawing` not supported on Linux | Medium | Use `SkiaSharp` or `ImageSharp` |
| WCF client not ported | High | Use `CoreWCF` or switch to gRPC/REST |
| Windows Forms: partial support | Medium | Test on Linux; use `WinForms` compatibility shim |
| `BinaryFormatter` removed | High | Switch to `System.Text.Json` or custom serializer |

## Configuration Migration

### web.config to appsettings.json

```xml
<!-- web.config -->
<appSettings>
  <add key="MaasBaseUrl" value="https://api.modelarts-maas.com/openai/v1" />
  <add key="MaasModel" value="glm-5.1" />
</appSettings>
<connectionStrings>
  <add name="Default" connectionString="Server=...;Database=..." />
</connectionStrings>
```

```json
// appsettings.json
{
  "Maas": {
    "BaseUrl": "https://api.modelarts-maas.com/openai/v1",
    "Model": "glm-5.1"
  },
  "ConnectionStrings": {
    "Default": "Server=...;Database=..."
  }
}
```

### Configuration Reading Migration

```csharp
// Old: ConfigurationManager
var url = ConfigurationManager.AppSettings["MaasBaseUrl"];

// New: IConfiguration (dependency injection)
public class MaasService {
    private readonly string _baseUrl;
    public MaasService(IConfiguration config) {
        _baseUrl = config["Maas:BaseUrl"];
    }
}
```

## API Compatibility Analysis

| .NET Framework API | .NET 6/8 Equivalent |
|-------------------|---------------------|
| `HttpContext.Current` | Inject `IHttpContextAccessor` |
| `WebClient` | `HttpClient` |
| `Thread.Sleep` | `await Task.Delay` |
| `List<T>.ForEach` | `foreach` loop |
| `DataTable` | Strongly-typed collection or `Dapper` |
| `DataSet` | Domain models + `EF Core` |
| `XmlDocument` | `XDocument` (LINQ to XML) |
| `StreamWriter(path, true)` | `new StreamWriter(path, append: true)` |

## NuGet Package Analysis

1. Run `dotnet list package --outdated` to identify available updates
2. Run `dotnet list package --deprecated` to identify deprecated packages
3. For each package:
   - Check .NET 6/8 compatibility on nuget.org
   - Check for breaking changes in release notes
   - Test with updated package before committing

### Common Package Migrations

| Old Package | New Package | Notes |
|-------------|-------------|-------|
| `Newtonsoft.Json` | `System.Text.Json` | Built-in, better performance |
| `Dapper` (net45) | `Dapper` (net6) | Same API, new target |
| `EntityFramework` | `Microsoft.EntityFrameworkCore` | New package, similar API |
| `log4net` | `Microsoft.Extensions.Logging` | Built-in logging |
| `AutoMapper` | Map statically or use source generators | Reduce runtime reflection |
| `Moq` | `Moq` (net6) or `NSubstitute` | Same API, new target |

## Characterization Test Pattern (xUnit)

```csharp
[DisplayName("Characterization: OrderService.ProcessOrder")]
public class OrderServiceCharacterizationTests {
    private readonly OrderService _service;

    public OrderServiceCharacterizationTests() {
        _service = new OrderService(/* dependencies */);
    }

    [Fact]
    [DisplayName("Pins current behavior for standard order")]
    public void ProcessOrder_StandardOrder_CurrentBehavior() {
        var input = new Order {
            OrderId = 12345L,
            Items = new List<OrderItem> {
                new() { Sku = "SKU-001", Quantity = 2, Price = 49.99m },
                new() { Sku = "SKU-002", Quantity = 1, Price = 99.99m }
            }
        };

        var actual = _service.ProcessOrder(input);

        // Pin the exact current output
        actual.Status.Should().Be("PROCESSED");
        actual.Total.Should().Be(199.97m);
        actual.ItemsCount.Should().Be(3);
    }
}
```

## Common .NET Migration Pitfalls

- **Assembly binding redirects**: No longer needed in .NET 6+; remove from project
- **GAC (Global Assembly Cache)**: Does not exist in .NET 6+; all dependencies are local
- **IIS hosting**: ASP.NET Core uses Kestrel by default; IIS is optional via `UseIISIntegration()`
- **Windows registry**: Not available on Linux; use configuration files or environment variables
- **Windows services**: Use `System.ServiceProcess.ServiceBase` or `IHostedService` for cross-platform
