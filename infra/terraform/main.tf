data "aws_availability_zones" "az" {}

locals {
  name = "${var.project}-${var.env}"
  azs  = slice(data.aws_availability_zones.az.names, 0, 2)
  tags = { Project = var.project, Env = var.env }
}
