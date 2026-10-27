# Peach agenda parser (Lab 6; was infra/ai.yml). The browser posts pasted text
# to this function's URL with a Cognito ID token; the function asks Claude on
# Bedrock for a structured agenda and returns it. It only suggests: the user
# checks the pre-filled form and saves through the API. The function needs no
# database, so it runs outside the VPC and reaches Bedrock over the internet -
# no NAT, no interface endpoint, nothing billed while nobody parses. Plus the
# account's monthly budget alarm.

# --- the parser --------------------------------------------------------------

resource "aws_iam_role" "parser" {
  # The name CloudFormation generated, kept so the role was imported.
  name = "${var.project_name}-ai-ParserRole-XrcGHj7phTtQ"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "parser_logs" {
  role       = aws_iam_role.parser.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "parser" {
  name = "call-bedrock"
  role = aws_iam_role.parser.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      # Any model for now; narrowing it to parser_model is a discussion
      # question in docs/lab6.md. bedrock-mantle for the Messages API,
      # bedrock:InvokeModel for Converse (an inference profile and the
      # foundation models it routes to, in several regions).
      Sid      = "Inference"
      Effect   = "Allow"
      Action   = ["bedrock-mantle:CreateInference", "bedrock:InvokeModel"]
      Resource = "*"
    }]
  })
}

resource "aws_cloudwatch_log_group" "parser" {
  name              = "/aws/lambda/${var.project_name}-agenda-parser"
  retention_in_days = var.parser_log_retention_days
}

# No vpc_config: Bedrock and the pool's public keys are on the internet, and
# the database is not needed. The API's image, so the schemas and the token
# checks are the same code the API runs.
resource "aws_lambda_function" "parser" {
  function_name = "${var.project_name}-agenda-parser"
  description   = "Pasted text in, a suggested agenda out. Writes nothing."
  role          = aws_iam_role.parser.arn

  package_type  = "Image"
  image_uri     = local.backend_image
  architectures = [local.backend_architecture]
  memory_size   = 512
  timeout       = 30

  image_config {
    command = ["app.ai.agenda_lambda.handler"]
  }

  logging_config {
    log_format = "Text"
    log_group  = aws_cloudwatch_log_group.parser.name
  }

  environment {
    variables = {
      APP_ENV              = "production"
      PARSER_API           = var.parser_api
      PARSER_MODEL         = var.parser_model
      BEDROCK_REGION       = local.region
      COGNITO_REGION       = local.region
      COGNITO_USER_POOL_ID = aws_cognito_user_pool.main.id
      COGNITO_CLIENT_ID    = aws_cognito_user_pool_client.web.id
    }
  }

  # scripts/deploy-backend.sh moves the code along with the API's.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

# Public, like the API's: the handler checks the Cognito token and answers 401
# to anything else, because every call costs money.
resource "aws_lambda_function_url" "parser" {
  function_name      = aws_lambda_function.parser.function_name
  authorization_type = "NONE"

  cors {
    allow_origins = local.browser_origins
    allow_methods = ["POST"]
    allow_headers = ["authorization", "content-type"]
    max_age       = 3600
  }
}

# A public function URL needs both grants: InvokeFunctionUrl, and
# InvokeFunction limited to calls that came through the URL.
resource "aws_lambda_permission" "parser_url" {
  statement_id           = "${var.project_name}-ai-ParserUrlPermission-TPpSVWgQXm3s"
  function_name          = aws_lambda_function.parser.function_name
  action                 = "lambda:InvokeFunctionUrl"
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "parser_url_invoke" {
  statement_id             = "${var.project_name}-ai-ParserUrlInvokePermission-e8feQcKLoBqe"
  function_name            = aws_lambda_function.parser.function_name
  action                   = "lambda:InvokeFunction"
  principal                = "*"
  invoked_via_function_url = true
}

# --- the cheapest insurance in the course ------------------------------------

# The whole account, not only this project: a forgotten endpoint elsewhere
# costs the same money.
resource "aws_budgets_budget" "monthly" {
  count = nonsensitive(var.budget_email != "") ? 1 : 0

  name         = "${var.project_name}-monthly"
  budget_type  = "COST"
  time_unit    = "MONTHLY"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"

  # Money already spent...
  notification {
    notification_type          = "ACTUAL"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.budget_email]
  }

  # ...and a month on its way past the limit, while there is time to act.
  notification {
    notification_type          = "FORECASTED"
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    subscriber_email_addresses = [var.budget_email]
  }
}
