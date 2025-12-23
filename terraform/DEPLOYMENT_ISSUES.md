# Terraform Deployment Trial Run - Issues Found

**Date:** December 22, 2025

## Summary

The Terraform deployment script successfully provisions AWS infrastructure, but the application fails to start due to several issues discovered during the trial run.

---

## Issues Found

### Issue #1: Terraform Not Pre-Installed
**Status:** Resolved
**Description:** Terraform was not installed on the development machine.
**Fix:** Installed via binary download to `~/bin/terraform`.
**Action:** Add Terraform to deploy.sh prerequisites check (already done).

---

### Issue #2: Terraform `$$` Variable Escaping
**Status:** Resolved
**Description:** Shell command substitution (`$(command)`) was being incorrectly processed by Terraform's templatefile function. Using `$$` for escaping caused bash to interpret it as PID.
**Fix:** Rewrote user_data.sh to avoid complex escaping - used static URLs and shell variables only where needed.
**Lesson:** Keep user_data scripts simple; avoid mixing Terraform interpolation with shell command substitution.

---

### Issue #3: EBS Volume Size Too Small
**Status:** Resolved
**Description:** Amazon Linux 2023 AMI requires minimum 30GB root volume, but Terraform specified 20GB.
**Error:** `InvalidBlockDeviceMapping: Volume of size 20GB is smaller than snapshot, expect size >= 30GB`
**Fix:** Updated `main.tf` to use 30GB.

---

### Issue #4: Docker Compose Installation Command
**Status:** Resolved
**Description:** Original script used dynamic URL with `$(uname -s)-$(uname -m)` which failed due to escaping issues.
**Fix:** Changed to static URL for `docker-compose-linux-x86_64` v2.32.4.
**Note:** Also switched from `docker-compose` (v1) to `docker compose` (v2) command.

---

### Issue #5: Private GitHub Repository ⚠️ BLOCKING
**Status:** UNRESOLVED
**Description:** The user_data script tries to clone `https://github.com/jenbrannstrom/rtbcat-platform.git` but the repository is private.
**Error:** `fatal: could not read Username for 'https://github.com': No such device or address`

**Options to fix:**

1. **Make Repository Public** (Simplest)
   - Go to GitHub repo settings → Make public
   - Pros: No code changes needed
   - Cons: Source code visible to everyone

2. **Use GitHub Deploy Key** (Recommended for private repos)
   - Generate SSH key pair
   - Add public key to GitHub as deploy key
   - Store private key in AWS Secrets Manager
   - Update user_data to fetch key and use SSH clone
   - Pros: Repo stays private, secure
   - Cons: More complex setup

3. **Bundle Code to S3**
   - Create a build step that zips the repo
   - Upload to S3 bucket
   - Download in user_data from S3
   - Pros: No GitHub auth needed, faster
   - Cons: Need to update S3 on each deploy

4. **Custom AMI**
   - Build an AMI with code pre-installed using Packer
   - Pros: Fastest startup, no clone step
   - Cons: Need to rebuild AMI for code changes

---

## Infrastructure Successfully Created

Despite the app not starting, the following AWS resources were successfully provisioned:

| Resource | ID/Name |
|----------|---------|
| EC2 Instance | `i-0d8947a91d9069bf3` (t3.small) |
| Elastic IP | `18.185.146.184` |
| Security Group | `sg-0335b5ac3bb34cee5` |
| S3 Bucket | `catscan-production-data-b18d05c7` |
| IAM Role | `catscan-production-role` |

---

## Cost While Debugging

Current resources running:
- EC2 t3.small: ~$0.02/hour ($0.50/day)
- EBS 30GB gp3: ~$0.003/hour ($0.07/day)
- Elastic IP: Free (attached to running instance)

**Recommendation:** Run `terraform destroy` to stop costs if not actively testing.

---

## Next Steps

1. Choose approach for Issue #5 (recommend: make repo public for trial)
2. Update user_data.sh with chosen approach
3. Redeploy with `terraform apply`
4. Verify services start correctly
5. Test dashboard and API endpoints

---

## Commands Reference

```bash
# Check deployment status
cd /home/jen/Documents/rtbcat-platform/terraform
~/bin/terraform output

# View EC2 console logs
aws ec2 get-console-output --region eu-central-1 --instance-id i-0d8947a91d9069bf3 --latest --query 'Output' --output text

# Destroy all resources (stop costs)
~/bin/terraform destroy

# Redeploy after fixing
~/bin/terraform plan -out=tfplan
~/bin/terraform apply tfplan
```
