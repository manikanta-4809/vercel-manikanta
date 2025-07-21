
AWS React Deployment CLI Tool
This CLI tool automates the deployment of React applications on AWS using Docker, ECR, EC2, and Terraform with monitoring support via Prometheus & Grafana.

Features
Git clone & project initialization

S3 upload for source backup

Dockerfile generation (for React projects)

Docker image build & ECR push

EC2 + Terraform-based deployment

Monitoring Stack Provisioning (Prometheus, Grafana, Node Exporter)

Deployment destroy & rollback options

Works with AWS CLI configured credentials

Prerequisites
Python 3.11+

AWS CLI with credentials configured (~/.aws/credentials)

Terraform installed

Docker installed & running

Boto3 Python library
Install with:

arduino
Copy
Edit
pip install boto3 click python-dotenv gitpython requests

CLI Commands

1.Initialize Project
swift
Copy
Edit
python main.py init <repo_url>
Clones repo, uploads code to S3, detects project type, and saves config.

2.Deploy Project
css
Copy
Edit
python main.py deploy
Builds Docker image, pushes to ECR, provisions AWS infrastructure via Terraform.

3.Destroy Deployment
css
Copy
Edit
python main.py destroy
Tears down deployment resources using Terraform.

4.Initialize Monitoring Stack
csharp
Copy
Edit
python main.py monitor init
Deploys Prometheus + Grafana on EC2 with Docker Compose.

5.Check Monitoring Status
css
Copy
Edit
python main.py monitor status

6.View Monitoring Dashboards
css
Copy
Edit
python main.py monitor dashboard

7.Rollback Deployment (Manual Instruction)
css
Copy
Edit
python main.py rollback
Configuration
Default S3 Bucket: my-deploy-tool-bucket

AWS Profile: Read from .env or default

Note
Only supports React projects with package.json

Monitored resources are deployed in default VPC/subnets

Rollback requires manual Docker image tag specification