provider "aws" {
  region = var.region
}

# ECS Cluster
resource "aws_ecs_cluster" "app_cluster" {
  name = "${var.repo_name}-cluster"

  tags = {
    Name = "${var.repo_name}-cluster"
  }
}

# ECS Task Security Group
resource "aws_security_group" "app_sg" {
  name_prefix = "${var.repo_name}-sg"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.repo_name}-sg"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "app_task" {
  family                   = "${var.repo_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.ecs_execution_role_arn

  container_definitions = jsonencode([{
    name      = "${var.repo_name}-container"
    image     = var.ecr_image_uri
    essential = true
    portMappings = [{
      containerPort = 3000
      protocol      = "tcp"
    }]
  }])
}

# ECS Service
resource "aws_ecs_service" "app_service" {
  name            = "${var.repo_name}-service"
  cluster         = aws_ecs_cluster.app_cluster.id
  task_definition = aws_ecs_task_definition.app_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    assign_public_ip = true
    security_groups  = [aws_security_group.app_sg.id]
  }

  depends_on = [
    aws_ecs_task_definition.app_task,
    aws_security_group.app_sg
  ]

  tags = {
    Name = "${var.repo_name}-service"
  }
}

# Monitoring Security Group
resource "aws_security_group" "monitoring" {
  name_prefix = "monitoring-sg"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 9100
    to_port     = 9100
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "monitoring-sg"
  }
}

# Monitoring EC2 Instance
resource "aws_instance" "monitoring" {
  ami                         = var.monitoring_ami_id
  instance_type               = "t2.micro"
  key_name                    = var.ec2_key_name
  subnet_id                   = var.subnet_ids[0]
  vpc_security_group_ids      = [aws_security_group.monitoring.id]
  associate_public_ip_address = true
  user_data                   = file("${path.module}/user_data.sh")

  tags = {
    Name = "monitoring-instance"
  }

  depends_on = [
    aws_security_group.monitoring
  ]
}
