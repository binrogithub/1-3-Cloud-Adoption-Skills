// gaussdb_connect_probe.cs — minimal end-to-end probe for a GaussDB driver + server combo.
//
// Usage:
//   1. Create a throwaway folder:       mkdir /tmp/probe && cd /tmp/probe
//   2. Drop this file in:               cp gaussdb_connect_probe.cs /tmp/probe/Program.cs
//   3. Create a project file (pick one based on driver you want to test):
//
//      # DotNetCore.GaussDB (MD5 path / pwd_enc_type=0 or 1)
//      cat > Probe.csproj <<EOF
//      <Project Sdk="Microsoft.NET.Sdk">
//        <PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net9.0</TargetFramework><Nullable>enable</Nullable></PropertyGroup>
//        <ItemGroup><PackageReference Include="DotNetCore.GaussDB" Version="9.0.0" /></ItemGroup>
//      </Project>
//      EOF
//
//      # HuaweiCloud.Driver.GaussDB (SHA256 SASL path / pwd_enc_type=2 on GaussDB 505+)
//      # → also change `using GaussDB;` → `using HuaweiCloud.GaussDB;`
//      #   and `using GaussDBTypes;` → `using HuaweiCloud.GaussDBTypes;` below.
//
//   4. Set DSN and run:
//      export GAUSSDB_DSN='Host=<host>;Port=<port>;Username=<user>;Password=<pwd>;Database=<db>;'
//      dotnet run
//
// Prints one line per probe step. Exit code 0 = OK, non-zero on first failure.

using System.Data;
using GaussDB;           // ↔ HuaweiCloud.GaussDB if using the Huawei driver
using GaussDBTypes;      // ↔ HuaweiCloud.GaussDBTypes if using the Huawei driver

var dsn = Environment.GetEnvironmentVariable("GAUSSDB_DSN");
if (string.IsNullOrWhiteSpace(dsn))
{
    Console.Error.WriteLine("GAUSSDB_DSN env var not set. Example:");
    Console.Error.WriteLine("  export GAUSSDB_DSN='Host=<host>;Port=<port>;Username=<user>;Password=<pwd>;Database=<db>;'");
    return 1;
}

try
{
    //---------------------------------------------------------------------
    // 1. Connect + version + encryption info
    //---------------------------------------------------------------------
    await using var conn = new GaussDBConnection(dsn);
    await conn.OpenAsync();
    Console.WriteLine($"[OK] connect — server_version={conn.PostgreSqlVersion}");

    await using (var cmd = conn.CreateCommand())
    {
        cmd.CommandText = "SELECT version()";
        Console.WriteLine($"[OK] version() = {await cmd.ExecuteScalarAsync()}");
        cmd.CommandText = "SHOW password_encryption_type";
        Console.WriteLine($"[OK] password_encryption_type = {await cmd.ExecuteScalarAsync()}");
        cmd.CommandText = "SELECT current_user, current_database()";
        await using var r = await cmd.ExecuteReaderAsync();
        await r.ReadAsync();
        Console.WriteLine($"[OK] current_user={r.GetString(0)}, database={r.GetString(1)}");
    }

    //---------------------------------------------------------------------
    // 2. Create temp table + BINARY COPY 3 rows + read back
    //---------------------------------------------------------------------
    await using (var tx = await conn.BeginTransactionAsync())
    {
        await using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = (GaussDBTransaction)tx;
            cmd.CommandText = @"CREATE TEMPORARY TABLE probe_t (
                id BIGINT, nome TEXT, valor NUMERIC(18,2),
                ativo BOOLEAN, criado TIMESTAMP, chave UUID
            )";
            await cmd.ExecuteNonQueryAsync();
        }
        Console.WriteLine("[OK] create temp table");

        var tbl = new DataTable();
        tbl.Columns.Add("id",     typeof(long));
        tbl.Columns.Add("nome",   typeof(string));
        tbl.Columns.Add("valor",  typeof(decimal));
        tbl.Columns.Add("ativo",  typeof(bool));
        tbl.Columns.Add("criado", typeof(DateTime));
        tbl.Columns.Add("chave",  typeof(Guid));
        for (int i = 1; i <= 3; i++)
            tbl.Rows.Add((long)i, $"row{i}", 10.5m * i, i % 2 == 0, DateTime.UtcNow, Guid.NewGuid());

        using (var writer = conn.BeginBinaryImport(@"COPY probe_t FROM STDIN BINARY"))
        {
            foreach (DataRow r in tbl.Rows)
            {
                writer.StartRow();
                writer.Write((long)r["id"],     GaussDBDbType.Bigint);
                writer.Write((string)r["nome"], GaussDBDbType.Text);
                writer.Write((decimal)r["valor"], GaussDBDbType.Numeric);
                writer.Write((bool)r["ativo"],  GaussDBDbType.Boolean);
                writer.Write((DateTime)r["criado"], GaussDBDbType.Timestamp);
                writer.Write((Guid)r["chave"],  GaussDBDbType.Uuid);
            }
            writer.Complete();
        }
        Console.WriteLine("[OK] BINARY COPY — 3 rows");

        long count; decimal sum;
        await using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = (GaussDBTransaction)tx;
            cmd.CommandText = "SELECT count(*), sum(valor) FROM probe_t";
            await using var r = await cmd.ExecuteReaderAsync();
            await r.ReadAsync();
            count = r.GetInt64(0);
            sum   = r.GetDecimal(1);
        }
        Console.WriteLine($"[OK] read back — count={count}, sum(valor)={sum} (expected 3, 63.00)");

        //-----------------------------------------------------------------
        // 3. nextval block allocation pattern
        //-----------------------------------------------------------------
        await using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = (GaussDBTransaction)tx;
            cmd.CommandText = @"DROP SEQUENCE IF EXISTS probe_seq;
                                CREATE SEQUENCE probe_seq START 1000";
            await cmd.ExecuteNonQueryAsync();
        }
        long first;
        await using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = (GaussDBTransaction)tx;
            cmd.CommandText = "SELECT nextval('probe_seq') - 50 + 1";
            first = (long)await cmd.ExecuteScalarAsync();
        }
        Console.WriteLine($"[OK] nextval - 50 + 1 = {first} (expected 951)");
        await using (var cmd = conn.CreateCommand())
        {
            cmd.Transaction = (GaussDBTransaction)tx;
            cmd.CommandText = "DROP SEQUENCE IF EXISTS probe_seq";
            await cmd.ExecuteNonQueryAsync();
        }

        await tx.CommitAsync();
    }
    Console.WriteLine("[OK] commit");

    Console.WriteLine("\n[END] all probes passed");
    return 0;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"\n[FAIL] {ex.GetType().Name}: {ex.Message}");
    Console.Error.WriteLine(ex.StackTrace);
    return 1;
}
