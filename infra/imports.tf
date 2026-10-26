# Adopt what the three CloudFormation stacks created, instead of creating a
# second copy. Each id is the one the provider's docs ask for at the bottom of
# the resource's page. Delete this file once the import is applied.

# --- peach-cognito -----------------------------------------------------------

import {
  to = aws_cognito_user_pool.main
  id = "us-east-1_qEVU77JkT"
}

import {
  to = aws_cognito_identity_provider.google[0]
  id = "us-east-1_qEVU77JkT:Google"
}

import {
  to = aws_cognito_user_pool_client.web
  id = "us-east-1_qEVU77JkT/5lueqqm1cce5n1kempbtt51huk"
}

import {
  to = aws_cognito_user_pool_domain.main
  id = "peach-308224965217"
}

import {
  to = aws_cognito_managed_login_branding.web
  id = "us-east-1_qEVU77JkT,32049d91-bb4b-48a5-bf34-9b230ff39842"
}

# --- peach-reports -----------------------------------------------------------

import {
  to = aws_vpc_endpoint.s3
  id = "vpce-07086bcbbe01c7c14"
}

import {
  to = aws_sqs_queue.report_requests_dlq
  id = "https://sqs.us-east-1.amazonaws.com/308224965217/peach-report-requests-dlq"
}

import {
  to = aws_sqs_queue.report_requests
  id = "https://sqs.us-east-1.amazonaws.com/308224965217/peach-report-requests"
}

import {
  to = aws_iam_role.scheduler
  id = "peach-reports-SchedulerRole-OKsEShkgbrFe"
}

import {
  to = aws_iam_role_policy.scheduler
  id = "peach-reports-SchedulerRole-OKsEShkgbrFe:send-report-requests"
}

import {
  to = aws_scheduler_schedule.weekly
  id = "default/peach-weekly-report"
}

import {
  to = aws_iam_role.builder
  id = "peach-reports-BuilderRole-jvSSpFf4tVPF"
}

import {
  to = aws_iam_role_policy_attachment.builder_vpc
  id = "peach-reports-BuilderRole-jvSSpFf4tVPF/arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

import {
  to = aws_iam_role_policy.builder
  id = "peach-reports-BuilderRole-jvSSpFf4tVPF:build-reports"
}

import {
  to = aws_cloudwatch_log_group.builder
  id = "/aws/lambda/peach-report-builder"
}

import {
  to = aws_lambda_function.builder
  id = "peach-report-builder"
}

import {
  to = aws_lambda_event_source_mapping.builder
  id = "e7a68fef-da24-4f71-ba73-3afb9b2cbbf5"
}

import {
  to = aws_iam_role.mailer
  id = "peach-reports-MailerRole-dEUQICmVV41m"
}

import {
  to = aws_iam_role_policy_attachment.mailer_logs
  id = "peach-reports-MailerRole-dEUQICmVV41m/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

import {
  to = aws_iam_role_policy.mailer
  id = "peach-reports-MailerRole-dEUQICmVV41m:mail-reports"
}

import {
  to = aws_cloudwatch_log_group.mailer
  id = "/aws/lambda/peach-report-mailer"
}

import {
  to = aws_lambda_function.mailer
  id = "peach-report-mailer"
}

import {
  to = aws_lambda_permission.mailer_s3
  id = "peach-report-mailer/peach-reports-MailerInvokePermission-jCO8nooxKwcI"
}

import {
  to = aws_s3_bucket.reports
  id = "peach-reports-308224965217"
}

import {
  to = aws_s3_bucket_public_access_block.reports
  id = "peach-reports-308224965217"
}

import {
  to = aws_s3_bucket_ownership_controls.reports
  id = "peach-reports-308224965217"
}

import {
  to = aws_s3_bucket_server_side_encryption_configuration.reports
  id = "peach-reports-308224965217"
}

import {
  to = aws_s3_bucket_lifecycle_configuration.reports
  id = "peach-reports-308224965217"
}

import {
  to = aws_s3_bucket_notification.reports
  id = "peach-reports-308224965217"
}

import {
  to = aws_sesv2_email_identity.mail[0]
  id = "mylanora.world"
}

# --- peach-ai ----------------------------------------------------------------

import {
  to = aws_iam_role.parser
  id = "peach-ai-ParserRole-XrcGHj7phTtQ"
}

import {
  to = aws_iam_role_policy_attachment.parser_logs
  id = "peach-ai-ParserRole-XrcGHj7phTtQ/arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

import {
  to = aws_iam_role_policy.parser
  id = "peach-ai-ParserRole-XrcGHj7phTtQ:call-bedrock"
}

import {
  to = aws_cloudwatch_log_group.parser
  id = "/aws/lambda/peach-agenda-parser"
}

import {
  to = aws_lambda_function.parser
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_function_url.parser
  id = "peach-agenda-parser"
}

import {
  to = aws_lambda_permission.parser_url
  id = "peach-agenda-parser/peach-ai-ParserUrlPermission-TPpSVWgQXm3s"
}

import {
  to = aws_lambda_permission.parser_url_invoke
  id = "peach-agenda-parser/peach-ai-ParserUrlInvokePermission-e8feQcKLoBqe"
}

import {
  to = aws_budgets_budget.monthly[0]
  id = "308224965217:peach-monthly"
}
