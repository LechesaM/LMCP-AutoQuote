# ECS Blue/Green deployment blueprint (skeleton)
# Use AWS CodeDeploy with ECS blue/green to achieve zero-downtime deploys + automatic rollback.

variable "enable_bluegreen" { type = bool default = false }

# At scale, prefer:
# - Two target groups (blue + green)
# - ALB listener rules switching
# - CodeDeploy Deployment Group
#
# This file is a guide/skeleton because it depends on how you structure listeners/routing.

# Typical resources:
# - aws_codedeploy_app
# - aws_codedeploy_deployment_group (ECS)
# - aws_lb_target_group blue/green
# - listener rules
#
# Implementation note:
# Your GitHub Actions will call CodeDeploy, not direct ECS task update.

# If you want, we can generate the full end-to-end blue/green file once you confirm:
# - single ALB or separate internal/public
# - desired path routing (/api, /ui)
# - whether you want canary shift (10% -> 100%)
