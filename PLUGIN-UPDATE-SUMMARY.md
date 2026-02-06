# Plugin Update: Multi-Type Value Expression Support

## ✅ Changes Applied

The Conditional Job Trigger plugin has been updated to support **any data type** in expressions, not just booleans.

---

## 🔄 **What Changed**

### 1. **New Property: `valueExpression`**

```groovy
@PluginProperty(
    title = "Value Expression",
    description = """Expression to evaluate. Supports any data type:
- Boolean: true/false
- String: '${option.environment}' (non-empty triggers)
- Number: '${data.count}' (non-zero triggers)
- Variables: '${job.status}', '${option.deploy}'
- Complex: '${data.value}' == 'production'
...
```

**Backward Compatibility:** The old `conditionExpression` property is kept but deprecated. If `valueExpression` is not set, it falls back to `conditionExpression`.

### 2. **New Property: `matchValue` (Optional)**

```groovy
@PluginProperty(
    title = "Match Value",
    description = "Optional: If set, job triggers ONLY when expression result equals this value",
    required = false
)
String matchValue
```

Allows exact string matching: only trigger when result equals the specified value.

---

## 🎯 **New Evaluation Logic**

### **Method: `evaluateExpression()`**

Replaces the old `evaluateCondition()` method.

**Returns:** `[value: Object, type: String]`

```groovy
private Map evaluateExpression(String expression, PluginStepContext context, ExecutionListener logger) {
    // 1. Expand variables from context
    String expanded = context.getExecutionContext().getDataContext().replaceDataReferences(expression)
    
    // 2. Check if it's a simple value (no operators)
    if (no operators) {
        // Parse as appropriate type (boolean, number, or string)
        Object value = parseValue(expanded)
        return [value: value, type: getValueType(value)]
    }
    
    // 3. Complex expression - use JavaScript engine
    Object result = engine.eval(expanded)
    return [value: result, type: getValueType(result)]
}
```

### **Method: `shouldTriggerJob()`**

Implements the decision rules for all data types.

```groovy
private boolean shouldTriggerJob(Object value, String matchValue, ExecutionListener logger) {
    // Rule 1: If matchValue is set → exact string comparison
    if (matchValue != null) {
        return value?.toString().equals(matchValue)
    }
    
    // Rule 2: null → skip
    if (value == null) return false
    
    // Rule 3: Boolean → use directly
    if (value instanceof Boolean) return (Boolean) value
    
    // Rule 4: String → non-empty triggers
    if (value instanceof String) return !value.trim().isEmpty()
    
    // Rule 5: Number → non-zero triggers
    if (value instanceof Number) return value.doubleValue() != 0.0
    
    // Rule 6: Collection → non-empty triggers
    if (value instanceof Collection) return !value.isEmpty()
    
    // Rule 7: Map → non-empty triggers  
    if (value instanceof Map) return !value.isEmpty()
    
    // Default: any other object triggers
    return true
}
```

### **Helper Methods:**

```groovy
// Parse string to appropriate type (boolean, number, or string)
private Object parseValue(String value)

// Get type name for logging
private String getValueType(Object value)
```

---

## 📊 **Decision Rules Summary**

| Value Type | Condition to Trigger | Examples |
|------------|---------------------|----------|
| **null** | Never triggers | Empty expression → skip |
| **Boolean** | `true` triggers | `true` → trigger, `false` → skip |
| **String** | Non-empty triggers | `"prod"` → trigger, `""` → skip |
| **Number** | Non-zero triggers | `5` → trigger, `0` → skip |
| **Collection** | Non-empty triggers | `[1,2,3]` → trigger, `[]` → skip |
| **Map** | Non-empty triggers | `{a:1}` → trigger, `{}` → skip |
| **With matchValue** | Exact match only | value="prod", match="prod" → trigger |

---

## 🔍 **Enhanced Logging**

New debug output includes:

```groovy
logger.log(3, "[Conditional Job Trigger] Evaluated value: ${rawValue} (type: ${valueType})")
logger.log(3, "[Conditional Job Trigger] String value: '${value}' → ${nonEmpty ? 'trigger' : 'skip'}")
logger.log(3, "[Conditional Job Trigger] Number value: ${value} → ${nonZero ? 'trigger' : 'skip'}")
// etc for each type
```

---

## 📤 **Enhanced Output Context**

Added to output context:

```groovy
context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "evaluated-value", rawValue?.toString() ?: "null")
context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "value-type", valueType)
```

**Usage in next steps:**
```bash
${conditional-trigger.evaluated-value}  # The actual evaluated value
${conditional-trigger.value-type}       # Type: boolean, string, number, etc.
${conditional-trigger.triggered}        # true if job was triggered
${conditional-trigger.skipped}          # true if skipped
```

---

## 💡 **Use Case Examples**

### **1. Option Value Check**
```yaml
valueExpression: "${option.environment}"
# "prod" → triggers
# "" → skips
```

### **2. Exact Match**
```yaml
valueExpression: "${option.environment}"
matchValue: "production"
# Only triggers when option exactly equals "production"
```

### **3. Numeric Threshold (via expression)**
```yaml
valueExpression: "${data.error-count} > 5"
# Evaluates to boolean, triggers if true
```

### **4. Data Availability Check**
```yaml
valueExpression: "${data.deployment-id}"
# Triggers if deployment-id is present and non-empty
```

### **5. Collection Check**
```yaml
valueExpression: "${data.failed-hosts}"
# Triggers if failed-hosts list is non-empty
```

### **6. Backward Compatible**
```yaml
conditionExpression: "true"
# Still works! Falls back to old property
```

---

## 🔧 **Code Changes Summary**

### **Files Modified:**
1. ✅ `ConditionalJobTrigger.groovy` - Main plugin logic
   - Added `valueExpression` property
   - Added `matchValue` property  
   - Kept `conditionExpression` for backward compatibility
   - Replaced `evaluateCondition()` with `evaluateExpression()`
   - Added `shouldTriggerJob()` with multi-type logic
   - Added `parseValue()` helper
   - Added `getValueType()` helper
   - Enhanced logging with type information
   - Added evaluated value to output context

2. ✅ `ConditionalJobTriggerSpec.groovy` - Unit tests
   - Updated tests for new evaluation logic
   - Added tests for each data type
   - Added matchValue tests
   - Added backward compatibility test

### **Files NOT Changed:**
- ✅ `PluginFailureReason.groovy` - No changes needed
- ✅ `build.gradle` - No new dependencies required
- ✅ Plugin type remains WorkflowStep
- ✅ No REST API calls introduced
- ✅ ExecutionService usage preserved
- ✅ Auth context handling unchanged

---

## 🎓 **Key Implementation Details**

### **Variable Expansion Context:**
```groovy
String expanded = context.getExecutionContext().getDataContext().replaceDataReferences(expression)
```

**Available contexts:**
- `${option.*}` - Job options
- `${data.*}` - Shared step data
- `${job.*}` - Job context
- `${node.*}` - Node data (if applicable)

### **Type Detection:**
```groovy
if (!expression.contains("==") && !expression.contains("&&") ...) {
    // Simple value - parse directly
} else {
    // Complex expression - use JavaScript engine
}
```

### **Backward Compatibility:**
```groovy
String expression = valueExpression ?: conditionExpression
```

Uses Groovy's Elvis operator - if `valueExpression` is null/empty, falls back to `conditionExpression`.

---

## ✅ **Testing the Updates**

### **Test 1: String Value**
```yaml
valueExpression: "${option.environment}"
# If option.environment = "production" → triggers
# If option.environment = "" → skips
```

### **Test 2: Numeric Value**
```yaml
valueExpression: "${data.retry-count}"
# If retry-count = 3 → triggers
# If retry-count = 0 → skips
```

### **Test 3: Exact Match**
```yaml
valueExpression: "${option.deploy-target}"
matchValue: "production"
# Only triggers when deploy-target exactly equals "production"
```

### **Test 4: Boolean (Backward Compatible)**
```yaml
conditionExpression: "true"
# Still works as before
```

---

## 📝 **Changes At a Glance**

**Before:**
- Only evaluated boolean expressions
- Simple true/false logic

**After:**
- Evaluates ANY data type
- Type-aware decision rules
- Optional exact matching with `matchValue`
- Enhanced logging with type information
- Backward compatible with old property name
- Outputs evaluated value and type

---

## 🚀 **Ready to Deploy**

The updated code is ready to be deployed using the same deployment process. The plugin maintains full backward compatibility while adding powerful new capabilities!

**No breaking changes** - existing jobs using `conditionExpression` will continue to work exactly as before.
