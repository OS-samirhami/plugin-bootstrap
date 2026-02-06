# Code Changes - Conditional Job Trigger Plugin

## Summary
Updated plugin to support **any data type** in expressions (string, number, map, collection, etc.) while maintaining backward compatibility.

---

## 🔑 Key Changes

### 1. **Added New Property: `valueExpression`**

**Before:**
```groovy
@PluginProperty(title = "Condition Expression", ...)
String conditionExpression
```

**After:**
```groovy
@PluginProperty(title = "Value Expression", ...)
String valueExpression

@PluginProperty(title = "Condition Expression (Legacy)", ...) 
String conditionExpression  // Kept for backward compatibility

@PluginProperty(title = "Match Value", ...)
String matchValue  // New: optional exact matching
```

---

### 2. **Updated `executeStep()` Method**

**Key Changes:**

```groovy
// OLD: Boolean evaluation only
boolean conditionResult = evaluateCondition(conditionExpression, context, logger)
if (!conditionResult) { skip }

// NEW: Multi-type evaluation with backward compatibility
String expression = valueExpression ?: conditionExpression  // ← Fallback for compatibility
def evaluationResult = evaluateExpression(expression, context, logger)
Object rawValue = evaluationResult.value
String valueType = evaluationResult.type

logger.log(3, "Evaluated value: ${rawValue} (type: ${valueType})")  // ← Type logging

boolean shouldTrigger = shouldTriggerJob(rawValue, matchValue, logger)
if (!shouldTrigger) { skip }
```

**Added to output context:**
```groovy
context.getOutputContext().addOutput("conditional-trigger", "evaluated-value", rawValue?.toString())
context.getOutputContext().addOutput("conditional-trigger", "value-type", valueType)
```

---

### 3. **Replaced `evaluateCondition()` with `evaluateExpression()`**

**OLD Method (Boolean only):**
```groovy
private boolean evaluateCondition(String expression, ...) {
    String normalized = expanded.toLowerCase()
    if (normalized == "true") return true
    if (normalized == "false") return false
    // JavaScript eval → return Boolean
}
```

**NEW Method (Any type):**
```groovy
private Map evaluateExpression(String expression, PluginStepContext context, ExecutionListener logger) {
    String expanded = context.getExecutionContext().getDataContext().replaceDataReferences(expression)
    
    // If simple value (no operators), parse directly
    if (no operators detected) {
        Object value = parseValue(expanded)  // ← Parses to bool, number, or string
        return [value: value, type: getValueType(value)]
    }
    
    // Complex expression - JavaScript evaluation
    Object result = engine.eval(expanded)
    return [value: result, type: getValueType(result)]  // ← Returns raw Object
}
```

---

### 4. **Added `shouldTriggerJob()` Method (NEW)**

```groovy
private boolean shouldTriggerJob(Object value, String matchValue, ExecutionListener logger) {
    // Exact match mode
    if (matchValue != null && !matchValue.trim().isEmpty()) {
        return value?.toString().equals(matchValue)
    }
    
    // Type-based decision rules
    if (value == null) return false                    // null → skip
    if (value instanceof Boolean) return (Boolean) value
    if (value instanceof String) return !value.trim().isEmpty()
    if (value instanceof Number) return value.doubleValue() != 0.0
    if (value instanceof Collection) return !value.isEmpty()
    if (value instanceof Map) return !value.isEmpty()
    
    return true  // Default: other objects trigger
}
```

---

### 5. **Added Helper Methods (NEW)**

```groovy
private Object parseValue(String value) {
    // Try boolean
    if (value.equalsIgnoreCase("true")) return true
    if (value.equalsIgnoreCase("false")) return false
    
    // Try number
    if (value.contains(".")) return Double.parseDouble(value)
    return Long.parseLong(value)
    
    // Fallback to string
    return value
}

private String getValueType(Object value) {
    if (value == null) return "null"
    if (value instanceof Boolean) return "boolean"
    if (value instanceof Number) return "number"
    if (value instanceof String) return "string"
    if (value instanceof Map) return "map"
    if (value instanceof Collection) return "collection"
    return value.getClass().getSimpleName()
}
```

---

## 📋 **Updated Test Cases**

**New tests added:**

```groovy
def "evaluateExpression returns string type"()
def "evaluateExpression returns number type"()  
def "evaluateExpression returns null for empty"()
def "shouldTriggerJob with non-empty string returns true"()
def "shouldTriggerJob with zero returns false"()
def "shouldTriggerJob with matchValue does exact comparison"()
def "backward compatibility with conditionExpression"()
```

---

## 🎯 **Behavioral Differences**

| Scenario | OLD Behavior | NEW Behavior |
|----------|--------------|--------------|
| Expression: `"production"` | Parses as string, checks if == "true" → false | Non-empty string → **triggers** ✅ |
| Expression: `"42"` | Tries to parse as bool → false | Parses as number 42 → **triggers** ✅ |
| Expression: `"0"` | Tries to parse as bool → false | Parses as number 0 → **skips** ✅ |
| Expression: `""` | Empty → defaults to false | null value → **skips** ✅ |
| With `matchValue: "prod"` | Not supported | Exact match only → **new feature** ✅ |
| `conditionExpression: "true"` | Works | Still works (backward compat) ✅ |

---

## ✅ **Validation Checklist**

- [x] Renamed logic from `conditionExpression` to `valueExpression`
- [x] Kept `conditionExpression` for backward compatibility
- [x] Evaluate expression and capture raw result as Object
- [x] Decision rule: null → skip
- [x] Decision rule: Boolean → true = trigger, false = skip
- [x] Decision rule: String → non-empty = trigger
- [x] Decision rule: Number → non-zero = trigger
- [x] Decision rule: Collection/Map → non-empty = trigger
- [x] Optional `matchValue` for exact matching
- [x] Log evaluated value and type for debugging
- [x] Access execution context for variables
- [x] Access job options via data context
- [x] Access shared step data via data context
- [x] Preserve ExecutionService usage
- [x] Preserve waitForCompletion logic
- [x] Preserve error handling
- [x] Preserve auth context
- [x] No REST API calls
- [x] Plugin type unchanged (WorkflowStep)
- [x] No new dependencies
- [x] Boolean behavior not broken

---

## 🚀 **Ready to Deploy**

The updated code is ready to be redeployed using the same deployment script:

```bash
./deploy-final.sh
```

Or deploy just the updated Java file to the Rundeck server and rebuild.

---

**All requirements met!** ✅
