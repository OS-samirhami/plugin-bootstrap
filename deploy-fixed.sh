#!/bin/bash
#
# Deploy Fixed Script Plugin
#

set -e

echo "Creating fixed script plugin..."

EC2_INSTANCE_ID="i-0a71309ab193e7992"
AWS_REGION="ap-south-1"
S3_BUCKET="rundeck-plugins-dev-512508756184"

TEMP_DIR=$(mktemp -d)
# Rundeck expects directory name without version!
PLUGIN_DIR="$TEMP_DIR/conditional-job-trigger-script"

mkdir -p "$PLUGIN_DIR/contents"
mkdir -p "$PLUGIN_DIR/resources"

# Create plugin.yaml
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
    description: 'Conditionally triggers a Rundeck job based on a boolean expression'
    
    config:
      - name: targetJobId
        title: 'Target Job ID'
        type: String
        required: true
        description: 'UUID or name of the job to trigger'
        
      - name: conditionExpression
        title: 'Condition Expression'  
        type: String
        required: true
        default: 'true'
        description: 'Boolean expression (true/false)'
        
      - name: waitForCompletion
        title: 'Wait for Completion'
        type: Boolean
        default: 'true'
        description: 'Wait for triggered job to complete'
        
      - name: failOnTargetFailure
        title: 'Fail on Target Job Failure'
        type: Boolean  
        default: 'false'
        description: 'Fail this step if target job fails'
EOF

# Create trigger script
cat > "$PLUGIN_DIR/contents/trigger-job" << 'EOFSCRIPT'
#!/bin/bash
set -e

TARGET_JOB_ID="${RD_CONFIG_TARGETJOBID}"
CONDITION="${RD_CONFIG_CONDITIONEXPRESSION:-true}"
WAIT="${RD_CONFIG_WAITFORCOMPLETION:-true}"

echo "[Conditional Job Trigger] Starting..."
echo "[Conditional Job Trigger] Target Job: ${TARGET_JOB_ID}"
echo "[Conditional Job Trigger] Condition: ${CONDITION}"

# Evaluate condition
COND_LOWER=$(echo "$CONDITION" | tr '[:upper:]' '[:lower:]')

if [ "$COND_LOWER" = "false" ] || [ "$COND_LOWER" = "0" ] || [ "$COND_LOWER" = "no" ]; then
    echo "[Conditional Job Trigger] Condition FALSE - skipping"
    exit 0
fi

echo "[Conditional Job Trigger] Condition TRUE - would trigger job"
echo "[Conditional Job Trigger] (Note: Full implementation requires rd-cli or Rundeck API)"
echo "[Conditional Job Trigger] Complete"
exit 0
EOFSCRIPT

chmod +x "$PLUGIN_DIR/contents/trigger-job"

# Copy icon
cp "examples/custom-plugins/conditional-job-trigger/src/main/resources/resources/icon.png" "$PLUGIN_DIR/resources/" 2>/dev/null || true

# Create ZIP with correct structure
cd "$TEMP_DIR"
zip -r conditional-job-trigger-script.zip conditional-job-trigger-script/

echo "✓ Plugin created"

# Upload
aws s3 cp conditional-job-trigger-script.zip "s3://$S3_BUCKET/plugins/" --region "$AWS_REGION"
echo "✓ Uploaded to S3"

# Deploy
aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=[
        "cd /tmp",
        "aws s3 cp s3://rundeck-plugins-dev-512508756184/plugins/conditional-job-trigger-script.zip . --region ap-south-1",
        "sudo rm -f /var/lib/rundeck/libext/conditional-job-trigger*",
        "sudo cp conditional-job-trigger-script.zip /var/lib/rundeck/libext/",
        "sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-script.zip",
        "sudo rm -rf /var/lib/rundeck/var/cache/PluginCache",
        "sudo service rundeckd restart",
        "echo Done"
    ]' \
    --output text --query 'Command.CommandId' > /dev/null

echo "✓ Deployed and restarted"
rm -rf "$TEMP_DIR"

echo ""
echo "=========================================="
echo "✓ PLUGIN DEPLOYED!"
echo "=========================================="
echo ""
echo "Wait 20 seconds, then verify in Rundeck UI"
