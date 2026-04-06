resource "aws_wafv2_ip_set" "admin_allow" {
  count              = var.enable_waf && length(var.admin_ip_allowlist) > 0 ? 1 : 0
  name               = "${local.name}-admin-allow"
  scope              = "REGIONAL"
  ip_address_version = "IPV4"
  addresses          = var.admin_ip_allowlist
  tags               = local.tags
}

resource "aws_wafv2_web_acl" "waf" {
  count = var.enable_waf ? 1 : 0

  name  = "${local.name}-waf"
  scope = "REGIONAL"
  default_action { allow {} }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-waf"
    sampled_requests_enabled   = true
  }

  rule {
    name     = "rate-limit"
    priority = 1
    action { block {} }
    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "aws-managed-common"
    priority = 2
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.name}-managed-common"
      sampled_requests_enabled   = true
    }
  }

  # Path-based allowlist for /ui only (if you host UI behind same ALB)
  dynamic "rule" {
    for_each = var.enable_waf && length(var.admin_ip_allowlist) > 0 ? [1] : []
    content {
      name     = "admin-ui-ip-allowlist"
      priority = 3
      action { block {} }

      statement {
        and_statement {
          statement {
            byte_match_statement {
              search_string         = "/ui"
              field_to_match        { uri_path {} }
              positional_constraint = "STARTS_WITH"
              text_transformation { priority = 0 type = "NONE" }
            }
          }
          statement {
            not_statement {
              statement {
                ip_set_reference_statement {
                  arn = aws_wafv2_ip_set.admin_allow[0].arn
                }
              }
            }
          }
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${local.name}-admin-ui-ip-allowlist"
        sampled_requests_enabled   = true
      }
    }
  }
}

resource "aws_wafv2_web_acl_association" "alb_assoc" {
  count        = var.enable_waf ? 1 : 0
  resource_arn = aws_lb.alb.arn
  web_acl_arn  = aws_wafv2_web_acl.waf[0].arn
}
