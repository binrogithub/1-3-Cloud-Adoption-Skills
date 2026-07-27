#!/usr/bin/env python3
"""
sql_dialect_audit.py — scan a .NET / SQL project for GaussDB adaptation anti-patterns.

Usage:
    python sql_dialect_audit.py <project-root> [--tsv]

Walks the tree (skipping bin/, obj/, .idea/, .vs/, node_modules/, LocalPackages/),
greps .cs and .sql files for known GaussDB-hostile constructs, and reports hits
by category.

Exit code 0 if no hits; 1 if any hits found. Useful as a pre-commit or CI gate.
"""
from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict

# Patterns are regex, checked per line. Each entry: (category, pattern, hint)
PATTERNS = [
    # --- Category: temp tables / sequences ---
    ("temp-table: ON COMMIT DROP (unsupported)",
     r"\bON\s+COMMIT\s+DROP\b",
     "use ON COMMIT DELETE ROWS + explicit DROP TABLE IF EXISTS"),
    ("temp-sequence: CREATE TEMPORARY SEQUENCE (unsupported)",
     r"\bCREATE\s+TEMP(?:ORARY)?\s+SEQUENCE\b",
     "use permanent SEQUENCE bracketed by DROP SEQUENCE IF EXISTS"),
    ("temp-table: SQL-Server #tempTable syntax",
     r"(?<![A-Za-z0-9_])#[A-Za-z_][A-Za-z0-9_]*",
     "use CREATE TEMP TABLE x; DROP TABLE IF EXISTS x; per GaussDB syntax"),

    # --- Category: T-SQL functions & operators ---
    ("t-sql func: ISNULL()",     r"\bISNULL\s*\(",  "rewrite to COALESCE(...)"),
    ("t-sql func: GETDATE()",    r"\bGETDATE\s*\(", "rewrite to CURRENT_TIMESTAMP or now()"),
    ("t-sql func: GETUTCDATE()", r"\bGETUTCDATE\s*\(", "rewrite to CURRENT_TIMESTAMP AT TIME ZONE 'UTC'"),
    ("t-sql func: DATEADD()",    r"\bDATEADD\s*\(",    "rewrite to x + n * INTERVAL '…'"),
    ("t-sql func: DATEDIFF()",   r"\bDATEDIFF\s*\(",   "rewrite to (b::date - a::date) or equivalent"),
    ("t-sql func: NEWID()",      r"\bNEWID\s*\(",      "rewrite to gen_random_uuid()"),
    ("t-sql func: LEN()",        r"\bLEN\s*\(",        "rewrite to char_length() or length()"),
    ("t-sql func: CHARINDEX()",  r"\bCHARINDEX\s*\(",  "rewrite to strpos()"),
    ("t-sql func: IIF()",        r"\bIIF\s*\(",        "rewrite to CASE WHEN ... THEN ... ELSE ..."),
    ("t-sql func: CONVERT(type,x,style)", r"\bCONVERT\s*\(\s*[A-Za-z0-9_]+\s*,.*?,\s*\d+\s*\)",
                                  "rewrite to to_char(x, fmt) or CAST"),

    # --- Category: sequences & identity ---
    ("t-sql: NEXT VALUE FOR seq", r"\bNEXT\s+VALUE\s+FOR\b", "rewrite to nextval('seq')"),
    ("t-sql: IDENTITY column",    r"\bIDENTITY\s*\(\s*\d+\s*,\s*\d+\s*\)", "use SERIAL/BIGSERIAL or DEFAULT nextval()"),
    ("t-sql: @@IDENTITY",         r"@@IDENTITY\b",     "use RETURNING col or lastval()"),
    ("t-sql: SCOPE_IDENTITY()",   r"\bSCOPE_IDENTITY\s*\(", "use RETURNING col"),

    # --- Category: query hints / session flags ---
    ("t-sql hint: TOP N",         r"\bSELECT\s+TOP\b|\bSELECT\s+DISTINCT\s+TOP\b", "rewrite to LIMIT N"),
    ("t-sql hint: OPTION (...)",  r"\bOPTION\s*\(\s*(MAXDOP|RECOMPILE|HASH\s+JOIN|MERGE\s+JOIN|LOOP\s+JOIN)\b",
                                  "remove the hint"),
    ("t-sql hint: WITH (NOLOCK)", r"WITH\s*\(\s*NOLOCK\s*\)", "remove; set isolation at tx level if actually needed"),
    ("t-sql flag: SET XACT_ABORT",  r"\bSET\s+XACT_ABORT\b",  "remove (GaussDB uses a different tx model)"),
    ("t-sql flag: SET NOCOUNT",     r"\bSET\s+NOCOUNT\b",     "remove"),
    ("t-sql flag: SET QUOTED_IDENTIFIER", r"\bSET\s+QUOTED_IDENTIFIER\b", "remove"),
    ("t-sql flag: SET ANSI_NULLS",  r"\bSET\s+ANSI_NULLS\b",  "remove"),

    # --- Category: identifiers / schema ---
    ("t-sql schema: dbo. prefix", r"\bdbo\.", "strip; GaussDB has no dbo schema"),
    ("t-sql ident: [bracketed]",  r"\[[A-Za-z_][A-Za-z0-9_ ]*\]", "use \"double quotes\" or bare lowercase identifiers"),
    ("t-sql datatype: NVARCHAR",  r"\bNVARCHAR\b", "use VARCHAR or TEXT"),
    ("t-sql datatype: NCHAR",     r"\bNCHAR\b",    "use CHAR"),
    ("t-sql datatype: UNIQUEIDENTIFIER", r"\bUNIQUEIDENTIFIER\b", "use UUID"),
    ("t-sql datatype: BIT",       r"\bBIT\b(?!_|OR|AND|XOR|SHIFT)", "use BOOLEAN (word-boundary caveat: may match false positives)"),
    ("t-sql datatype: SQL_VARIANT", r"\bSQL_VARIANT\b", "no equivalent — redesign"),

    # --- Category: PL/SQL constructs ---
    ("t-sql PL: DECLARE @var",    r"\bDECLARE\s+@\w+", "drop the @; variables are DECLARE var TYPE in plpgsql"),
    ("t-sql PL: EXEC proc @p=v",  r"\bEXEC(UTE)?\s+\w+\s+@\w+\s*=", "use CALL proc(p => v) or positional"),
    ("t-sql PL: BEGIN TRY",       r"\bBEGIN\s+TRY\b", "use BEGIN ... EXCEPTION WHEN OTHERS THEN ... END;"),
    ("t-sql PL: RAISERROR",       r"\bRAISERROR\b",   "use RAISE EXCEPTION '…';"),
    ("t-sql PL: @@ROWCOUNT",      r"@@ROWCOUNT\b",    "use GET DIAGNOSTICS n = ROW_COUNT;"),

    # --- Category: MERGE ... OUTPUT (MSSQL flavor) ---
    ("t-sql DML: INSERT ... OUTPUT", r"\bINSERT\b[\s\S]{0,200}?\bOUTPUT\b",
                                    "rewrite to INSERT ... RETURNING col"),
    ("t-sql DML: MERGE ... OUTPUT",  r"\bMERGE\b[\s\S]{0,800}?\bOUTPUT\b",
                                    "rewrite to INSERT ... ON CONFLICT DO UPDATE ... RETURNING ..."),

    # --- Category: .NET driver / package ---
    (".net driver: Microsoft.Data.SqlClient import",
     r"\busing\s+Microsoft\.Data\.SqlClient\b",
     "replace with GaussDB driver namespace (see connectivity-and-auth.md)"),
    (".net driver: SqlBulkCopy usage",
     r"\bnew\s+SqlBulkCopy\b|\bSqlBulkCopy\s*\(",
     "replace with BeginBinaryImport + COPY ... FROM STDIN BINARY (see bulk-load-patterns.md)"),
    (".net driver: bare 'GaussDB' package (doesn't exist on nuget.org)",
     r'<PackageReference\s+Include="GaussDB"\s+Version=',
     "use DotNetCore.GaussDB or HuaweiCloud.Driver.GaussDB"),
    (".net driver: bare 'GaussDB.EntityFrameworkCore.PostgreSQL' (doesn't exist)",
     r'<PackageReference\s+Include="GaussDB\.EntityFrameworkCore\.PostgreSQL"',
     "use DotNetCore.EntityFrameworkCore.GaussDB or HuaweiCloud.EntityFrameworkCore.GaussDB"),
    (".net driver: nested namespace 'GaussDB.GaussDBTypes' (wrong)",
     r"using\s+GaussDB\.GaussDBTypes\s*;",
     "use separate 'using GaussDB; using GaussDBTypes;'"),
    (".net driver: enum case 'GaussDBDbType.BigInt' (wrong)",
     r"GaussDBDbType\.BigInt\b",
     "correct casing is 'GaussDBDbType.Bigint'"),

    # --- Category: C# string literal hazards ---
    ("c# raw string: 4 trailing quotes after COPY",
     r'\$"""\s*COPY\s+.*?STDIN\s+BINARY""""',
     "exactly 3 trailing quotes: \"\"\""),
]

SKIP_DIRS = {"bin", "obj", ".idea", ".vs", "node_modules", "LocalPackages",
             ".git", ".vscode", "dist", "build", "target", "packages"}

EXTS = {".cs", ".sql", ".csproj", ".fsproj", ".slnx", ".sln", ".json", ".config"}


def audit(root: Path, as_tsv: bool = False) -> int:
    hits = defaultdict(list)  # category -> [(file, line_no, line_text, hint)]
    compiled = [(cat, re.compile(pat, re.IGNORECASE), hint) for cat, pat, hint in PATTERNS]

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    for cat, pat, hint in compiled:
                        if pat.search(line):
                            hits[cat].append((path, lineno, line.rstrip(), hint))
        except OSError:
            continue

    if not hits:
        print(f"[OK] no anti-patterns found under {root}")
        return 0

    if as_tsv:
        print("category\tfile\tline\tcontent\thint")
        for cat, entries in sorted(hits.items()):
            for p, n, t, h in entries:
                print(f"{cat}\t{p}\t{n}\t{t}\t{h}")
    else:
        total = sum(len(v) for v in hits.values())
        print(f"[HITS] {total} anti-pattern occurrences across {len(hits)} categories\n")
        for cat, entries in sorted(hits.items(), key=lambda kv: -len(kv[1])):
            print(f"=== {cat} ({len(entries)}) ===")
            print(f"    hint: {entries[0][3]}")
            for p, n, t, _ in entries[:10]:
                rel = p.relative_to(root) if p.is_relative_to(root) else p
                print(f"    {rel}:{n}  {t[:120]}")
            if len(entries) > 10:
                print(f"    ... and {len(entries) - 10} more")
            print()

    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("root", type=Path, help="project root to scan")
    ap.add_argument("--tsv", action="store_true", help="machine-parseable TSV output")
    args = ap.parse_args()
    if not args.root.exists():
        print(f"error: path not found: {args.root}", file=sys.stderr)
        return 2
    return audit(args.root, as_tsv=args.tsv)


if __name__ == "__main__":
    sys.exit(main())
