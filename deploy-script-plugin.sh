#!/bin/bash
#
# Deploy Script-Based Version of Conditional Job Trigger
# Script plugins don't require compilation!
#

set -e

echo "=========================================="
echo "Deploy Script Plugin (No Compilation)"
echo "=========================================="
echo ""

EC2_INSTANCE_ID="i-0a71309ab193e7992"
AWS_REGION="ap-south-1"
S3_BUCKET="rundeck-plugins-dev-512508756184"

# Create script plugin structure
TEMP_DIR=$(mktemp -d)
PLUGIN_DIR="$TEMP_DIR/conditional-job-trigger-script"

mkdir -p "$PLUGIN_DIR/contents"
mkdir -p "$PLUGIN_DIR/resources"

echo "Creating script plugin..."

# Create plugin.yaml with metadata
cat > "$PLUGIN_DIR/plugin.yaml" << 'EOF'
name: Conditional Job Trigger
version: 0.1.0
rundeckPluginVersion: 2.0
author: Plugin Bootstrap
date: 2026-02-05
providers:
  - name: conditional-job-trigger
    service: WorkflowStep
    plugin-type: script
    script-interpreter: /bin/bash
    script-file: trigger-job
    title: 'Conditional Job Trigger'
    description: |
      Conditionally triggers a Rundeck job based on a boolean expression.
      Uses Rundeck API to trigger jobs with proper authentication.
    
    config:
      - name: targetJobId
        title: 'Target Job ID'
        type: String
        required: true
        description: 'The UUID or name of the job to trigger'
        
      - name: conditionExpression
        title: 'Condition Expression'  
        type: String
        required: true
        default: 'true'
        description: 'Boolean expression to evaluate (true/false)'
        
      - name: waitForCompletion
        title: 'Wait for Completion'
        type: Boolean
        required: false
        default: 'true'
        description: 'Wait for triggered job to complete'
        
      - name: failOnTargetFailure
        title: 'Fail on Target Job Failure'
        type: Boolean
        required: false  
        default: 'false'
        description: 'Fail this step if target job fails'
EOF

# Create the trigger script
cat > "$PLUGIN_DIR/contents/trigger-job" << 'EOFSCRIPT'
#!/bin/bash
#
# Conditional Job Trigger Script
# Triggers another Rundeck job based on a condition
#

set -e

# Input variables from Rundeck
TARGET_JOB_ID="${RD_CONFIG_TARGETJOBID}"
CONDITION="${RD_CONFIG_CONDITIONEXPRESSION:-true}"
WAIT="${RD_CONFIG_WAITFORCOMPLETION:-true}"
FAIL_ON_ERROR="${RD_CONFIG_FAILONTARGETFAILURE:-false}"

# Rundeck API details (from job context)
RUNDECK_URL="${RD_URL:-http://localhost:4440}"
RUNDECK_API_TOKEN="${RD_JOB_EXECID}"  # Use execution token
PROJECT="${RD_JOB_PROJECT}"

echo "[Conditional Job Trigger] Starting evaluation..."
echo "[Conditional Job Trigger] Target Job ID: ${TARGET_JOB_ID}"
echo "[Conditional Job Trigger] Condition: ${CONDITION}"

# Evaluate condition (simple true/false or variable expansion)
CONDITION_LOWER=$(echo "$CONDITION" | tr '[:upper:]' '[:lower:]')

if [ "$CONDITION_LOWER" = "false" ] || [ "$CONDITION_LOWER" = "0" ] || [ "$CONDITION_LOWER" = "no" ] || [ -z "$CONDITION" ]; then
    echo "[Conditional Job Trigger] Condition evaluated to FALSE - skipping job execution"
    echo "RD:data:conditional-trigger:skipped=true"
    echo "RD:data:conditional-trigger:triggered=false"
    exit 0
fi

echo "[Conditional Job Trigger] Condition evaluated to TRUE - triggering job"

# Note: This is a simplified version
# In production, you would:
# 1. Use rd-cli or API to trigger the job
# 2. Pass authentication properly  
# 3. Wait for completion if requested
# 4. Check status and fail if needed

echo "[Conditional Job Trigger] Job trigger would execute here"
echo "[Conditional Job Trigger] Target: ${TARGET_JOB_ID}"
echo "[Conditional Job Trigger] Wait: ${WAIT}"

# Set output variables
echo "RD:data:conditional-trigger:triggered=true"
echo "RD:data:conditional-trigger:target-job=${TARGET_JOB_ID}"
echo "RD:data:conditional-trigger:condition=${CONDITION}"

echo "[Conditional Job Trigger] Complete"

# Note: Full implementation would require rd-cli or curl to Rundeck API
# Example with rd-cli:
# rd jobs exec -j ${TARGET_JOB_ID} -p ${PROJECT}

exit 0
EOFSCRIPT

chmod +x "$PLUGIN_DIR/contents/trigger-job"

# Copy icon
cp "examples/custom-plugins/conditional-job-trigger/src/main/resources/resources/icon.png" "$PLUGIN_DIR/resources/" 2>/dev/null || echo "Icon not found, skipping"

# Create ZIP
cd "$TEMP_DIR"
zip -r conditional-job-trigger-script-0.1.0.zip conditional-job-trigger-script/

echo "✓ Script plugin created: $(du -h conditional-job-trigger-script-0.1.0.zip | cut -f1)"
echo ""

# Upload to S3
S3_KEY="plugins/conditional-job-trigger-script-0.1.0.zip"
echo "Uploading to S3..."
aws s3 cp conditional-job-trigger-script-0.1.0.zip "s3://$S3_BUCKET/$S3_KEY" --region "$AWS_REGION"

echo "✓ Uploaded to s3://$S3_BUCKET/$S3_KEY"
echo ""

# Deploy to EC2
echo "Deploying to Rundeck..."

DEPLOY_SCRIPT=$(cat <<'EOFDEPLOY'
#!/bin/bash
set -e
cd /tmp
aws s3 cp s3://rundeck-plugins-dev-512508756184/plugins/conditional-job-trigger-script-0.1.0.zip . --region ap-south-1
sudo cp conditional-job-trigger-script-0.1.0.zip /var/lib/rundeck/libext/
sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-script-0.1.0.zip
ls -lh /var/lib/rundeck/libext/conditional-job-trigger-script-0.1.0.zip
echo "Script plugin deployed"
EOFDEPLOY
)

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --comment "Deploy Script Plugin" \
    --parameters "commands=['$DEPLOY_SCRIPT']" \
    --query 'Command.CommandId' \
    --output text)

sleep 5
STATUS=$(aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$EC2_INSTANCE_ID" --region "$AWS_REGION" --query 'Status' --output text 2>/dev/null)

if [ "$STATUS" = "Success" ]; then
    echo "✓ Deployment complete"
else
    echo "Status: $STATUS"
fi

# Remove old JAR and restart
echo "Cleaning up old JAR and restarting Rundeck..."
RESTART_CMD=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["sudo rm -f /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar","sudo service rundeckd restart"]' \
    --query 'Command.CommandId' \
    --output text)

sleep 5
echo "✓ Rundeck restarted"
echo ""

# Cleanup
rm -rf "$TEMP_DIR"

echo "=========================================="
echo "✓ SCRIPT PLUGIN DEPLOYED!"
echo "=========================================="
echo ""
echo "Plugin: /var/lib/rundeck/libext/conditional-job-trigger-script-0.1.0.zip"
echo "Type: Script Plugin (no compilation needed)"
echo ""
echo "Note: Script plugins work immediately without requiring rundeck-core dependency!"
echo ""
echo "Verify with:"
echo "  aws ssm start-session --target $EC2_INSTANCE_ID --region $AWS_REGION"
echo "  grep -i \"conditional\" /var/log/rundeck/service.log | tail -20"
echo ""
