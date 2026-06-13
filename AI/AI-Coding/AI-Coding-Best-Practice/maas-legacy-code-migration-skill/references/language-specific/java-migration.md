# Java Migration Guide

## Version Migration Path

Recommended incremental path: Java 8 -> 11 -> 17 -> 21

### Java 8 to 11

| Breaking Change | Impact | Migration Action |
|----------------|--------|------------------|
| Removed Java EE modules (javax.* -> jakarta.*) | High | Add explicit dependencies for javax.activation, javax.xml.bind |
| `--illegal-access=deny` by default | Medium | Test with `--illegal-access=deny` flag |
| Nest-based access control | Low | Usually transparent; test inner class access |
| `var` keyword available | None (opt-in) | Consider using `var` for local variables in new code |

### Java 11 to 17

| Breaking Change | Impact | Migration Action |
|----------------|--------|------------------|
| Strong encapsulation of JDK internals | High | Remove `--add-opens` workarounds; use public APIs |
| Sealed classes available | None (opt-in) | Consider for new domain modeling |
| Pattern matching for instanceof | None (opt-in) | Simplify type-checking code |
| Records available | None (opt-in) | Consider for DTOs and value objects |

### Java 17 to 21

| Breaking Change | Impact | Migration Action |
|----------------|--------|------------------|
| Virtual threads available | None (opt-in) | Consider for I/O-heavy workloads |
| Pattern matching for switch | None (opt-in) | Simplify complex switch statements |
| Sequenced collections | None (opt-in) | Consider for ordered collection access |

## Framework Migration

### Spring to Spring Boot

1. Create Spring Boot application class with `@SpringBootApplication`
2. Move Spring XML config to Java config (`@Configuration`, `@Bean`)
3. Replace Spring MVC XML with `@RestController` and `@RequestMapping`
4. Move properties from multiple files to `application.properties`/`application.yml`
5. Replace custom datasource config with Spring Boot auto-configuration
6. Replace custom security config with Spring Security auto-configuration
7. Test each migration step

### J2EE to Jakarta EE

1. Replace `javax.*` imports with `jakarta.*` imports (batch find-and-replace)
2. Update Maven/Gradle dependencies from Java EE to Jakarta EE
3. Update deployment descriptors (web.xml, ejb-jar.xml)
4. Test with Jakarta EE compatible application server

## Dependency Analysis

- Use `mvn dependency:tree` to map dependency graph
- Use `versions-maven-plugin` to identify available updates
- Check each dependency for Java version compatibility
- Test with `-Djava.version=<target>` before actual migration

## Characterization Test Pattern (JUnit 5)

```java
@DisplayName("Characterization: OrderService.processOrder")
class OrderServiceCharacterizationTest {
    private OrderService service;

    @BeforeEach
    void setUp() {
        service = new OrderService(/* dependencies */);
    }

    @Test
    @DisplayName("Pins current behavior for standard order")
    void processOrder_standardOrder_currentBehavior() {
        Order input = new Order(12345L, List.of(
            new OrderItem("SKU-001", 2, 49.99),
            new OrderItem("SKU-002", 1, 99.99)
        ));

        OrderResult actual = service.processOrder(input);

        // Pin the exact current output
        assertThat(actual.getStatus()).isEqualTo("PROCESSED");
        assertThat(actual.getTotal()).isEqualByComparingTo(BigDecimal.valueOf(199.97));
        assertThat(actual.getItemsCount()).isEqualTo(3);
    }
}
```
