variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Target AWS region."
}

variable "environment" {
  type        = string
  default     = "staging"
  description = "Deployment environment name."
}

variable "vpc_id" {
  type        = string
  description = "Existing VPC ID for ECS, RDS, and ElastiCache."
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnets for ECS tasks, RDS, and ElastiCache."
}

variable "public_subnet_ids" {
  type        = list(string)
  description = "Public subnets for the HTTPS Application Load Balancer."
}

variable "acm_certificate_arn" {
  type        = string
  description = "ACM TLS certificate ARN for the HTTPS ALB listener."
}

variable "api_image" {
  type        = string
  description = "Pinned container image URI for opspilot-api (never :latest)."
}

variable "frontend_image" {
  type        = string
  description = "Pinned container image URI for opspilot-frontend."
}

variable "db_instance_class" {
  type        = string
  default     = "db.t4g.micro"
  description = "RDS PostgreSQL 16 instance class."
}
