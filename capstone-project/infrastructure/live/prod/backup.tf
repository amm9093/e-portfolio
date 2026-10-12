# Immutable backups with an encrypted copy in the EU (Ireland) Region
# (report: "Key design decisions" and "Regulatory landscape"). Vault Lock stops anyone - including an
# attacker with administrator rights - deleting recovery points early.

# Separate key in the DR region; KMS keys are regional.
data "aws_iam_policy_document" "dr_key" {
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
}

resource "aws_kms_key" "dr" {
  provider                = aws.dr
  description             = "CMK for DR backup copies (${var.environment})"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  policy                  = data.aws_iam_policy_document.dr_key.json
}

resource "aws_backup_vault" "primary" {
  name        = "${local.name}-primary"
  kms_key_arn = aws_kms_key.phi.arn
}

resource "aws_backup_vault" "dr" {
  provider    = aws.dr
  name        = "${local.name}-dr"
  kms_key_arn = aws_kms_key.dr.arn
}

# Governance-to-compliance cooling-off: changeable_for_days gives a window
# to test before the lock becomes permanent. Remove it only after review.
resource "aws_backup_vault_lock_configuration" "primary" {
  backup_vault_name   = aws_backup_vault.primary.name
  min_retention_days  = 7
  max_retention_days  = 400
  changeable_for_days = 3
}

resource "aws_backup_vault_lock_configuration" "dr" {
  provider            = aws.dr
  backup_vault_name   = aws_backup_vault.dr.name
  min_retention_days  = 7
  max_retention_days  = 400
  changeable_for_days = 3
}

resource "aws_backup_plan" "tier1" {
  name = "${local.name}-tier1"

  rule {
    rule_name         = "daily-with-dr-copy"
    target_vault_name = aws_backup_vault.primary.name
    schedule          = "cron(0 1 * * ? *)" # 01:00 UTC daily

    lifecycle {
      delete_after = 35
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.dr.arn
      lifecycle {
        delete_after = 90
      }
    }
  }
}

data "aws_iam_policy_document" "backup_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["backup.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backup" {
  name               = "${local.name}-backup"
  assume_role_policy = data.aws_iam_policy_document.backup_assume.json
}

resource "aws_iam_role_policy_attachment" "backup" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBackupServiceRolePolicyForBackup"
}

# Anything tagged backup_tier = "1" is protected by this plan.
resource "aws_backup_selection" "tier1" {
  name         = "${local.name}-tier1"
  plan_id      = aws_backup_plan.tier1.id
  iam_role_arn = aws_iam_role.backup.arn

  selection_tag {
    type  = "STRINGEQUALS"
    key   = "backup_tier"
    value = "1"
  }
}
