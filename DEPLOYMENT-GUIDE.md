# Manual Deployment Guide
# EC2 Instance: i-0a71309ab193e7992 (ap-south-1)

## Prerequisites

1. **AWS CLI configured:**
   ```bash
   aws configure
   # Set your credentials and region: ap-south-1
   ```

2. **SSH Key for EC2 access**
   - Locate your .pem or .ppk file
   - Ensure permissions: `chmod 400 your-key.pem` (Linux/Mac)

3. **EC2 Instance Running**
   ```bash
   # Check instance status
   aws ec2 describe-instances \
       --instance-ids i-0a71309ab193e7992 \
       --region ap-south-1 \
       --query 'Reservations[0].Instances[0].State.Name'
   
   # If stopped, start it:
   aws ec2 start-instances \
       --instance-ids i-0a71309ab193e7992 \
       --region ap-south-1
   ```

4. **Get Public IP**
   ```bash
   aws ec2 describe-instances \
       --instance-ids i-0a71309ab193e7992 \
       --region ap-south-1 \
       --query 'Reservations[0].Instances[0].PublicIpAddress' \
       --output text
   ```

---

## Option 1: Automated Deployment (Linux/Mac/WSL)

```bash
# Make script executable
chmod +x deploy-to-ec2.sh

# Run deployment script
./deploy-to-ec2.sh
```

The script will:
1. Get EC2 instance details
2. Package the plugin
3. Upload to EC2
4. Build on EC2
5. Install to Rundeck
6. Restart Rundeck

---

## Option 2: Manual Step-by-Step Deployment

### Step 1: Create Plugin Package

```bash
cd examples/custom-plugins
tar -czf conditional-job-trigger.tar.gz conditional-job-trigger/
```

Or create ZIP (Windows):
```cmd
cd examples\custom-plugins
powershell Compress-Archive -Path conditional-job-trigger -DestinationPath conditional-job-trigger.zip
```

### Step 2: Get EC2 Connection Details

```bash
# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "EC2 IP: $PUBLIC_IP"
```

### Step 3: Upload Package to EC2

**Using SCP:**
```bash
# Linux/Mac/WSL
scp -i /path/to/your-key.pem \
    conditional-job-trigger.tar.gz \
    ec2-user@$PUBLIC_IP:/tmp/

# Windows (use full path)
scp -i C:\path\to\your-key.pem ^
    conditional-job-trigger.zip ^
    ec2-user@PUBLIC_IP:/tmp/
```

**Using AWS Session Manager (if SSM enabled):**
```bash
# Upload via S3 intermediate
aws s3 cp conditional-job-trigger.tar.gz s3://your-bucket/
aws ssm send-command \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name "AWS-RunShellScript" \
    --parameters 'commands=["aws s3 cp s3://your-bucket/conditional-job-trigger.tar.gz /tmp/"]'
```

### Step 4: Connect to EC2

```bash
# Direct SSH
ssh -i /path/to/your-key.pem ec2-user@$PUBLIC_IP

# Or using Session Manager
aws ssm start-session \
    --target i-0a71309ab193e7992 \
    --region ap-south-1
```

### Step 5: Build Plugin on EC2

```bash
# Once connected to EC2 instance:

# Extract package
cd /tmp
tar -xzf conditional-job-trigger.tar.gz  # or unzip conditional-job-trigger.zip
cd conditional-job-trigger

# Make gradlew executable
chmod +x gradlew

# Check Gradle version
./gradlew --version

# Build plugin (without tests due to dependency)
./gradlew clean build -x test

# Verify JAR was created
ls -lh build/libs/
# Should show: conditional-job-trigger-0.1.0.jar
```

### Step 6: Install Plugin to Rundeck

```bash
# Find Rundeck base directory
RDECK_BASE="${RDECK_BASE:-/var/lib/rundeck}"
echo "Rundeck base: $RDECK_BASE"

# Create libext directory if it doesn't exist
sudo mkdir -p $RDECK_BASE/libext

# Copy plugin JAR
sudo cp build/libs/conditional-job-trigger-0.1.0.jar $RDECK_BASE/libext/

# Set permissions
sudo chown rundeck:rundeck $RDECK_BASE/libext/conditional-job-trigger-0.1.0.jar

# Verify
ls -lh $RDECK_BASE/libext/conditional-job-trigger-0.1.0.jar
```

### Step 7: Restart Rundeck

```bash
# Using service command
sudo service rundeckd restart

# Or using systemd
sudo systemctl restart rundeckd

# Check status
sudo service rundeckd status
# or
sudo systemctl status rundeckd
```

### Step 8: Verify Plugin Loaded

```bash
# Watch Rundeck logs for plugin loading
tail -f /var/log/rundeck/service.log | grep -i conditional

# Or check for plugin in logs
grep -i "conditional.*trigger" /var/log/rundeck/service.log

# Should see something like:
# [timestamp] INFO  PluginRegistry - Loaded plugin: conditional-job-trigger
```

---

## Option 3: Quick Copy-Paste Commands

```bash
# === RUN ON YOUR LOCAL MACHINE ===

# 1. Package plugin
cd examples/custom-plugins
tar -czf conditional-job-trigger.tar.gz conditional-job-trigger/

# 2. Get EC2 IP
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids i-0a71309ab193e7992 --region ap-south-1 --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)

# 3. Upload (replace YOUR_KEY.pem)
scp -i ~/.ssh/YOUR_KEY.pem conditional-job-trigger.tar.gz ec2-user@$PUBLIC_IP:/tmp/

# 4. SSH to EC2
ssh -i ~/.ssh/YOUR_KEY.pem ec2-user@$PUBLIC_IP

# === RUN ON EC2 INSTANCE ===

# 5. Extract and build
cd /tmp
tar -xzf conditional-job-trigger.tar.gz
cd conditional-job-trigger
chmod +x gradlew
./gradlew clean build -x test

# 6. Install
sudo cp build/libs/conditional-job-trigger-0.1.0.jar /var/lib/rundeck/libext/
sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar

# 7. Restart
sudo service rundeckd restart

# 8. Verify
tail -50 /var/log/rundeck/service.log | grep -i conditional
```

---

## Troubleshooting

### Issue: Cannot resolve rundeck-core dependency

**Solution:** This is expected. Use `-x test` flag:
```bash
./gradlew clean build -x test
```

### Issue: Permission denied for libext

**Solution:** Use sudo:
```bash
sudo cp build/libs/*.jar /var/lib/rundeck/libext/
sudo chown rundeck:rundeck /var/lib/rundeck/libext/*.jar
```

### Issue: Plugin not appearing in Rundeck UI

**Check:**
```bash
# 1. Verify JAR is in place
ls -lh /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar

# 2. Check logs for errors
tail -100 /var/log/rundeck/service.log

# 3. Verify Rundeck is running
sudo service rundeckd status

# 4. Restart again
sudo service rundeckd restart

# 5. Wait 30 seconds, then check UI
```

### Issue: SSH connection refused

**Solutions:**
1. Check security group allows SSH (port 22)
2. Verify instance is running
3. Try Session Manager instead of direct SSH

---

## Files Created

- `deploy-to-ec2.sh` - Automated deployment script (Linux/Mac)
- `deploy-to-ec2.bat` - Windows deployment script
- `DEPLOYMENT-GUIDE.md` - This file

Choose the method that works best for your environment!
