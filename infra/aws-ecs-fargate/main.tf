# Reviewable AWS ECS Fargate blueprint for OpsPilot AI.
# DO NOT run `terraform apply` without explicit authorization and cost review.

terraform {
  required_version = ">= 1.8.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_cloudwatch_log_group" "opspilot" {
  name              = "/ecs/opspilot-${var.environment}"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "main" {
  name = "opspilot-${var.environment}"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "opspilot/${var.environment}/app-secrets"
  recovery_window_in_days = 7
}

resource "aws_db_subnet_group" "postgres" {
  name       = "opspilot-${var.environment}-db"
  subnet_ids = var.private_subnet_ids
}

resource "aws_db_instance" "postgres" {
  identifier              = "opspilot-${var.environment}-pg"
  engine                  = "postgres"
  engine_version          = "16.4"
  instance_class          = var.db_instance_class
  allocated_storage       = 20
  storage_encrypted       = true
  db_name                 = "opspilot"
  username                = "opspilot"
  manage_master_user_password = true
  db_subnet_group_name    = aws_db_subnet_group.postgres.name
  backup_retention_period = 7
  deletion_protection     = true
  skip_final_snapshot     = false
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "opspilot-${var.environment}-redis"
  subnet_ids = var.private_subnet_ids
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "opspilot-${var.environment}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
}

resource "aws_lb" "public" {
  name               = "opspilot-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
}

resource "aws_lb_target_group" "api" {
  name        = "opspilot-${var.environment}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id
  health_check {
    path                = "/health/ready"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 15
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.public.arn
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.acm_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "opspilot-${var.environment}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.api_image
      essential = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "APP_ENV", value = "production" },
        { name = "LOG_FORMAT", value = "json" }
      ]
      secrets = [
        { name = "DATABASE_URL", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:DATABASE_URL::" },
        { name = "JWT_SECRET_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:JWT_SECRET_KEY::" },
        { name = "INTEGRATION_ENCRYPTION_KEY", valueFrom = "${aws_secretsmanager_secret.app_secrets.arn}:INTEGRATION_ENCRYPTION_KEY::" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.opspilot.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }
    }
  ])
}
