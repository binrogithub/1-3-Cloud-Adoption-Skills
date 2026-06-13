# Behavior Preservation

## What Characterization Tests Are

Characterization tests are NOT unit tests. They don't test "correct" behavior — they test **existing** behavior. For legacy code, the existing behavior IS the specification.

**Unit test**: "Given input X, the function SHOULD return Y" (tests intended behavior)
**Characterization test**: "Given input X, the function CURRENTLY returns Y" (pins existing behavior)

## How to Write Characterization Tests

### Step 1: Identify Critical Paths

From the understanding document, identify:
- Entry points (main functions, API endpoints)
- Core business logic functions
- Data transformation functions
- Integration points (database, external APIs)

### Step 2: Generate Inputs

For each critical path:
- Use representative inputs from production data (anonymized)
- Include edge cases: empty input, maximum input, boundary values
- Include error cases: invalid input, missing data

### Step 3: Record Outputs

Run the existing code with each input and record the output:

```python
# characterization_test.py
def test_process_order_characterization():
    """Pin current behavior of process_order function."""
    input_data = {"order_id": 12345, "items": [...]}
    # Record what the function currently returns
    result = process_order(input_data)
    # Assert that it still returns the same thing after migration
    assert result == {
        "status": "processed",
        "total": 199.99,
        "items_count": 3,
        # ... exact current output
    }
```

### Step 4: Run Against Original Code

All characterization tests must pass against the original (pre-migration) code. If they don't, the test is wrong, not the code.

## Characterization Test Frameworks by Language

| Language | Framework | Pattern |
|----------|-----------|---------|
| Java | JUnit 5 + AssertJ | `assertThat(actual).isEqualTo(expected)` with full object comparison |
| Python | pytest + deepdiff | `assert actual == expected` with `DeepDiff` for complex objects |
| Go | go test + cmp | `cmp.Diff(actual, expected)` with option.IgnoreUnexported() |
| COBOL | Golden-file comparison | Compare program output to saved golden file |
| .NET | xUnit + FluentAssertions | `actual.Should().BeEquivalentTo(expected)` |

## Golden-File Pattern (for COBOL and complex outputs)

1. Run original program with test input
2. Save full output to golden file: `testcases/order_12345.golden`
3. After migration, run new code with same input
4. Compare output to golden file (byte-for-byte or semantic comparison)
5. If different: investigate and either update golden file or fix migration

## Interpreting Characterization Test Failures

| Failure Type | Meaning | Action |
|-------------|---------|--------|
| Output value changed | Behavior changed | Investigate: intentional? If yes, update test. If no, fix migration. |
| New exception thrown | Error handling changed | Investigate: is the new exception more correct? |
| Missing output field | Output structure changed | Likely a bug in migration. Fix. |
| Extra output field | New field added | Investigate: intentional addition? If yes, update test. If no, remove. |

## When Characterization Tests Cannot Be Written

Some code cannot be characterized:
- Non-deterministic output (random, time-dependent)
- Side effects that cannot be isolated (writes to production database)
- Interactive code that requires user input

**Action**: Document why the path cannot be characterized. Assess risk. Get human sign-off. Add manual test procedures for these paths.

## Behavior Change Decision Framework

When a characterization test fails after migration:

1. **Is the behavior change documented in the migration plan?**
   - Yes: Update the characterization test to reflect the planned change
   - No: The change is unintentional. Revert and fix.

2. **Is the new behavior "more correct" than the old behavior?**
   - This is a trap question. "More correct" is subjective.
   - The only correct answer: if the change was planned, accept it. If not, revert it.

3. **Can the business accept this behavior change?**
   - Only a business stakeholder can answer this.
   - Document the change and get explicit sign-off.
