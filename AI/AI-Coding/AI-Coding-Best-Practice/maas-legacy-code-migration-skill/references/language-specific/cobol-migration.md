# COBOL Migration Guide

## COBOL-to-Modern Translation Patterns

### Target Languages

| Target | Best For | Trade-off |
|--------|----------|-----------|
| Java | Enterprise systems, Spring ecosystem | More verbose, but enterprise-ready |
| Python | Data processing, analytics, quick prototyping | Less type-safe, but faster to write |

## COPY Book Resolution

COBOL COPY books are include files that define data structures. They must be resolved before translation:

1. **Identify all COPY statements**: `grep -r "COPY " *.cbl`
2. **Resolve COPY book paths**: Map COPY names to file paths
3. **Inline COPY books**: Replace COPY statements with actual content
4. **Extract data structures**: Map COBOL data structures to target language classes/structs

### Data Structure Mapping

| COBOL | Java | Python |
|-------|------|--------|
| `PIC 9(4)` | `int` (with range check) | `int` (with range check) |
| `PIC 9(9)V99` | `BigDecimal` | `Decimal` |
| `PIC X(20)` | `String` (max 20) | `str` (max 20) |
| `PIC X(1)` | `char` or `String` | `str` |
| `PIC S9(9)V99 COMP-3` | `BigDecimal` | `Decimal` |
| `OCCURS 10 TIMES` | `List<T>` (max 10) | `list` (max 10) |
| `REDEFINES` | `@JsonIgnore` + alternate getter | `Union` type or separate fields |
| `88 level` (condition names) | `boolean` getter methods | `bool` properties |

## CICS/DB2 Interaction Preservation

CICS and DB2 calls are embedded in COBOL and must be mapped to target language equivalents:

| COBOL CICS | Java Equivalent | Python Equivalent |
|------------|----------------|-------------------|
| `EXEC CICS READ` | JPA `entityManager.find()` | SQLAlchemy `session.query()` |
| `EXEC CICS WRITE` | JPA `entityManager.persist()` | SQLAlchemy `session.add()` |
| `EXEC CICS REWRITE` | JPA `entityManager.merge()` | SQLAlchemy `session.commit()` |
| `EXEC CICS DELETE` | JPA `entityManager.remove()` | SQLAlchemy `session.delete()` |
| `EXEC CICS SEND MAP` | REST API response | Flask/Django response |
| `EXEC CICS RECEIVE MAP` | REST API request | Flask/Django request |
| `EXEC CICS LINK` | Service method call | Function/method call |
| `EXEC CICS XCTL` | Controller redirect | Flask redirect |
| `EXEC CICS RETURN` | Method return | Function return |

| COBOL DB2 | Java Equivalent | Python Equivalent |
|-----------|----------------|-------------------|
| `EXEC SQL SELECT` | JPA `@Query` or `jdbcTemplate.query()` | SQLAlchemy `select()` |
| `EXEC SQL INSERT` | JPA `persist()` or `jdbcTemplate.update()` | SQLAlchemy `insert()` |
| `EXEC SQL UPDATE` | JPA `merge()` or `jdbcTemplate.update()` | SQLAlchemy `update()` |
| `EXEC SQL DELETE` | JPA `remove()` or `jdbcTemplate.update()` | SQLAlchemy `delete()` |
| `EXEC SQL CURSOR` | JPA `Stream` or `ResultSet` | SQLAlchemy `yield_per()` |

## Paragraph-to-Method Mapping

COBOL paragraphs (named code blocks) map to methods:

```
COBOL:
  PROCESS-ORDER.
      PERFORM VALIDATE-INPUT
      PERFORM CALCULATE-TOTAL
      PERFORM APPLY-DISCOUNT
      PERFORM WRITE-OUTPUT.

Java:
  public OrderResult processOrder(OrderInput input) {
      validateInput(input);
      BigDecimal total = calculateTotal(input);
      BigDecimal discounted = applyDiscount(total, input);
      return writeOutput(input, discounted);
  }
```

## Division Mapping

| COBOL Division | Target Language Equivalent |
|----------------|--------------------------|
| IDENTIFICATION DIVISION | Class/module docstring |
| ENVIRONMENT DIVISION | Configuration class / environment config |
| DATA DIVISION | Class fields / data classes |
| PROCEDURE DIVISION | Class methods / functions |

## Characterization Test Pattern (Golden-File)

```python
# test_order_processing_characterization.py
import json
from pathlib import Path

def test_process_order_characterization():
    """Pin current COBOL behavior using golden files."""
    # Read test input
    input_data = json.loads(Path("testcases/order_12345_input.json").read_text())

    # Run migrated Python code
    actual = process_order(input_data)

    # Compare against golden file (recorded from original COBOL)
    golden = json.loads(Path("testcases/order_12345_output.golden.json").read_text())

    assert actual == golden, f"Behavior differs from original COBOL:\n{json.dumps(actual, indent=2)}"
```

## Common COBOL Migration Pitfalls

- **Fixed-point arithmetic**: COBOL `PIC 9(9)V99` is fixed-point; floating-point in target language will produce different results. Use `BigDecimal` (Java) or `Decimal` (Python).
- **Truncation**: COBOL silently truncates overflow; target languages may throw exceptions. Add explicit truncation logic.
- **Record layout**: COBOL data is positional; target language uses named fields. Map carefully.
- **PERFORM THRU**: COBOL `PERFORM PARA-1 THRU PARA-2` executes a range of paragraphs. Map to a single method that calls the range.
- **ALTER**: COBOL `ALTER` dynamically changes paragraph targets. This has no direct equivalent; refactor to conditional logic.
