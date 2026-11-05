# Lab 8, Part 4. Off by default; a pull request that sets lab8_stream_enabled in
# terraform.tfvars creates the pipeline on merge, and the next one removes it.

module "lab8_stream" {
  count  = var.lab8_stream_enabled ? 1 : 0
  source = "./lab8"

  name        = "${var.project_name}-lab8-payments"
  bucket      = "${var.project_name}-lab8-${local.account_id}"
  alert_email = var.budget_email
}
