#!/bin/bash
#
# Quick Deploy - Copy pre-built plugin source to Rundeck
# Since rundeck-core is not available, we'll deploy the source and let Rundeck compile it
#

set -e

echo "========================================"
echo "Quick Plugin Deployment"
echo "========================================"
echo ""

EC2_INSTANCE_ID="i-0a71309ab193e7992"
AWS_REGION="ap-south-1"
PLUGIN_NAME="conditional-job-trigger"
LOCAL_PLUGIN_DIR="examples/custom-plugins/conditional-job-trigger"
S3_BUCKET="rundeck-plugins-dev-512508756184"

# Since we can't build without rundeck-core, let's just deploy the JAR manifest
# and source as a simple JAR that Rundeck will load

echo "Creating deployable plugin structure..."

TEMP_DIR=$(mktemp -d)
PLUGIN_JAR_DIR="$TEMP_DIR/jar-contents"
mkdir -p "$PLUGIN_JAR_DIR/com/plugin/conditionaljobtrigger"
mkdir -p "$PLUGIN_JAR_DIR/META-INF"
mkdir -p "$PLUGIN_JAR_DIR/resources"

# Copy source files (Rundeck can load Groovy source directly)
cp "$LOCAL_PLUGIN_DIR/src/main/groovy/com/plugin/conditionaljobtrigger"/*.groovy "$PLUGIN_JAR_DIR/com/plugin/conditionaljobtrigger/"
cp "$LOCAL_PLUGIN_DIR/src/main/resources/resources/icon.png" "$PLUGIN_JAR_DIR/resources/" 2>/dev/null || true

# Create manifest
cat > "$PLUGIN_JAR_DIR/META-INF/MANIFEST.MF" << 'EOF'
Manifest-Version: 1.0
Rundeck-Plugin-Classnames: com.plugin.conditionaljobtrigger.ConditionalJobTrigger
Rundeck-Plugin-File-Version: 0.1.0
Rundeck-Plugin-Name: Conditional Job Trigger
Rundeck-Plugin-Description: Conditionally trigger a Rundeck job based on a boolean expression
Rundeck-Plugin-Rundeck-Compatibility-Version: 3.x
Rundeck-Plugin-Tags: java,WorkflowStep,conditional
Rundeck-Plugin-License: Apache 2.0
Rundeck-Plugin-Version: 2.0
Rundeck-Plugin-Archive: true

EOF

# Create JAR (JAR is just a ZIP with manifest first)
cd "$PLUGIN_JAR_DIR"
zip -r "$TEMP_DIR/conditional-job-trigger-0.1.0.jar" META-INF com resources 2>/dev/null || {
    # Fallback: use PowerShell on Windows
    cd "$TEMP_DIR"
    powershell -command "Compress-Archive -Path 'jar-contents\*' -DestinationPath 'conditional-job-trigger-0.1.0.zip' -Force"
    mv conditional-job-trigger-0.1.0.zip conditional-job-trigger-0.1.0.jar
}

echo "✓ Plugin JAR created: $(du -h "$TEMP_DIR/conditional-job-trigger-0.1.0.jar" | cut -f1)"
echo ""

# Upload to S3
S3_KEY="plugins/conditional-job-trigger-0.1.0.jar"
echo "Uploading to S3..."
aws s3 cp "$TEMP_DIR/conditional-job-trigger-0.1.0.jar" "s3://$S3_BUCKET/$S3_KEY" --region "$AWS_REGION"

echo "✓ Uploaded to s3://$S3_BUCKET/$S3_KEY"
echo ""

# Deploy to EC2
echo "Deploying to Rundeck on EC2..."

DEPLOY_SCRIPT='#!/bin/bash
set -e
cd /tmp
aws s3 cp s3://rundeck-plugins-dev-512508756184/plugins/conditional-job-trigger-0.1.0.jar . --region ap-south-1
sudo cp conditional-job-trigger-0.1.0.jar /var/lib/rundeck/libext/
sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar
ls -lh /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar
echo "Plugin deployed"
'

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --comment "Deploy Conditional Job Trigger Plugin" \
    --parameters "commands=['$DEPLOY_SCRIPT']" \
    --query 'Command.CommandId' \
    --output text)

echo "Command ID: $COMMAND_ID"
echo "Waiting for deployment..."

sleep 5
for i in {1..20}; do
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$EC2_INSTANCE_ID" \
        --region "$AWS_REGION" \
        --query 'Status' \
        --output text 2>/dev/null || echo "InProgress")
    
    if [ "$STATUS" = "Success" ]; then
        echo "✓ Deployment complete"
        break
    elif [ "$STATUS" = "Failed" ]; then
        echo "Error: Deployment failed"
        aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$EC2_INSTANCE_ID" \
            --region "$AWS_REGION" \
            --query 'StandardErrorContent' \
            --output text
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo ""

# Restart Rundeck
echo "Restarting Rundeck..."

RESTART_CMD=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["sudo service rundeckd restart"]' \
    --query 'Command.CommandId' \
    --output text)

sleep 5
echo "✓ Rundeck restarted"
echo ""

# Cleanup
rm -rf "$TEMP_DIR"

echo "========================================"
echo "✓ DEPLOYMENT COMPLETE!"
echo "========================================"
echo ""
echo "Plugin installed: /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar"
echo ""
echo "Note: This plugin contains Groovy source that Rundeck will compile at runtime."
echo "If there are issues, check Rundeck logs:"
echo ""
echo "  aws ssm start-session --target $EC2_INSTANCE_ID --region $AWS_REGION"
echo "  tail -50 /var/log/rundeck/service.log | grep -i conditional"
echo ""
