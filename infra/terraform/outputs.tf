output "alb_dns_name" { value = aws_lb.alb.dns_name }
output "db_endpoint"  { value = aws_db_instance.postgres.address }
output "redis_host"   { value = aws_elasticache_cluster.redis.cache_nodes[0].address }
output "buckets"      { value = { for k,v in aws_s3_bucket.b : k => v.bucket } }

# --- CI/CD Secret Outputs (copy/paste into GitHub secrets) ---

output "cicd_ecs_exec_role_arn" {
  value       = aws_iam_role.task_exec.arn
  description = "Set GitHub secret ECS_EXEC_ROLE_ARN to this"
}

output "cicd_ecs_task_role_arn" {
  value       = aws_iam_role.task.arn
  description = "Set GitHub secret ECS_TASK_ROLE_ARN to this"
}

output "cicd_ssm_db_url_arn" {
  value       = aws_ssm_parameter.db_url.arn
  description = "Set GitHub secret SSM_DB_URL_ARN to this"
}

output "cicd_ssm_jwt_arn" {
  value       = aws_ssm_parameter.jwt.arn
  description = "Set GitHub secret SSM_JWT_ARN to this"
}

output "cicd_ssm_mfa_arn" {
  value       = aws_ssm_parameter.mfa.arn
  description = "Set GitHub secret SSM_MFA_ARN to this"
}

output "cicd_ssm_redis_arn" {
  value       = aws_ssm_parameter.redis_url.arn
  description = "Set GitHub secret SSM_REDIS_ARN to this"
}

output "cicd_codedeploy_bucket_hint" {
  value       = "${local.name}-codedeploy-revisions"
  description = "Suggested S3 bucket name for CodeDeploy revisions (create manually or add as Terraform if desired)"
}
