output "alb_dns_name" {
  value       = aws_lb.public.dns_name
  description = "HTTPS Application Load Balancer DNS name."
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.main.name
  description = "ECS Fargate cluster name."
}

output "rds_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "Managed PostgreSQL 16 endpoint."
}
