# Lab 8, Part 4: streaming in the cloud. Producer -> Kinesis -> Firehose -> S3,
# and Kinesis -> Lambda -> SNS for the failure alert. All of it exists only while
# the lab runs (a stream is billed by the hour), so the root module switches it
# on and off with lab8_stream_enabled. The bucket, the crawler and the Athena
# tables stay outside: what came through the stream can still be read afterwards.

terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
    archive = {
      source = "hashicorp/archive"
    }
  }
}

variable "name" {
  type = string
}

variable "bucket" {
  type        = string
  description = "The lab's own bucket, created in Part 2."
}

variable "alert_email" {
  type      = string
  sensitive = true
}

# --- the stream ---------------------------------------------------------------

resource "aws_kinesis_stream" "payments" {
  name             = var.name
  retention_period = 24

  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }
}

# --- Firehose: the stream into S3, in files of about a minute -------------------

resource "aws_iam_role" "firehose" {
  name = "${var.name}-firehose"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "firehose" {
  name = "read-stream-write-bucket"
  role = aws_iam_role.firehose.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["kinesis:DescribeStream", "kinesis:GetShardIterator", "kinesis:GetRecords", "kinesis:ListShards"]
        Resource = aws_kinesis_stream.payments.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject",
        ]
        Resource = ["arn:aws:s3:::${var.bucket}", "arn:aws:s3:::${var.bucket}/payments-stream*"]
      },
    ]
  })
}

resource "aws_kinesis_firehose_delivery_stream" "payments" {
  name        = var.name
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.payments.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = "arn:aws:s3:::${var.bucket}"
    prefix              = "payments-stream/dt=!{timestamp:yyyy-MM-dd}/"
    error_output_prefix = "payments-stream-errors/!{firehose:error-output-type}/"
    buffering_interval  = 60
    buffering_size      = 5
  }

  # Firehose checks the role's permissions when it is created.
  depends_on = [aws_iam_role_policy.firehose]
}

# --- the alert: Lambda checks each batch, SNS sends the email -------------------

resource "aws_sns_topic" "alerts" {
  name = "${var.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_iam_role" "checker" {
  name = "${var.name}-checker"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "checker_stream" {
  role       = aws_iam_role.checker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaKinesisExecutionRole"
}

resource "aws_iam_role_policy" "checker" {
  name = "publish-alert"
  role = aws_iam_role.checker.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "sns:Publish"
      Resource = aws_sns_topic.alerts.arn
    }]
  })
}

resource "aws_cloudwatch_log_group" "checker" {
  name              = "/aws/lambda/${var.name}-failure-check"
  retention_in_days = 14
}

data "archive_file" "checker" {
  type        = "zip"
  source_file = "${path.module}/failure_check.py"
  output_path = "${path.module}/failure_check.zip"
}

resource "aws_lambda_function" "checker" {
  function_name    = "${var.name}-failure-check"
  description      = "Emails when more than 10% of the payments in a batch failed."
  role             = aws_iam_role.checker.arn
  runtime          = "python3.13"
  handler          = "failure_check.handler"
  filename         = data.archive_file.checker.output_path
  source_code_hash = data.archive_file.checker.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      TOPIC_ARN = aws_sns_topic.alerts.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.checker]
}

resource "aws_lambda_event_source_mapping" "checker" {
  event_source_arn                   = aws_kinesis_stream.payments.arn
  function_name                      = aws_lambda_function.checker.arn
  starting_position                  = "TRIM_HORIZON"
  batch_size                         = 1000
  maximum_batching_window_in_seconds = 60

  # The mapping is refused until the role may read the stream.
  depends_on = [aws_iam_role_policy_attachment.checker_stream]
}
