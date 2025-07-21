variable "region" {
  description = "AWS region"
  type        = string
}

variable "ecr_image_uri" {
  description = "ECR image URI for the application"
  type        = string
}

variable "ecs_execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "subnet_ids" {
  description = "List of Subnet IDs for ECS tasks and EC2"
  type        = list(string)
}

variable "monitoring_ami_id" {
  description = "AMI ID for the monitoring EC2 instance"
  type        = string
}

variable "ec2_key_name" {
  description = "EC2 Key Pair name for SSH access"
  type        = string
}

variable "repo_name" {
  description = "Sanitized repository name (used for ECS resources)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID for ECS tasks and security groups"
  type        = string
}
