variable "aws_region" { type = string default = "af-south-1" }
variable "project"    { type = string default = "autoquote" }
variable "env"        { type = string default = "prod" }

variable "vpc_cidr"   { type = string default = "10.0.0.0/16" }

variable "db_name"    { type = string default = "autoquote" }
variable "db_user"    { type = string default = "postgres" }
variable "db_pass"    { type = string sensitive = true }

variable "jwt_secret" { type = string sensitive = true }
variable "mfa_secret_key" { type = string sensitive = true }

variable "api_image"  { type = string }
variable "worker_image" { type = string }
variable "beat_image" { type = string }

# Optional TLS
variable "domain_name" { type = string default = "" }
variable "acm_cert_arn" { type = string default = "" }

# WAF + alerts
variable "enable_waf" { type = bool default = true }
variable "admin_ip_allowlist" { type = list(string) default = [] }
variable "waf_rate_limit" { type = number default = 2000 }

variable "enable_sns" { type = bool default = true }
variable "alert_emails" { type = list(string) default = [] }

# Blue/green (optional; if enabled, api service switches to CodeDeploy controller)
variable "enable_bluegreen" { type = bool default = false }
variable "prod_listener_port" { type = number default = 80 }
variable "test_listener_port" { type = number default = 9000 }
variable "bluegreen_termination_wait_minutes" { type = number default = 5 }
variable "bluegreen_shift_minutes" { type = number default = 1 }


# GitHub Actions OIDC (optional)
variable "enable_github_oidc" { type = bool default = true }
variable "github_org" { type = string default = "" }        # e.g. "your-org" or GitHub username
variable "github_repo" { type = string default = "" }       # e.g. "autoquote"
variable "github_branch" { type = string default = "main" } # branch allowed to deploy

variable "enable_codedeploy_bucket" { type = bool default = true }
