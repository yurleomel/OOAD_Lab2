# Lanora sign-in (Lab 4; was infra/cognito.yaml): a Cognito user pool (email
# is the username), one public app client for the browser, a managed login
# page on the pool's domain (email + password and Google on one screen), and
# Google as an optional identity provider.

locals {
  google_enabled = var.google_client_id != ""
}

resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-users"

  # Managed login (the v2 hosted page) needs Essentials; the first 10,000
  # monthly active users are free.
  user_pool_tier = "ESSENTIALS"

  # Every account that signed up lives here: renaming the pool or changing
  # how users sign in (username_attributes) replaces it, and the accounts go.
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  username_configuration {
    case_sensitive = false
  }

  # Self sign-up stays on: anyone may create an account.
  admin_create_user_config {
    allow_admin_create_user_only = false
  }

  # Mirrors the sign-up form's own check (PROJECT.md §9).
  password_policy {
    minimum_length                   = 8
    require_numbers                  = true
    require_lowercase                = false
    require_uppercase                = false
    require_symbols                  = false
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your Lanora confirmation code"
    email_message        = "Your Lanora confirmation code is {####}"
  }

  # Cognito's own sender: no SES setup, about 50 emails a day - enough for a
  # course project.
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  deletion_protection = "INACTIVE"

  # A plan that would replace or delete the pool is an error, not a review item.
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_cognito_identity_provider" "google" {
  count = local.google_enabled ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.main.id
  provider_name = "Google"
  provider_type = "Google"

  # Cognito fills in everything after authorize_scopes for a Google provider;
  # written down here, so a plan does not offer to remove it.
  provider_details = {
    client_id                     = var.google_client_id
    client_secret                 = var.google_client_secret
    authorize_scopes              = "openid email profile"
    attributes_url                = "https://people.googleapis.com/v1/people/me?personFields="
    attributes_url_add_attributes = "true"
    authorize_url                 = "https://accounts.google.com/o/oauth2/v2/auth"
    oidc_issuer                   = "https://accounts.google.com"
    token_request_method          = "POST"
    token_url                     = "https://www.googleapis.com/oauth2/v4/token"
  }

  attribute_mapping = {
    email          = "email"
    email_verified = "email_verified"
    name           = "name"
    username       = "sub" # added by Cognito too
  }
}

# Public: it lives in the browser, so it has no secret (generate_secret stays
# unset, which is false; an imported client cannot read it back, and setting it
# would force a new client). The API accepts only ID tokens issued to this
# client (the `aud` claim).
resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.project_name}-web"
  user_pool_id = aws_cognito_user_pool.main.id

  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  # The provider's name, not the literal "Google", so the provider exists first.
  supported_identity_providers = concat(["COGNITO"], aws_cognito_identity_provider.google[*].provider_name)

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  # Each site root gets a callback (sign-in) and a logout URL (sign-out).
  callback_urls = [for url in local.site_origins : "${url}/auth/callback"]
  logout_urls   = [for url in local.site_origins : "${url}/"]

  id_token_validity      = 60
  access_token_validity  = 60
  refresh_token_validity = 30

  token_validity_units {
    id_token      = "minutes"
    access_token  = "minutes"
    refresh_token = "days"
  }
}

# <project>-<account id> is unique across AWS without anyone choosing a name.
resource "aws_cognito_user_pool_domain" "main" {
  domain                = "${var.project_name}-${local.account_id}"
  user_pool_id          = aws_cognito_user_pool.main.id
  managed_login_version = 2
}

# A version 2 domain shows no sign-in page until the client has a style;
# Cognito's default one is enough.
resource "aws_cognito_managed_login_branding" "web" {
  user_pool_id                = aws_cognito_user_pool.main.id
  client_id                   = aws_cognito_user_pool_client.web.id
  use_cognito_provided_values = true
}
