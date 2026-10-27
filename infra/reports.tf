# Peach weekly report (Lab 5; was infra/reports.yaml), built by events. Every
# Monday at 07:00 Kyiv time the schedule puts a command on the report-requests
# queue; the builder (the API's image, in the API's VPC) reads the database and
# writes reports/<week>.csv through an S3 gateway endpoint; the new object is
# an event that starts the mailer (outside the VPC), which emails the file
# through SES. Neither function calls the other.
#
# The IAM role names and permission statement ids below are the ones
# CloudFormation generated. They stay as they are: a new name is a new
# resource, and these were imported, not re-created.

locals {
  reports_bucket = "${var.project_name}-reports-${local.account_id}"

  report_sender_address = var.report_sender_address != "" ? var.report_sender_address : (
    var.mail_domain != "" ? "reports@${var.mail_domain}" : ""
  )
  report_sender = local.report_sender_address != "" ? "${var.report_sender_name} <${local.report_sender_address}>" : ""
}

# --- network -----------------------------------------------------------------

# Free, unlike an interface endpoint or a NAT gateway: a route to S3 in the
# subnets' route table. Without it the builder's PutObject hangs until the
# timeout, because with no NAT the request has nowhere to go.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = data.aws_lambda_function.backend.vpc_config[0].vpc_id
  service_name      = "com.amazonaws.${local.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [data.aws_route_table.main.id]
}

# --- queue -------------------------------------------------------------------

# max_message_size: SQS's own default since 2025 is 1 MiB; the provider still
# defaults to the old 256 KiB and would shrink the queues without it.

resource "aws_sqs_queue" "report_requests_dlq" {
  name                      = "${var.project_name}-report-requests-dlq"
  message_retention_seconds = 1209600 # 14 days, the most SQS keeps anything
  max_message_size          = 1048576
}

resource "aws_sqs_queue" "report_requests" {
  name             = "${var.project_name}-report-requests"
  max_message_size = 1048576

  # Six times the builder's 60 s timeout. Shorter, and a message becomes
  # visible again while its first attempt is still running - a second builder
  # then starts on the same report.
  visibility_timeout_seconds = 360

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.report_requests_dlq.arn
    maxReceiveCount     = 3
  })
}

# --- trigger 1: the schedule -------------------------------------------------

resource "aws_iam_role" "scheduler" {
  name = "${var.project_name}-reports-SchedulerRole-OKsEShkgbrFe"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
      Condition = { StringEquals = { "aws:SourceAccount" = local.account_id } }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "send-report-requests"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sqs:SendMessage"
      Resource = aws_sqs_queue.report_requests.arn
    }]
  })
}

resource "aws_scheduler_schedule" "weekly" {
  name        = "${var.project_name}-weekly-report"
  description = "Asks for last week's report every Monday morning."

  schedule_expression = var.report_schedule
  # Without it the cron runs in UTC, and the report arrives at 09:00 or 10:00
  # depending on daylight saving time.
  schedule_expression_timezone = "Europe/Kyiv"
  state                        = "ENABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_sqs_queue.report_requests.arn
    role_arn = aws_iam_role.scheduler.arn
    # A command with no week: the builder takes the last complete one. A
    # literal string, byte for byte the one the schedule already has.
    input = "{\"week\": null, \"source\": \"schedule\"}"
  }
}

# --- trigger 2: the builder, fed by the queue --------------------------------

resource "aws_iam_role" "builder" {
  name = "${var.project_name}-reports-BuilderRole-jvSSpFf4tVPF"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "builder_vpc" {
  role       = aws_iam_role.builder.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "builder" {
  name = "build-reports"
  role = aws_iam_role.builder.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Lambda polls the queue on the function's behalf, with these
      # permissions: the function itself never connects to SQS, which is why
      # it works from a VPC with no NAT.
      {
        Sid    = "ConsumeRequests"
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:ChangeMessageVisibility",
        ]
        Resource = aws_sqs_queue.report_requests.arn
      },
      {
        Sid      = "WriteReports"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "arn:aws:s3:::${local.reports_bucket}/reports/*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "builder" {
  name              = "/aws/lambda/${var.project_name}-report-builder"
  retention_in_days = var.report_log_retention_days
}

resource "aws_lambda_function" "builder" {
  function_name = "${var.project_name}-report-builder"
  description   = "Builds reports/<week>.csv from the database."
  role          = aws_iam_role.builder.arn

  # The API's image, so the models and database code come for free.
  package_type  = "Image"
  image_uri     = local.backend_image
  architectures = [local.backend_architecture]
  memory_size   = 512
  timeout       = 60

  image_config {
    command = ["app.reports.lambda_handler.handler"]
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.builder.name
  }

  vpc_config {
    subnet_ids         = data.aws_lambda_function.backend.vpc_config[0].subnet_ids
    security_group_ids = data.aws_lambda_function.backend.vpc_config[0].security_group_ids
  }

  environment {
    variables = {
      APP_ENV           = "production"
      DB_POOLING        = "false"
      DATABASE_URL      = data.aws_secretsmanager_secret_version.database_url.secret_string
      REPORTS_BUCKET    = local.reports_bucket
      REPORTS_FAIL_WEEK = var.report_fail_week
    }
  }

  # The code is the application's road: scripts/deploy-backend.sh moves this
  # function to every new API image. Terraform owns everything else about it.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

# One message per invocation: a failure retries one report, not a batch.
resource "aws_lambda_event_source_mapping" "builder" {
  function_name    = aws_lambda_function.builder.arn
  event_source_arn = aws_sqs_queue.report_requests.arn
  batch_size       = 1
}

# --- trigger 3: a file in S3 starts the mailer -------------------------------

resource "aws_iam_role" "mailer" {
  name = "${var.project_name}-reports-MailerRole-dEUQICmVV41m"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "mailer_logs" {
  role       = aws_iam_role.mailer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "mailer" {
  name = "mail-reports"
  role = aws_iam_role.mailer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Read only: a function triggered by uploads to reports/ that could write
      # there would call itself forever.
      {
        Sid      = "ReadReports"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "arn:aws:s3:::${local.reports_bucket}/reports/*"
      },
      {
        Sid      = "SendEmail"
        Effect   = "Allow"
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Resource = "arn:aws:ses:${local.region}:${local.account_id}:identity/*"
      },
    ]
  })
}

resource "aws_cloudwatch_log_group" "mailer" {
  name              = "/aws/lambda/${var.project_name}-report-mailer"
  retention_in_days = var.report_log_retention_days
}

# Outside the VPC: SES is on the internet. The same image with a handler that
# needs only the standard library and boto3, so it is tested with the rest.
resource "aws_lambda_function" "mailer" {
  function_name = "${var.project_name}-report-mailer"
  description   = "Emails each new report through SES."
  role          = aws_iam_role.mailer.arn

  package_type  = "Image"
  image_uri     = local.backend_image
  architectures = [local.backend_architecture]
  memory_size   = 256
  timeout       = 30

  image_config {
    command = ["app.reports.mailer.handler"]
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.mailer.name
  }

  environment {
    variables = {
      REPORT_SENDER     = local.report_sender
      REPORT_RECIPIENTS = var.report_recipients
    }
  }

  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_permission" "mailer_s3" {
  statement_id   = "${var.project_name}-reports-MailerInvokePermission-jCO8nooxKwcI"
  function_name  = aws_lambda_function.mailer.function_name
  action         = "lambda:InvokeFunction"
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.reports.arn
  source_account = local.account_id
}

# --- storage -----------------------------------------------------------------

# Every report ever built is in here: renaming the bucket replaces it, and an
# apply would then try to delete a bucket full of reports.
resource "aws_s3_bucket" "reports" {
  bucket = local.reports_bucket

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket = aws_s3_bucket.reports.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    id     = "expire-reports"
    status = "Enabled"

    filter {
      prefix = "reports/"
    }

    expiration {
      days = 90
    }
  }
}

# A resource of its own in Terraform, so Lab 5's circular dependency is gone:
# bucket, then permission, then this. No name has to be known in advance.
resource "aws_s3_bucket_notification" "reports" {
  bucket = aws_s3_bucket.reports.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.mailer.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "reports/"
    filter_suffix       = ".csv"
  }

  depends_on = [aws_lambda_permission.mailer_s3]
}

# --- email -------------------------------------------------------------------

# Easy DKIM: three CNAMEs at the DNS provider, then Verified in minutes.
resource "aws_sesv2_email_identity" "mail" {
  count = var.mail_domain != "" ? 1 : 0

  email_identity = var.mail_domain
}
