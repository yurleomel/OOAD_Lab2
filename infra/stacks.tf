# What the stacks that stay in CloudFormation already have. The backend
# (network, database, API function) and the site are still deployed by
# scripts/deploy-backend.sh and deploy-frontend.sh; Terraform only reads them.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_cloudformation_stack" "backend" {
  name = "${var.project_name}-backend"
}

data "aws_cloudformation_stack" "frontend" {
  name = "${var.project_name}-frontend"
}

# The report functions and the parser run the API's image with other handlers,
# on the API's architecture; the builder also joins its subnets and security
# group, which the database admits.
data "aws_lambda_function" "backend" {
  function_name = data.aws_cloudformation_stack.backend.outputs["FunctionName"]
}

data "aws_secretsmanager_secret_version" "database_url" {
  secret_id = data.aws_cloudformation_stack.backend.outputs["DatabaseUrlSecretArn"]
}

# The backend's subnets have no route tables of their own, so they use the
# VPC's main one; the S3 gateway endpoint adds its route there.
data "aws_route_table" "main" {
  vpc_id = data.aws_lambda_function.backend.vpc_config[0].vpc_id

  filter {
    name   = "association.main"
    values = ["true"]
  }
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region

  backend_image        = data.aws_lambda_function.backend.image_uri
  backend_architecture = data.aws_lambda_function.backend.architectures[0]

  site_url        = trimsuffix(data.aws_cloudformation_stack.frontend.outputs["SiteUrl"], "/")
  cloudfront_url  = "https://${data.aws_cloudformation_stack.frontend.outputs["DistributionDomainName"]}"
  site_origins    = distinct([var.local_site_url, local.site_url])
  browser_origins = distinct([var.local_site_url, local.site_url, local.cloudfront_url])
}
