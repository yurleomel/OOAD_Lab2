# Non-secret values only. google_client_secret, report_sender_address,
# report_recipients and budget_email are sensitive variables in the HCP
# Terraform workspace.

project_name     = "peach"
region           = "us-east-1"
google_client_id = "861082373462-psqd84mduprvthulmvgspd4j6db93sf3.apps.googleusercontent.com"
mail_domain      = "mylanora.world"

# Two weeks of builder and mailer logs: a Monday report that failed can still
# be read on the next Monday.
report_log_retention_days = 14
