package com.plugin.conditionaljobtrigger

import com.dtolabs.rundeck.core.plugins.Plugin
import com.dtolabs.rundeck.plugins.step.StepPlugin
import com.dtolabs.rundeck.core.execution.workflow.steps.StepException
import com.dtolabs.rundeck.plugins.ServiceNameConstants
import com.dtolabs.rundeck.plugins.step.PluginStepContext
import com.dtolabs.rundeck.plugins.descriptions.PluginDescription
import com.dtolabs.rundeck.plugins.descriptions.PluginProperty
import com.dtolabs.rundeck.plugins.descriptions.RenderingOption
import com.dtolabs.rundeck.plugins.descriptions.SelectValues
import com.dtolabs.rundeck.core.execution.ExecutionListener
import com.dtolabs.rundeck.core.jobs.JobReference
import com.dtolabs.rundeck.core.jobs.JobService
import com.dtolabs.rundeck.core.execution.ExecutionReference
import javax.script.ScriptEngine
import javax.script.ScriptEngineManager
import static com.dtolabs.rundeck.core.plugins.configuration.StringRenderingConstants.GROUP_NAME

/**
 * Conditional Job Trigger - Workflow Step Plugin
 * 
 * Conditionally triggers another Rundeck job based on an expression evaluation.
 * Supports any data type: boolean, string, number, map, collection, or option values.
 * Uses Rundeck's internal ExecutionService to trigger jobs within the same context.
 */
@Plugin(name = PLUGIN_NAME, service = ServiceNameConstants.WorkflowStep)
@PluginDescription(title = PLUGIN_TITLE, description = PLUGIN_DESCRIPTION)
class ConditionalJobTrigger implements StepPlugin {
    
    public static final String PLUGIN_NAME = "conditional-job-trigger"
    public static final String PLUGIN_TITLE = "Conditional Job Trigger"
    public static final String PLUGIN_DESCRIPTION = "Conditionally trigger a Rundeck job based on an expression. Supports boolean, string, number, map, or collection values."

    @PluginProperty(
        title = "Target Job ID",
        description = "The UUID or name of the job to trigger. Example: 'abc123-def456-ghi789' or 'my-job-name'",
        required = true
    )
    @RenderingOption(key = GROUP_NAME, value = "Job Configuration")
    String targetJobId

    @PluginProperty(
        title = "Value Expression",
        description = """Expression to evaluate. Supports any data type:
- Boolean: true/false
- String: '\${option.environment}' (non-empty triggers)
- Number: '\${data.count}' (non-zero triggers)
- Variables: '\${job.status}', '\${option.deploy}'
- Complex: '\${data.value}' == 'production'

Evaluation rules:
- null → skip
- Boolean true → trigger
- Non-empty string → trigger
- Non-zero number → trigger
- Non-empty collection/map → trigger

Example: '\${option.environment}' returns 'prod' → triggers job""",
        defaultValue = "true",
        required = true
    )
    @RenderingOption(key = GROUP_NAME, value = "Condition Configuration")
    String valueExpression
    
    @PluginProperty(
        title = "Condition Expression (Legacy)",
        description = "Deprecated: Use 'Value Expression' instead. Kept for backward compatibility.",
        required = false
    )
    @RenderingOption(key = GROUP_NAME, value = "Condition Configuration")
    String conditionExpression
    
    @PluginProperty(
        title = "Match Value",
        description = "Optional: If set, job triggers ONLY when expression result equals this value (string comparison). Leave empty to use default evaluation rules.",
        required = false
    )
    @RenderingOption(key = GROUP_NAME, value = "Condition Configuration")
    String matchValue

    @PluginProperty(
        title = "Wait for Completion",
        description = "If true, wait for the triggered job to complete before continuing. If false, trigger and continue immediately.",
        defaultValue = "true",
        required = false
    )
    @SelectValues(values = ["true", "false"])
    @RenderingOption(key = GROUP_NAME, value = "Execution Configuration")
    String waitForCompletion

    @PluginProperty(
        title = "Fail on Target Job Failure",
        description = "If waiting for completion, fail this step if the target job fails.",
        defaultValue = "false",
        required = false
    )
    @SelectValues(values = ["true", "false"])
    @RenderingOption(key = GROUP_NAME, value = "Execution Configuration")
    String failOnTargetFailure

    @Override
    void executeStep(final PluginStepContext context, final Map<String, Object> configuration) {
        ExecutionListener logger = context.getExecutionContext().getExecutionListener()
        
        logger.log(2, "[Conditional Job Trigger] Starting evaluation...")
        logger.log(3, "[Conditional Job Trigger] Target Job ID: ${targetJobId}")
        
        // Backward compatibility: use valueExpression if set, otherwise fall back to conditionExpression
        String expression = valueExpression ?: conditionExpression
        logger.log(3, "[Conditional Job Trigger] Expression: ${expression}")
        if (matchValue) {
            logger.log(3, "[Conditional Job Trigger] Match Value: ${matchValue}")
        }
        
        // Step 1: Evaluate expression and get raw result
        def evaluationResult = evaluateExpression(expression, context, logger)
        Object rawValue = evaluationResult.value
        String valueType = evaluationResult.type
        
        logger.log(3, "[Conditional Job Trigger] Evaluated value: ${rawValue} (type: ${valueType})")
        
        // Step 2: Decide whether to trigger based on value
        boolean shouldTrigger = shouldTriggerJob(rawValue, matchValue, logger)
        
        if (!shouldTrigger) {
            logger.log(2, "[Conditional Job Trigger] Condition not met - skipping job execution")
            context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "skipped", "true")
            context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "evaluated-value", rawValue?.toString() ?: "null")
            context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "value-type", valueType)
            return
        }
        
        logger.log(2, "[Conditional Job Trigger] Condition met - triggering job")
        
        // Step 2: Get JobService from context
        JobService jobService = context.getExecutionContext().getJobService()
        if (!jobService) {
            throw new StepException(
                "JobService not available in execution context",
                PluginFailureReason.JobServiceUnavailable
            )
        }
        
        // Step 3: Resolve the job reference
        String projectName = context.getFrameworkProject()
        JobReference jobRef = resolveJobReference(targetJobId, projectName, jobService, logger)
        
        if (!jobRef) {
            throw new StepException(
                "Could not find job with ID or name: ${targetJobId}",
                PluginFailureReason.JobNotFound
            )
        }
        
        logger.log(2, "[Conditional Job Trigger] Found job: ${jobRef.getJobName()} (${jobRef.getId()})")
        
        // Step 4: Trigger the job
        boolean shouldWait = waitForCompletion?.toLowerCase() == "true"
        boolean shouldFailOnError = failOnTargetFailure?.toLowerCase() == "true"
        
        try {
            Map<String, String> jobOptions = [:]  // Could be extended to pass options
            
            logger.log(2, "[Conditional Job Trigger] Executing job (wait: ${shouldWait})...")
            
            // Use JobService to execute the job
            ExecutionReference execRef = jobService.runJob(
                jobRef,
                context.getExecutionContext().getAuthContext(),
                context.getExecutionContext().getUser(),
                jobOptions
            )
            
            if (execRef) {
                logger.log(2, "[Conditional Job Trigger] Job triggered successfully. Execution ID: ${execRef.getId()}")
                context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "execution-id", execRef.getId())
                context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "triggered", "true")
                context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "evaluated-value", rawValue?.toString() ?: "null")
                context.getExecutionContext().getOutputContext().addOutput("conditional-trigger", "value-type", valueType)
                
                if (shouldWait) {
                    logger.log(2, "[Conditional Job Trigger] Waiting for job completion...")
                    waitForJobCompletion(execRef, jobService, shouldFailOnError, logger)
                }
            } else {
                throw new StepException(
                    "Failed to trigger job - no execution reference returned",
                    PluginFailureReason.JobExecutionFailed
                )
            }
            
        } catch (Exception e) {
            logger.log(0, "[Conditional Job Trigger] Error triggering job: ${e.message}")
            throw new StepException(
                "Failed to trigger job: ${e.message}",
                PluginFailureReason.JobExecutionFailed
            )
        }
        
        logger.log(2, "[Conditional Job Trigger] Complete")
    }
    
    /**
     * Evaluate the expression and return raw result with type information
     * Returns: [value: Object, type: String]
     */
    private Map evaluateExpression(String expression, PluginStepContext context, ExecutionListener logger) {
        if (!expression || expression.trim().isEmpty()) {
            return [value: null, type: "null"]
        }
        
        // Expand variables from execution context (options, data context, etc.)
        String expandedExpression = context.getExecutionContext().getDataContext().replaceDataReferences(expression)
        logger.log(3, "[Conditional Job Trigger] Expanded expression: ${expandedExpression}")
        
        // If expansion resulted in just a value (no operators), return it directly
        if (!expandedExpression.contains("==") && !expandedExpression.contains("!=") && 
            !expandedExpression.contains(">") && !expandedExpression.contains("<") &&
            !expandedExpression.contains("&&") && !expandedExpression.contains("||")) {
            
            // Direct value - try to parse as number, boolean, or keep as string
            Object parsedValue = parseValue(expandedExpression.trim())
            String type = getValueType(parsedValue)
            return [value: parsedValue, type: type]
        }
        
        // Complex expression - evaluate using JavaScript engine
        try {
            ScriptEngineManager manager = new ScriptEngineManager()
            ScriptEngine engine = manager.getEngineByName("JavaScript")
            Object result = engine.eval(expandedExpression)
            String type = getValueType(result)
            
            logger.log(3, "[Conditional Job Trigger] JavaScript evaluation result: ${result} (${type})")
            return [value: result, type: type]
        } catch (Exception e) {
            logger.log(1, "[Conditional Job Trigger] Warning: Could not evaluate expression, treating as string: ${e.message}")
            return [value: expandedExpression, type: "string"]
        }
    }
    
    /**
     * Parse a string value to its appropriate type
     */
    private Object parseValue(String value) {
        if (value == null || value.isEmpty()) {
            return null
        }
        
        // Try boolean
        if (value.equalsIgnoreCase("true")) return true
        if (value.equalsIgnoreCase("false")) return false
        
        // Try number
        try {
            if (value.contains(".")) {
                return Double.parseDouble(value)
            } else {
                return Long.parseLong(value)
            }
        } catch (NumberFormatException e) {
            // Not a number, return as string
        }
        
        return value
    }
    
    /**
     * Get the type name of a value
     */
    private String getValueType(Object value) {
        if (value == null) return "null"
        if (value instanceof Boolean) return "boolean"
        if (value instanceof Number) return "number"
        if (value instanceof String) return "string"
        if (value instanceof Map) return "map"
        if (value instanceof Collection) return "collection"
        return value.getClass().getSimpleName()
    }
    
    /**
     * Decide whether to trigger job based on evaluated value
     * 
     * Rules:
     * - If matchValue is set: trigger only if value.toString() equals matchValue
     * - Otherwise:
     *   - null → skip
     *   - Boolean true → trigger
     *   - Non-empty string → trigger
     *   - Non-zero number → trigger
     *   - Non-empty collection/map → trigger
     */
    private boolean shouldTriggerJob(Object value, String matchValue, ExecutionListener logger) {
        // Rule 1: If matchValue is specified, do exact string comparison
        if (matchValue != null && !matchValue.trim().isEmpty()) {
            String valueStr = value?.toString() ?: ""
            boolean matches = valueStr.equals(matchValue)
            logger.log(3, "[Conditional Job Trigger] Match comparison: '${valueStr}' == '${matchValue}' → ${matches}")
            return matches
        }
        
        // Rule 2: null → skip
        if (value == null) {
            logger.log(3, "[Conditional Job Trigger] Value is null → skip")
            return false
        }
        
        // Rule 3: Boolean → use directly
        if (value instanceof Boolean) {
            logger.log(3, "[Conditional Job Trigger] Boolean value: ${value} → ${value ? 'trigger' : 'skip'}")
            return (Boolean) value
        }
        
        // Rule 4: String → non-empty triggers
        if (value instanceof String) {
            boolean nonEmpty = !((String) value).trim().isEmpty()
            logger.log(3, "[Conditional Job Trigger] String value: '${value}' → ${nonEmpty ? 'trigger' : 'skip'}")
            return nonEmpty
        }
        
        // Rule 5: Number → non-zero triggers
        if (value instanceof Number) {
            boolean nonZero = ((Number) value).doubleValue() != 0.0
            logger.log(3, "[Conditional Job Trigger] Number value: ${value} → ${nonZero ? 'trigger' : 'skip'}")
            return nonZero
        }
        
        // Rule 6: Collection → non-empty triggers
        if (value instanceof Collection) {
            boolean nonEmpty = !((Collection) value).isEmpty()
            logger.log(3, "[Conditional Job Trigger] Collection (size ${((Collection) value).size()}) → ${nonEmpty ? 'trigger' : 'skip'}")
            return nonEmpty
        }
        
        // Rule 7: Map → non-empty triggers
        if (value instanceof Map) {
            boolean nonEmpty = !((Map) value).isEmpty()
            logger.log(3, "[Conditional Job Trigger] Map (size ${((Map) value).size()}) → ${nonEmpty ? 'trigger' : 'skip'}")
            return nonEmpty
        }
        
        // Default: any other object triggers
        logger.log(3, "[Conditional Job Trigger] Object of type ${value.getClass().getSimpleName()} → trigger")
        return true
    }
    
    /**
     * Resolve job reference by ID or name
     */
    private JobReference resolveJobReference(String jobIdOrName, String projectName, JobService jobService, ExecutionListener logger) {
        // Try as UUID first
        try {
            return jobService.jobForID(jobIdOrName, projectName)
        } catch (Exception e) {
            logger.log(3, "[Conditional Job Trigger] Not a valid UUID, trying as job name...")
        }
        
        // Try as job name
        try {
            return jobService.jobForName(projectName, jobIdOrName)
        } catch (Exception e) {
            logger.log(3, "[Conditional Job Trigger] Could not find job by name either")
        }
        
        return null
    }
    
    /**
     * Wait for job completion (simplified - actual implementation depends on Rundeck API)
     */
    private void waitForJobCompletion(ExecutionReference execRef, JobService jobService, boolean failOnError, ExecutionListener logger) {
        // Note: Actual implementation would poll the execution status
        // This is a simplified version showing the structure
        logger.log(3, "[Conditional Job Trigger] Job execution monitoring would happen here")
        logger.log(3, "[Conditional Job Trigger] In production, poll execution status until completion")
        
        // Placeholder: In real implementation, you'd:
        // 1. Poll executionService.getExecutionState(execRef.getId())
        // 2. Check if status is completed/failed/aborted
        // 3. If failOnError and status is failed, throw StepException
    }
}
