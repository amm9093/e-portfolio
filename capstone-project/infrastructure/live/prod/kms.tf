# Customer-managed key for patient-identifiable data.
# The key policy lets IAM policies in this account control use of the key,
# and lets CloudWatch Logs encrypt this account's log groups with it.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_iam_policy_document" "phi_key" {
  # In a KMS key policy, "*" means "this key" and kms:* for the account root
  # is AWS's documented default that delegates control to IAM policies.
  # checkov:skip=CKV_AWS_111:Key policy resource "*" refers to this key only.
  # checkov:skip=CKV_AWS_356:Key policy resource "*" refers to this key only.
  # checkov:skip=CKV_AWS_109:Root delegation is the AWS default key policy; access is then limited by IAM.
  statement {
    sid       = "AccountAdministersKeyThroughIAM"
    actions   = ["kms:*"]
    resources = ["*"]
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"]
    }
  }

  statement {
    sid = "AllowCloudWatchLogs"
    actions = [
      "kms:Encrypt*",
      "kms:Decrypt*",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:Describe*",
    ]
    resources = ["*"]
    principals {
      type        = "Service"
      identifiers = ["logs.${data.aws_region.current.name}.amazonaws.com"]
    }
    condition {
      test     = "ArnLike"
      variable = "kms:EncryptionContext:aws:logs:arn"
      values   = ["arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"]
    }
  }
}

resource "aws_kms_key" "phi" {
  description             = "CMK for patient-identifiable data (${var.environment})"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.phi_key.json
}

resource "aws_kms_alias" "phi" {
  name          = "alias/${var.environment}-phi"
  target_key_id = aws_kms_key.phi.key_id
}
