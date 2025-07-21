
output "app_ecs_service_name" {
  description = "Name of the deployed ECS service"
  value       = aws_ecs_service.app_service.name
}

output "monitoring_instance_public_ip" {
  description = "Public IP of the Monitoring EC2 instance"
  value       = aws_instance.monitoring.public_ip
}

output "app_security_group_id" {
  description = "Security Group ID of the ECS service"
  value       = aws_security_group.app_sg.id
}

output "monitoring_security_group_id" {
  description = "Security Group ID of the Monitoring EC2 instance"
  value       = aws_security_group.monitoring.id
}

output "ecs_cluster_name" {
  description = "Name of the ECS Cluster"
  value       = aws_ecs_cluster.app_cluster.name
}

output "monitoring_instance_ip" {
  value = aws_instance.monitoring.public_ip
}
