# Conditional Job Trigger - Rundeck Plugin

A Workflow Step Plugin that conditionally triggers another Rundeck job based on a boolean expression.

## Features

- **Node-agnostic**: Works as a workflow step without requiring nodes
- **Internal ExecutionService**: Uses Rundeck's internal JobService (no REST API calls)
- **Auth Context Aware**: Respects the execution's authentication context
- **Flexible Conditions**: Supports simple booleans and complex expressions with variable interpolation
- **Async Support**: Option to wait for completion or trigger and continue

## Configuration

### Target Job ID
The UUID or name of the job to trigger.
- Example UUID: `abc123-def456-ghi789`
- Example name: `my-deployment-job`

### Condition Expression
Boolean expression to evaluate. The job will only trigger if the expression evaluates to `true`.

**Examples:**
- Simple: `true` or `false`
- Variables: `${option.deploy}` (checks if deploy option equals "true")
- Comparisons: `${data.count} > 10`
- Complex: `${option.environment} == 'production' && ${job.status} == 'success'`

### Wait for Completion
- `true`: Wait for the triggered job to finish before continuing
- `false`: Trigger the job and continue immediately (fire-and-forget)

### Fail on Target Job Failure
- `true`: If waiting for completion and the target job fails, fail this step
- `false`: Continue regardless of target job outcome

## Usage Example

### Scenario: Conditional Deployment

```yaml
- type: conditional-job-trigger
  nodeStep: false
  configuration:
    targetJobId: "deploy-to-production"
    conditionExpression: "${option.environment} == 'production' && ${data.tests-passed} == 'true'"
    waitForCompletion: "true"
    failOnTargetFailure: "true"
```

### Scenario: Parallel Notification

```yaml
- type: conditional-job-trigger
  nodeStep: false
  configuration:
    targetJobId: "send-slack-notification"
    conditionExpression: "${option.notify-on-success}"
    waitForCompletion: "false"
```

## Output Context

The plugin sets the following output context variables:

- `${conditional-trigger.triggered}`: `true` if job was triggered
- `${conditional-trigger.skipped}`: `true` if condition was false
- `${conditional-trigger.execution-id}`: Execution ID of triggered job
- `${conditional-trigger.condition}`: The evaluated condition

These can be used in subsequent steps:

```
Next step can check: ${conditional-trigger.execution-id}
```

## Build

```bash
# Copy Gradle wrapper (if not already present)
cp -r ../../../gradle .
cp ../../../gradlew* .

# Create settings.gradle
echo "rootProject.name = 'conditional-job-trigger'" > settings.gradle

# Build
./gradlew clean build
```

## Install

```bash
# Copy the built JAR to Rundeck's plugins directory
cp build/libs/conditional-job-trigger-0.1.0.jar $RDECK_BASE/libext/

# Restart Rundeck
sudo service rundeckd restart
```

## Logging

The plugin uses Rundeck's standard logging levels:
- **Level 0 (Error)**: Critical failures
- **Level 2 (Notice)**: Important execution information
- **Level 3 (Info)**: Detailed debugging (requires "Debug Output" option)

## Requirements

- Rundeck 3.x, 4.x, or 5.x
- Java 11 or later
- JobService available in execution context

## License

Apache 2.0

## Notes

- The `waitForCompletion` functionality shows the structure but requires full implementation with execution polling
- For production use, implement proper execution state monitoring
- Consider adding retry logic for failed job triggers
- Could be extended to pass job options to the triggered job
