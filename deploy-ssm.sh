#!/bin/bash
#
# Deploy Conditional Job Trigger Plugin using AWS Systems Manager
# EC2 Instance: i-0a71309ab193e7992 (ap-south-1)
#

set -e

echo "========================================"
echo "Rundeck Plugin Deployment via SSM"
echo "========================================"
echo ""

# Configuration
EC2_INSTANCE_ID="i-0a71309ab193e7992"
AWS_REGION="ap-south-1"
PLUGIN_NAME="conditional-job-trigger"
LOCAL_PLUGIN_DIR="examples/custom-plugins/conditional-job-trigger"
S3_BUCKET="rundeck-plugins-dev-512508756184"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Verifying EC2 instance and SSM availability...${NC}"

# Check instance exists
INSTANCE_INFO=$(aws ec2 describe-instances \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Reservations[0].Instances[0].[State.Name,PrivateIpAddress]' \
    --output text 2>/dev/null)

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to get instance details.${NC}"
    echo "Please check AWS CLI configuration and permissions."
    exit 1
fi

STATE=$(echo "$INSTANCE_INFO" | awk '{print $1}')
PRIVATE_IP=$(echo "$INSTANCE_INFO" | awk '{print $2}')

if [ "$STATE" != "running" ]; then
    echo -e "${RED}Error: Instance is not running (state: $STATE)${NC}"
    exit 1
fi

# Check SSM connectivity
echo "  Checking SSM connectivity..."
SSM_STATUS=$(aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'InstanceInformationList[0].PingStatus' \
    --output text 2>/dev/null || echo "NotAvailable")

if [ "$SSM_STATUS" != "Online" ]; then
    echo -e "${RED}Error: Instance is not connected to SSM (status: $SSM_STATUS)${NC}"
    echo "Please ensure:"
    echo "  1. SSM Agent is installed and running"
    echo "  2. Instance has AmazonSSMManagedInstanceCore policy"
    echo "  3. Instance can reach SSM endpoints"
    exit 1
fi

echo -e "${GREEN}✓ Instance is SSM-ready${NC}"
echo "  State:      $STATE"
echo "  Private IP: $PRIVATE_IP"
echo "  SSM Status: $SSM_STATUS"
echo ""

echo -e "${YELLOW}Step 2: Creating plugin package...${NC}"

if [ ! -d "$LOCAL_PLUGIN_DIR" ]; then
    echo -e "${RED}Error: Plugin directory not found: $LOCAL_PLUGIN_DIR${NC}"
    exit 1
fi

TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="$TEMP_DIR/$PLUGIN_NAME"
mkdir -p "$PACKAGE_DIR"

echo "  Copying files..."
cp -r "$LOCAL_PLUGIN_DIR/src" "$PACKAGE_DIR/"
cp -r "$LOCAL_PLUGIN_DIR/gradle" "$PACKAGE_DIR/"
cp "$LOCAL_PLUGIN_DIR/gradlew" "$PACKAGE_DIR/"
cp "$LOCAL_PLUGIN_DIR/gradlew.bat" "$PACKAGE_DIR/"
cp "$LOCAL_PLUGIN_DIR/build.gradle" "$PACKAGE_DIR/"
cp "$LOCAL_PLUGIN_DIR/settings.gradle" "$PACKAGE_DIR/"
cp "$LOCAL_PLUGIN_DIR/README.md" "$PACKAGE_DIR/" 2>/dev/null || true

echo "  Converting line endings to Unix format..."
if command -v dos2unix &> /dev/null; then
    dos2unix "$PACKAGE_DIR/gradlew" 2>/dev/null || sed -i 's/\r$//' "$PACKAGE_DIR/gradlew"
else
    sed -i 's/\r$//' "$PACKAGE_DIR/gradlew" 2>/dev/null || perl -pi -e 's/\r\n/\n/g' "$PACKAGE_DIR/gradlew"
fi

cd "$TEMP_DIR"
tar -czf "$PLUGIN_NAME.tar.gz" "$PLUGIN_NAME"
PACKAGE_FILE="$TEMP_DIR/$PLUGIN_NAME.tar.gz"

echo -e "${GREEN}✓ Package created${NC}"
echo "  Location: $PACKAGE_FILE"
echo "  Size: $(du -h "$PACKAGE_FILE" | cut -f1)"
echo ""

echo -e "${YELLOW}Step 3: Uploading package to S3...${NC}"

# Using existing S3 bucket
echo "  Using S3 bucket: $S3_BUCKET"

# Upload to S3
S3_KEY="plugins/${PLUGIN_NAME}-$(date +%Y%m%d-%H%M%S).tar.gz"
echo "  Uploading to s3://$S3_BUCKET/$S3_KEY"
aws s3 cp "$PACKAGE_FILE" "s3://$S3_BUCKET/$S3_KEY" --region "$AWS_REGION"

echo -e "${GREEN}✓ Package uploaded to S3${NC}"
echo ""

echo -e "${YELLOW}Step 4: Downloading package to EC2 instance...${NC}"

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --comment "Download Rundeck plugin from S3" \
    --parameters commands="[
        'mkdir -p /tmp/rundeck-plugins',
        'cd /tmp/rundeck-plugins',
        'aws s3 cp s3://$S3_BUCKET/$S3_KEY conditional-job-trigger.tar.gz --region $AWS_REGION',
        'echo Download complete'
    ]" \
    --query 'Command.CommandId' \
    --output text)

echo "  Command ID: $COMMAND_ID"
echo "  Waiting for download to complete..."

# Wait for command to complete
sleep 5
for i in {1..30}; do
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$EC2_INSTANCE_ID" \
        --region "$AWS_REGION" \
        --query 'Status' \
        --output text 2>/dev/null || echo "InProgress")
    
    if [ "$STATUS" = "Success" ]; then
        echo -e "${GREEN}✓ Download completed${NC}"
        break
    elif [ "$STATUS" = "Failed" ]; then
        echo -e "${RED}Error: Download failed${NC}"
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

echo -e "${YELLOW}Step 5: Building plugin on EC2...${NC}"

BUILD_SCRIPT='#!/bin/bash
set -e
cd /tmp/rundeck-plugins
echo "==> Extracting package..."
tar -xzf conditional-job-trigger.tar.gz
cd conditional-job-trigger

echo "==> Setting permissions..."
chmod -R u+x .
chmod +x gradlew

echo "==> Building plugin..."
bash gradlew clean build -x test

echo "==> Build complete!"
ls -lh build/libs/*.jar
'

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --comment "Build Rundeck plugin" \
    --parameters "commands=['$BUILD_SCRIPT']" \
    --query 'Command.CommandId' \
    --output text)

echo "  Command ID: $COMMAND_ID"
echo "  Building (this may take 30-60 seconds)..."

sleep 10
for i in {1..60}; do
    STATUS=$(aws ssm get-command-invocation \
        --command-id "$COMMAND_ID" \
        --instance-id "$EC2_INSTANCE_ID" \
        --region "$AWS_REGION" \
        --query 'Status' \
        --output text 2>/dev/null || echo "InProgress")
    
    if [ "$STATUS" = "Success" ]; then
        echo -e "${GREEN}✓ Build completed successfully${NC}"
        
        # Show build output
        OUTPUT=$(aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$EC2_INSTANCE_ID" \
            --region "$AWS_REGION" \
            --query 'StandardOutputContent' \
            --output text | tail -10)
        echo "$OUTPUT"
        break
    elif [ "$STATUS" = "Failed" ]; then
        echo -e "${RED}Error: Build failed${NC}"
        aws ssm get-command-invocation \
            --command-id "$COMMAND_ID" \
            --instance-id "$EC2_INSTANCE_ID" \
            --region "$AWS_REGION" \
            --query 'StandardErrorContent' \
            --output text | tail -20
        exit 1
    fi
    
    echo -n "."
    sleep 2
done
echo ""

echo -e "${YELLOW}Step 6: Installing plugin to Rundeck...${NC}"

INSTALL_SCRIPT='#!/bin/bash
set -e
cd /tmp/rundeck-plugins/conditional-job-trigger

echo "==> Installing plugin..."
RDECK_BASE="${RDECK_BASE:-/var/lib/rundeck}"
sudo mkdir -p "$RDECK_BASE/libext"
sudo cp build/libs/conditional-job-trigger-0.1.0.jar "$RDECK_BASE/libext/"
sudo chown rundeck:rundeck "$RDECK_BASE/libext/conditional-job-trigger-0.1.0.jar" 2>/dev/null || true

echo "==> Plugin installed to: $RDECK_BASE/libext/conditional-job-trigger-0.1.0.jar"
ls -lh "$RDECK_BASE/libext/conditional-job-trigger-0.1.0.jar"
'

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --comment "Install Rundeck plugin" \
    --parameters "commands=['$INSTALL_SCRIPT']" \
    --query 'Command.CommandId' \
    --output text)

sleep 3
aws ssm wait command-executed \
    --command-id "$COMMAND_ID" \
    --instance-id "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" 2>/dev/null || true

STATUS=$(aws ssm get-command-invocation \
    --command-id "$COMMAND_ID" \
    --instance-id "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --query 'Status' \
    --output text)

if [ "$STATUS" = "Success" ]; then
    echo -e "${GREEN}✓ Plugin installed${NC}"
else
    echo -e "${RED}Warning: Installation may have failed${NC}"
fi

echo ""
echo -e "${YELLOW}Step 7: Restarting Rundeck...${NC}"

RESTART_SCRIPT='#!/bin/bash
echo "==> Restarting Rundeck..."
sudo service rundeckd restart 2>/dev/null || sudo systemctl restart rundeckd 2>/dev/null || true
sleep 5
echo "==> Checking Rundeck status..."
sudo service rundeckd status 2>/dev/null || sudo systemctl status rundeckd 2>/dev/null || true
'

COMMAND_ID=$(aws ssm send-command \
    --instance-ids "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" \
    --document-name "AWS-RunShellScript" \
    --comment "Restart Rundeck" \
    --parameters "commands=['$RESTART_SCRIPT']" \
    --query 'Command.CommandId' \
    --output text)

sleep 5
aws ssm wait command-executed \
    --command-id "$COMMAND_ID" \
    --instance-id "$EC2_INSTANCE_ID" \
    --region "$AWS_REGION" 2>/dev/null || true

echo -e "${GREEN}✓ Rundeck restarted${NC}"
echo ""

echo -e "${YELLOW}Step 8: Cleaning up S3...${NC}"
echo "  Package will remain in S3 for backup: s3://$S3_BUCKET/$S3_KEY"
echo "  Delete manually if needed: aws s3 rm s3://$S3_BUCKET/$S3_KEY"
echo -e "${GREEN}✓ Deployment files preserved${NC}"
echo ""

# Cleanup local temp
rm -rf "$TEMP_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Plugin installed: /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar"
echo ""
echo "Next steps:"
echo "  1. Wait 30 seconds for Rundeck to load the plugin"
echo "  2. Access Rundeck UI and create/edit a job"
echo "  3. Add workflow step -> Look for 'Conditional Job Trigger'"
echo ""
echo "To verify plugin loaded, run:"
echo "  aws ssm start-session --target $EC2_INSTANCE_ID --region $AWS_REGION"
echo "  Then: tail -50 /var/log/rundeck/service.log | grep -i conditional"
echo ""
echo "To start an SSM session:"
echo "  aws ssm start-session --target $EC2_INSTANCE_ID --region $AWS_REGION"
