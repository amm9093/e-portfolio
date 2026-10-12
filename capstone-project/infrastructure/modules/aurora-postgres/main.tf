# Aurora PostgreSQL across three Availability Zones (report: "Target architecture").
# The master password is generated and rotated by AWS Secrets Manager, so it
# never appears in code, in the pipeline logs or in the Terraform state.

resource "aws_security_group" "db" {
  name        = "${var.name}-db"
  description = "Aurora ${var.name}: PostgreSQL from approved application security groups only"
  vpc_id      = var.vpc_id
}

# count (not for_each) because the security group IDs are usually created in
# the same run and are unknown at plan time; only the list length is known.
resource "aws_vpc_security_group_ingress_rule" "from_apps" {
  count                        = length(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.db.id
  description                  = "PostgreSQL from approved application security group"
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}

# Log slow queries and connections, but NOT every statement: full statement
# logging would copy patient data into the logs (a data protection risk).
resource "aws_rds_cluster_parameter_group" "this" {
  name        = "${var.name}-params"
  family      = "aurora-postgresql${split(".", var.engine_version)[0]}"
  description = "Logging settings for ${var.name}"

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # ms: log queries slower than 1 second
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }
}

# Enhanced Monitoring: OS-level metrics every 60 seconds.
data "aws_iam_policy_document" "monitoring_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["monitoring.rds.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "monitoring" {
  name               = "${var.name}-rds-monitoring"
  assume_role_policy = data.aws_iam_policy_document.monitoring_assume.json
}

resource "aws_iam_role_policy_attachment" "monitoring" {
  role       = aws_iam_role.monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

resource "aws_rds_cluster" "this" {
  # checkov:skip=CKV2_AWS_8:Covered by the tag-based AWS Backup plan in live/prod/backup.tf (backup_tier = "1"), which Checkov cannot trace.
  # checkov:skip=CKV2_AWS_27:Full statement logging is deliberately off - it would write patient data to logs. Slow queries and connections are logged instead.
  cluster_identifier = var.name

  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.this.name

  engine          = "aurora-postgresql"
  engine_version  = var.engine_version
  database_name   = var.database_name
  master_username = var.master_username

  manage_master_user_password   = true
  master_user_secret_kms_key_id = var.kms_key_arn

  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [aws_security_group.db.id]

  storage_encrypted                   = true
  kms_key_id                          = var.kms_key_arn
  iam_database_authentication_enabled = true

  backup_retention_period      = var.backup_retention_days
  preferred_backup_window      = "02:00-03:00"
  preferred_maintenance_window = "sun:03:30-sun:04:30"
  copy_tags_to_snapshot        = true

  deletion_protection       = var.deletion_protection
  skip_final_snapshot       = false
  final_snapshot_identifier = "${var.name}-final"

  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Picked up by the tier-1 AWS Backup plan (live/prod/backup.tf).
  tags = {
    backup_tier = var.backup_tier
  }
}

# One instance per AZ: a writer plus readers that can be promoted on failure.
resource "aws_rds_cluster_instance" "this" {
  count = var.instance_count

  identifier         = "${var.name}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.this.id
  instance_class     = var.instance_class
  engine             = aws_rds_cluster.this.engine
  engine_version     = aws_rds_cluster.this.engine_version

  auto_minor_version_upgrade            = true
  performance_insights_enabled          = true
  performance_insights_kms_key_id       = var.kms_key_arn
  performance_insights_retention_period = 7
  publicly_accessible                   = false

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.monitoring.arn
}
