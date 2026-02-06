# Quick Deploy - Conditional Job Trigger Plugin

## 🚀 One-Command Deployment

### Using Existing S3 Bucket: `rundeck-plugins-dev-512508756184`

**Linux/Mac/WSL:**
```bash
chmod +x deploy-ssm.sh
./deploy-ssm.sh
```

**Windows:**
```cmd
deploy-ssm.bat
```

---

## 📋 What the Script Does

1. ✅ Verifies EC2 instance i-0a71309ab193e7992 is SSM-ready
2. ✅ Packages plugin files locally
3. ✅ Uploads to S3: `s3://rundeck-plugins-dev-512508756184/plugins/`
4. ✅ Downloads to EC2 via SSM command
5. ✅ Builds plugin on EC2: `./gradlew clean build -x test`
6. ✅ Installs to: `/var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar`
7. ✅ Restarts Rundeck service
8. ✅ Keeps package in S3 for backup

---

## ⚡ Alternative: Quick Manual Commands

```bash
# 1. Package locally
cd examples/custom-plugins
tar -czf conditional-job-trigger.tar.gz conditional-job-trigger/

# 2. Upload to your S3 bucket
aws s3 cp conditional-job-trigger.tar.gz \
    s3://rundeck-plugins-dev-512508756184/plugins/ \
    --region ap-south-1

# 3. Download and build on EC2 via SSM
aws ssm send-command \
    --instance-ids i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name "AWS-RunShellScript" \
    --comment "Deploy Conditional Job Trigger Plugin" \
    --parameters 'commands=[
        "cd /tmp && mkdir -p rundeck-plugins && cd rundeck-plugins",
        "aws s3 cp s3://rundeck-plugins-dev-512508756184/plugins/conditional-job-trigger.tar.gz . --region ap-south-1",
        "tar -xzf conditional-job-trigger.tar.gz",
        "cd conditional-job-trigger",
        "chmod +x gradlew",
        "./gradlew clean build -x test",
        "sudo cp build/libs/conditional-job-trigger-0.1.0.jar /var/lib/rundeck/libext/",
        "sudo chown rundeck:rundeck /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar",
        "sudo service rundeckd restart"
    ]'
```

---

## 🔍 Verify Deployment

```bash
# Start SSM session
aws ssm start-session \
    --target i-0a71309ab193e7992 \
    --region ap-south-1

# Then run on EC2:
ls -lh /var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar
tail -50 /var/log/rundeck/service.log | grep -i conditional
```

---

## 📦 Deployment Configuration

- **EC2 Instance**: i-0a71309ab193e7992
- **AWS Region**: ap-south-1
- **S3 Bucket**: rundeck-plugins-dev-512508756184
- **S3 Path**: `s3://rundeck-plugins-dev-512508756184/plugins/`
- **Plugin JAR**: conditional-job-trigger-0.1.0.jar
- **Install Path**: /var/lib/rundeck/libext/

---

## 🎯 Expected Result

After successful deployment:

1. **Plugin JAR** installed at `/var/lib/rundeck/libext/conditional-job-trigger-0.1.0.jar`
2. **Rundeck restarted** and plugin loaded
3. **Available in UI** under "Add Step" → "Conditional Job Trigger"
4. **Backup in S3** at `s3://rundeck-plugins-dev-512508756184/plugins/conditional-job-trigger-TIMESTAMP.tar.gz`

---

## 💡 Pro Tips

**View SSM Command Output:**
```bash
# Get the command ID from send-command output, then:
aws ssm get-command-invocation \
    --command-id COMMAND_ID_HERE \
    --instance-id i-0a71309ab193e7992 \
    --region ap-south-1 \
    --output text
```

**Port Forward Rundeck UI:**
```bash
aws ssm start-session \
    --target i-0a71309ab193e7992 \
    --region ap-south-1 \
    --document-name AWS-StartPortForwardingSession \
    --parameters '{"portNumber":["4440"],"localPortNumber":["8080"]}'

# Access at: http://localhost:8080
```

**List Files in S3:**
```bash
aws s3 ls s3://rundeck-plugins-dev-512508756184/plugins/ --region ap-south-1
```

---

## ✅ Ready to Deploy!

Just run:
```bash
./deploy-ssm.sh
```

The entire deployment takes about 1-2 minutes.
