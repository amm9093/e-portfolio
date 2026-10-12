# Organisation guardrails as code (report: "Terraform implementation", Snippet 4).
# Service control policies set limits that no account administrator can
# override. Must be applied from the AWS Organizations management account.

data "aws_iam_policy_document" "guardrails" {
  # 1. Data residency: block regional services outside approved regions.
  #    Global services (IAM, CloudFront, Route 53, ...) are exempt because
  #    they are not tied to a region. List abridged; extend as needed.
  statement {
    sid    = "DenyOutsideApprovedRegions"
    effect = "Deny"
    not_actions = [
      "iam:*", "organizations:*", "sts:*", "support:*",
      "cloudfront:*", "route53:*", "wafv2:*", "budgets:*",
      "ce:*", "health:*", "trustedadvisor:*",
    ]
    resources = ["*"]
    condition {
      test     = "StringNotEquals"
      variable = "aws:RequestedRegion"
      values   = var.approved_regions
    }
  }

  # 2. Stop anyone switching off audit logging or threat detection,
  #    a common first step in ransomware attacks.
  statement {
    sid    = "ProtectAuditAndDetection"
    effect = "Deny"
    actions = [
      "cloudtrail:StopLogging",
      "cloudtrail:DeleteTrail",
      "cloudtrail:UpdateTrail",
      "guardduty:DeleteDetector",
      "guardduty:DisassociateFromMasterAccount",
      "config:StopConfigurationRecorder",
      "config:DeleteConfigurationRecorder",
      "securityhub:DisableSecurityHub",
    ]
    resources = ["*"]
  }

  # 3. No account may leave the organisation (and its guardrails).
  statement {
    sid       = "DenyLeaveOrganization"
    effect    = "Deny"
    actions   = ["organizations:LeaveOrganization"]
    resources = ["*"]
  }

  # 4. Never allow S3 public access settings to be loosened.
  statement {
    sid    = "ProtectS3PublicAccessBlock"
    effect = "Deny"
    actions = [
      "s3:PutAccountPublicAccessBlock",
      "s3:DeleteAccountPublicAccessBlock",
    ]
    resources = ["*"]
  }
}

resource "aws_organizations_policy" "guardrails" {
  name        = "${var.name_prefix}-baseline-guardrails"
  description = "Region restriction and protection of audit, detection and public-access controls"
  type        = "SERVICE_CONTROL_POLICY"
  content     = data.aws_iam_policy_document.guardrails.json
}

resource "aws_organizations_policy_attachment" "targets" {
  for_each  = toset(var.target_ids)
  policy_id = aws_organizations_policy.guardrails.id
  target_id = each.value
}
