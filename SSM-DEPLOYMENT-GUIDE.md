# SSM Deployment Guide
# Deploy Rundeck Plugin using AWS Systems Manager

## ✅ Prerequisites

1. **AWS CLI configured**
   ```bash
   aws configure
   # Set region: ap-south-1
   ```

2. **SSM Session Manager Plugin installed**
   ```bash
   # Check if installed
   session-manager-plugin --version
   
   # If not installed, download from:
   # https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html
   ```

3. **IAM Permissions**
   - `ssm:SendCommand`
   - `ssm:GetCommandInvocation`
   - `ssm:StartSession`
   - `s3:PutObject`, `s3:GetObject` (for file transfer)

4. **EC2 Instance Requirements**
   - SSM Agent installed and running
   - IAM instance profile with `AmazonSSMManagedInstanceCore` policy
   - Can reach SSM endpoints

---

## 🚀 Deployment Methods

### Method 1: Automated Script (Recommended)

#### Linux/Mac/WSL:
```bash
# Make executable
chmod +x deploy-ssm.sh

# Run
./deploy-ssm.sh
```

#### Windows:
```cmd
deploy-ssm.bat
```

The script will:
1. ✅ Verify SSM connectivity
2. ✅ Package the plugin
3. ✅ Upload to S3 (temporary bucket)
4. ✅ Download to EC2 via SSM
5. ✅ Build on EC2
6. ✅ Install to Rundeck
7. ✅ Restart Rundeck
8. ✅ Clean up S3

---

### Method 2: Manual SSM Commands

#### Step 1: Package Plugin Locally

```bash
cd examples/custom-plugins
tar -czf conditional-job-trigger.tar.gz conditional-job-trigger/

# Or on Windows:
powershell Compress-Archive -Path conditional-job-trigger -DestinationPath conditional-job-trigger.zip
```

#### Step 2: Upload to S3

```bash
# Create/use an S3 bucket
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
S3_BUCKET="ssm-transfer-${ACCOUNT_ID}-ap-south-1"

# Create bucket if needed
aws s3 mb s3://$S3_BUCKET --region ap-south-1

# Upload package
aws s3 cp conditional-job-trigger.tar.gz s3://$S3_BUCKET/rundeck-plugins/ --region ap-south-1
```

#### Step 3: Download to EC2 via SSM

```bash
aws ssm send-command \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name "AWS-RunShellScript" \
    --comment "Download Rundeck plugin" \
    --parameters 'commands=[
        "mkdir -p /tmp/rundeck-plugins",
        "cd /tmp/rundeck-plugins",
        "aws s3 cp s3://YOUR_BUCKET/rundeck-plugins/conditional-job-trigger.tar.gz . --region ap-south-1",
        "tar -xzf conditional-job-trigger.tar.gz",
        "echo Download complete"
    ]'
```

#### Step 4: Build Plugin via SSM

```bash
aws ssm send-command \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name "AWS-RunShellScript" \
    --comment "Build Rundeck plugin" \
    --parameters 'commands=[
        "cd /tmp/rundeck-plugins/conditional-job-trigger",
        "chmod +x gradlew",
        "./gradlew clean build -x test",
        "ls -lh build/libs/"
    ]'
```

#### Step 5: Install Plugin via SSM

```bash
aws ssm send-command \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name "AWS-RunShellScript" \
    --comment "Install Rundeck plugin" \
    --parameters 'commands=[
        "cd /tmp/rundeck-plugins/conditional-job-trigger",
        "sudo cp build/libs/conditional-job-trigger-0.1.0.jar /var/lib/rundeck/libext/",
        "sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar",
        "ls -lh /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar"
    ]'
```

#### Step 6: Restart Rundeck via SSM

```bash
aws ssm send-command \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name "AWS-RunShellScript" \
    --comment "Restart Rundeck" \
    --parameters 'commands=[
        "sudo service rundeckd restart",
        "sleep 5",
        "sudo service rundeckd status"
    ]'
```

---

### Method 3: Interactive SSM Session

```bash
# Start interactive session
aws ssm start-session \
    --target i-0a71309ab193e7992 \
    --region ap-south-1

# Once connected, run these commands:
mkdir -p /tmp/rundeck-plugins
cd /tmp/rundeck-plugins

# Download from S3
aws s3 cp s3://YOUR_BUCKET/rundeck-plugins/conditional-job-trigger.tar.gz .
tar -xzf conditional-job-trigger.tar.gz
cd conditional-job-trigger

# Build
chmod +x gradlew
./gradlew clean build -x test

# Install
sudo cp build/libs/conditional-job-trigger-0.1.0.jar /var/lib/rundeck/libext/
sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar

# Restart Rundeck
sudo service rundeckd restart

# Verify
tail -50 /var/log/rundeck/service.log | grep -i conditional
```

---

## 📋 Quick Reference Commands

### Check SSM Connectivity
```bash
aws ssm describe-instance-information \
    --filters "Key=InstanceIds,Values=i-0a71309ab193e7992" \
    --region ap-south-1 \
    --query 'InstanceInformationList[0].[PingStatus,PlatformName,PlatformVersion]' \
    --output table
```

### View Command Output
```bash
# Get command ID from send-command output, then:
aws ssm get-command-invocation \
    --command-id COMMAND_ID_HERE \
    --instance-id i-0a71309ab193e7992 \
    --region ap-south-1 \
    --query '[Status,StandardOutputContent,StandardErrorContent]' \
    --output text
```

### List Recent Commands
```bash
aws ssm list-commands \
    --instance-id i-0a71309ab193e7992 \
    --region ap-south-1 \
    --max-results 10 \
    --query 'Commands[*].[CommandId,Status,DocumentName,Comment]' \
    --output table
```

### Start SSM Session
```bash
aws ssm start-session \
    --target i-0a71309ab193e7992 \
    --region ap-south-1
```

### Port Forwarding (for Rundeck UI)
```bash
# Forward Rundeck port 4440 to local port 8080
aws ssm start-session \
    --target i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name AWS-StartPortForwardingSession \
    --parameters '{"portNumber":["4440"],"localPortNumber":["8080"]}'

# Then access: http://localhost:8080
```

---

## 🔍 Verification

### After Deployment

```bash
# Start SSM session
aws ssm start-session --target i-0a71309ab193e7992 --region ap-south-1

# Check plugin installed
ls -lh /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar

# Check Rundeck logs
tail -100 /var/log/rundeck/service.log | grep -i conditional

# Check Rundeck status
sudo service rundeckd status

# Look for plugin load messages
grep "Loaded plugin" /var/log/rundeck/service.log | grep conditional
```

---

## ⚠️ Troubleshooting

### SSM Agent Not Connected

```bash
# SSH to instance (if you have access) and check agent
sudo systemctl status amazon-ssm-agent

# Restart agent
sudo systemctl restart amazon-ssm-agent

# Check logs
sudo tail -50 /var/log/amazon/ssm/amazon-ssm-agent.log
```

### IAM Role Missing

EC2 instance needs an IAM role with this policy:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ssm:UpdateInstanceInformation",
      "ssmmessages:CreateControlChannel",
      "ssmmessages:CreateDataChannel",
      "ssmmessages:OpenControlChannel",
      "ssmmessages:OpenDataChannel",
      "s3:GetObject"
    ],
    "Resource": "*"
  }]
}
```

### Command Timeout

Increase timeout when sending commands:
```bash
aws ssm send-command \
    --timeout-seconds 600 \
    ...other parameters...
```

### Build Fails on EC2

Check build output:
```bash
aws ssm get-command-invocation \
    --command-id COMMAND_ID \
    --instance-id i-0a71309ab193e7992 \
    --region ap-south-1 \
    --query 'StandardErrorContent' \
    --output text
```

---

## 📁 Files Created

- ✅ `deploy-ssm.sh` - Automated SSM deployment (Linux/Mac/WSL)
- ✅ `deploy-ssm.bat` - Automated SSM deployment (Windows)
- ✅ `SSM-DEPLOYMENT-GUIDE.md` - This guide

---

## 🎯 Recommended Workflow

1. **Use automated script** for fastest deployment:
   ```bash
   ./deploy-ssm.sh
   ```

2. **Or use interactive session** for troubleshooting:
   ```bash
   aws ssm start-session --target i-0a71309ab193e7992 --region ap-south-1
   # Then follow manual steps
   ```

3. **Verify plugin loaded** in Rundeck UI

4. **Test plugin** by creating a test job

---

**All set!** The SSM deployment method is more secure than SSH as it:
- ✅ Uses IAM for authentication (no SSH keys)
- ✅ Logs all commands in CloudTrail
- ✅ Works without public IP address
- ✅ Supports session recording
