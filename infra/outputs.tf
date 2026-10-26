# What the Makefile, scripts/infra-env.sh and the frontend build read, with
# `terraform -chdir=infra output -raw <name>`. None of these is secret: the
# frontend compiles the pool ids and the parser URL into its bundle.

# --- sign-in -----------------------------------------------------------------

output "cognito_region" {
  value = local.region
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_domain" {
  value = "${aws_cognito_user_pool_domain.main.domain}.auth.${local.region}.amazoncognito.com"
}

output "cognito_google_enabled" {
  value = tostring(local.google_enabled)
}

output "google_redirect_uri" {
  description = "The authorised redirect URI to register on the Google OAuth client."
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${local.region}.amazoncognito.com/oauth2/idpresponse"
}

# --- weekly report -----------------------------------------------------------

output "reports_bucket" {
  value = aws_s3_bucket.reports.bucket
}

output "report_queue_url" {
  value = aws_sqs_queue.report_requests.url
}

output "report_dlq_url" {
  value = aws_sqs_queue.report_requests_dlq.url
}

output "report_schedule_name" {
  value = aws_scheduler_schedule.weekly.name
}

output "mail_dkim_records" {
  description = "The three CNAMEs SES wants at the DNS provider: name, then value."
  value = [
    for token in try(aws_sesv2_email_identity.mail[0].dkim_signing_attributes[0].tokens, []) :
    "${token}._domainkey.${var.mail_domain} ${token}.dkim.amazonses.com"
  ]
}

# --- agenda parser -----------------------------------------------------------

output "parser_url" {
  description = "The function URL, with no trailing slash. The site posts to it."
  value       = trimsuffix(aws_lambda_function_url.parser.function_url, "/")
}

output "parser_function_name" {
  value = aws_lambda_function.parser.function_name
}

output "budget_name" {
  value = one(aws_budgets_budget.monthly[*].name)
}
