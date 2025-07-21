# main.py (Final Updated with Automation)
import os
import subprocess
import click
from git import Repo
import boto3
from botocore.exceptions import ClientError
import json
from dotenv import load_dotenv
from datetime import datetime, timezone
import re
import shutil
import stat
import requests

load_dotenv()
AWS_PROFILE = os.getenv('AWS_PROFILE', 'default')
CONFIG_FILE = "deploy_tool_config.json"
FIXED_BUCKET_NAME = "my-deploy-tool-bucket"

@click.group()
def cli():
    pass

def save_config(data):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def check_aws_credentials():
    session = boto3.Session(profile_name=AWS_PROFILE)
    sts = session.client('sts')
    try:
        identity = sts.get_caller_identity()
        print(f"✅ AWS Credentials Verified: {identity['Arn']}")
        return session.get_credentials().get_frozen_credentials()
    except ClientError as e:
        print(f"❌ AWS Credentials Error: {e}")
        exit(1)

def clone_repo(repo_url):
    repo_name = repo_url.rstrip('/').split('/')[-1].replace('.git', '')
    folder = f"cloned-{repo_name}"
    if os.path.exists(folder):
        print(f"🗑️ Removing existing folder {folder} before cloning new repo.")
        shutil.rmtree(folder, onerror=on_rm_error)
    print(f"📥 Cloning {repo_url} ...")
    Repo.clone_from(repo_url, folder)
    return folder, repo_name

def on_rm_error(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)

def create_bucket_if_not_exists(bucket_name):
    s3 = boto3.Session(profile_name=AWS_PROFILE).client('s3')
    region = get_aws_region()
    try:
        s3.head_bucket(Bucket=bucket_name)
        print(f" S3 bucket '{bucket_name}' already exists.")
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            print(f" Bucket '{bucket_name}' does not exist. Creating...")
            if region == 'us-east-1':
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': region})
            print(f" Bucket '{bucket_name}' created.")

def upload_project_to_s3(local_path, bucket, prefix):
    s3 = boto3.Session(profile_name=AWS_PROFILE).client('s3')
    for root, _, files in os.walk(local_path):
        for file in files:
            s3_path = os.path.join(prefix, os.path.relpath(os.path.join(root, file), local_path)).replace("\\", "/")
            try:
                s3.upload_file(os.path.join(root, file), bucket, s3_path)
                print(f" Uploaded {s3_path}")
            except ClientError as e:
                print(f" Upload failed for {s3_path}: {e}")

def detect_project_type(folder):
    package_json_path = os.path.join(folder, 'package.json')
    if os.path.exists(package_json_path):
        with open(package_json_path) as f:
            data = json.load(f)
            deps = data.get('dependencies', {})
            dev_deps = data.get('devDependencies', {})
            if 'react-scripts' in deps or 'react-scripts' in dev_deps:
                return "cra"
            if 'vite' in deps or 'vite' in dev_deps:
                return "vite"
            if 'react' in deps:
                return "react"
    return "unknown"

@cli.command('init')
@click.argument('repo_url', required=False)
def init(repo_url):
    if not repo_url:
        repo_url = click.prompt('📥 Git Repository URL', type=str)
    folder, repo_name = clone_repo(repo_url)
    create_bucket_if_not_exists(FIXED_BUCKET_NAME)
    project_type = detect_project_type(folder)
    print(f" Project Type Detected: {project_type}")
    save_config({
        "bucket_name": FIXED_BUCKET_NAME,
        "repo_name": sanitize_repo_name(repo_name),
        "repo_url": repo_url,
        "project_type": project_type
    })
    print(f" Init completed for project '{repo_name}'")

@cli.command('deploy')
@click.argument('environment', required=False, default='dev')
def deploy(environment):
    config = load_config()
    if not config.get("repo_name") or not config.get("repo_url"):
        print(" Please run 'init' first.")
        exit(1)
    creds = check_aws_credentials()
    repo_name = config.get("repo_name")
    repo_url = config.get("repo_url")
    print(f" Starting deploy for environment '{environment}' on repo '{repo_name}'")
    folder, _ = clone_repo(repo_url)
    if detect_and_generate_dockerfile(folder):
        base_ecr_image = create_ecr_repo(repo_name)
        timestamp_tag = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        ecr_image_with_tag = f"{base_ecr_image}:{timestamp_tag}"
        docker_build_and_push(ecr_image_with_tag, folder)
    else:
        print(" Deployment aborted due to unsupported project.")
        exit(1)
    ec2_ami_id = get_default_amazon_linux_ami()
    key_pair_name = get_default_key_pair_name()
    run_terraform(creds, ecr_image_with_tag, ec2_ami_id, key_pair_name)
    print(f" Deployment completed for '{repo_name}' in environment '{environment}'.")

@cli.command('destroy')
@click.argument('environment', required=False, default='dev')
def destroy(environment):
    config = load_config()
    repo = config.get("repo_name")
    if not repo:
        print(" Please run 'init' before destroy.")
        exit(1)
    creds = check_aws_credentials()
    region = get_aws_region()
    ecr_image = f"{get_account_id()}.dkr.ecr.{region}.amazonaws.com/{repo}"
    print(" Running Terraform Destroy...")
    run_terraform_destroy(creds, ecr_image)
    print(f" Destroy completed for '{repo}' in environment '{environment}'.")

@cli.group()
def monitor():
    pass

@monitor.command('init')
def monitor_init():
    creds = check_aws_credentials()
    env = build_terraform_env(creds, None, get_default_amazon_linux_ami(), get_default_key_pair_name())
    subprocess.run(["terraform", "init"], cwd="terraform", env=env, check=True)
    subprocess.run(["terraform", "apply", "-auto-approve"], cwd="terraform", env=env, check=True)
    print(" Monitoring Stack Initialized.")

@monitor.command('status')
def monitor_status():
    instance_ip = get_monitoring_instance_ip()
    if not instance_ip:
        print(" Monitoring EC2 instance not running.")
        return
    print(f" Monitoring Instance IP: {instance_ip}")
    for service, port in [("Prometheus", 9090), ("Grafana", 3000)]:
        try:
            r = requests.get(f"http://{instance_ip}:{port}", timeout=5)
            print(f" {service} is UP" if r.status_code == 200 else f"❌ {service} Error")
        except:
            print(f" {service} Unreachable")

@monitor.command('dashboard')
def monitor_dashboard():
    instance_ip = get_monitoring_instance_ip()
    if instance_ip:
        print(f" Access Prometheus: http://{instance_ip}:9090")
        print(f" Access Grafana:    http://{instance_ip}:3000")
        print(f" Access Node Exporter:  http://{instance_ip}:9100")
    else:
        print(" Monitoring instance not running.")

@cli.command('rollback')
@click.option('--tag', prompt='Enter the previous image tag to rollback', help='ECR image tag to rollback to')
def rollback(tag):
    config = load_config()
    if not config.get("repo_name"):
        print("Please run 'init' first.")
        exit(1)

    creds = check_aws_credentials()
    repo_name = config.get("repo_name")
    region = get_aws_region()
    ecr_image = f"{get_account_id()}.dkr.ecr.{region}.amazonaws.com/{repo_name}:{tag}"
    
    print(f"Starting rollback using image: {ecr_image}")
    
    ec2_ami_id = get_default_amazon_linux_ami()
    key_pair_name = get_default_key_pair_name()
    
    run_terraform(creds, ecr_image, ec2_ami_id, key_pair_name)
    
    print(f"Rollback completed using image tag: {tag}")



def sanitize_repo_name(name):
    name = name.lower()
    name = re.sub(r'[^a-z0-9._-]', '-', name)
    name = re.sub(r'^[-._]+|[-._]+$', '', name)
    if not name:
        raise ValueError("Sanitized repository name is empty.")
    return name

# Helper functions (detect_and_generate_dockerfile, create_ecr_repo, docker_build_and_push, terraform, boto3 helpers) remain unchanged as shared earlier.
# Include your last working versions of these functions with auto environment passing like build_terraform_env()

def build_terraform_env(creds, ecr_image, ami_id, key_name):
    env = os.environ.copy()
    env.update({
        'AWS_ACCESS_KEY_ID': creds.access_key,
        'AWS_SECRET_ACCESS_KEY': creds.secret_key,
        'TF_VAR_region': get_aws_region(),
        'TF_VAR_ecr_image_uri': ecr_image or "placeholder",
        'TF_VAR_vpc_id': get_default_vpc_id(),
        'TF_VAR_repo_name': sanitize_repo_name(load_config().get("repo_name")),
        'TF_VAR_ecs_execution_role_arn': get_ecs_execution_role_arn(),
        'TF_VAR_subnet_ids': json.dumps(get_default_subnets()),
        'TF_VAR_monitoring_ami_id': ami_id,
        'TF_VAR_ec2_key_name': key_name
    })
    if creds.token:
        env['AWS_SESSION_TOKEN'] = creds.token
    return env

def create_ecr_repo(repo_name):
    ecr = boto3.Session(profile_name=AWS_PROFILE).client('ecr')
    try:
        response = ecr.create_repository(repositoryName=repo_name)
        print(f" ECR repository '{repo_name}' created.")
        return response['repository']['repositoryUri']
    except ecr.exceptions.RepositoryAlreadyExistsException:
        response = ecr.describe_repositories(repositoryNames=[repo_name])
        print(f" ECR repository '{repo_name}' already exists.")
        return response['repositories'][0]['repositoryUri']

def detect_and_generate_dockerfile(project_path, generate_source_map=False):
    dockerfile_path = os.path.join(project_path, 'Dockerfile')
    package_json_path = os.path.join(project_path, 'package.json')
    if os.path.exists(package_json_path):
        with open(package_json_path) as f:
            package_data = json.load(f)
            deps = package_data.get('dependencies', {})
            if 'react' in deps:
                print(" Detected React project. Generating Dockerfile...")
                docker_content = f"""
FROM node:18-alpine
WORKDIR /app
COPY . .
RUN npm install
{ 'ENV GENERATE_SOURCEMAP=false' if not generate_source_map else '' }
RUN npm run build
RUN npm install -g serve
CMD [\"serve\", \"-s\", \"build\", \"-l\", \"3000\"]
"""
                with open(dockerfile_path, 'w') as f:
                    f.write(docker_content.strip())
                print(f" Dockerfile generated at {dockerfile_path}")
                return True
            else:
                print("❌ This deploy tool supports only React projects (Create React App).")
                return False
    else:
        print("❌ package.json not found. This project is not supported.")
        return False

def docker_build_and_push(image_uri, project_dir):
    print(" Building Docker image with --no-cache ...")
    subprocess.run(["docker", "build", "--no-cache", "-t", image_uri, "."], cwd=os.path.abspath(project_dir), check=True)
    print(" Authenticating Docker with ECR...")
    ecr_registry = image_uri.split('/')[0]
    subprocess.run(f"aws ecr get-login-password --profile {AWS_PROFILE} | docker login --username AWS --password-stdin {ecr_registry}", shell=True, check=True)
    print(" Pushing Docker image to ECR...")
    subprocess.run(["docker", "push", image_uri], check=True)
    print(f" Image pushed to {image_uri}")

def get_account_id():
    return boto3.Session(profile_name=AWS_PROFILE).client('sts').get_caller_identity()['Account']

def get_aws_region():
    return boto3.Session(profile_name=AWS_PROFILE).region_name or "us-east-1"

def get_ecs_execution_role_arn():
    iam = boto3.Session(profile_name=AWS_PROFILE).client('iam')
    for role in iam.list_roles()['Roles']:
        if role['RoleName'] == 'ecsTaskExecutionRole':
            return role['Arn']
    raise Exception("❌ ECS Task Execution Role not found.")

def get_default_subnets():
    ec2 = boto3.Session(profile_name=AWS_PROFILE).client('ec2')
    return [subnet['SubnetId'] for subnet in ec2.describe_subnets()['Subnets']]

def get_default_amazon_linux_ami():
    ec2 = boto3.Session(profile_name=AWS_PROFILE).client('ec2')
    images = ec2.describe_images(Owners=['amazon'], Filters=[
        {'Name': 'name', 'Values': ['al2023-ami-*-kernel-6.1-x86_64']},
        {'Name': 'state', 'Values': ['available']}
    ])['Images']
    images.sort(key=lambda x: x['CreationDate'], reverse=True)
    if images:
        print(f" Using Amazon Linux 2023 AMI: {images[0]['ImageId']}")
        return images[0]['ImageId']
    else:
        raise Exception(" Amazon Linux 2023 AMI not found.")

def get_default_key_pair_name():
    ec2 = boto3.Session(profile_name=AWS_PROFILE).client('ec2')
    key_pairs = ec2.describe_key_pairs()['KeyPairs']
    if key_pairs:
        print(f" Using EC2 Key Pair: {key_pairs[0]['KeyName']}")
        return key_pairs[0]['KeyName']
    else:
        raise Exception(" No EC2 Key Pairs found.")

def get_default_vpc_id():
    ec2 = boto3.Session(profile_name=AWS_PROFILE).client('ec2')
    vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}])['Vpcs']
    if vpcs:
        print(f" Using Default VPC ID: {vpcs[0]['VpcId']}")
        return vpcs[0]['VpcId']
    else:
        raise Exception(" No default VPC found in this region/account.")
def run_terraform_destroy(creds, ecr_image):
    env = os.environ.copy()
    env.update({
        'AWS_ACCESS_KEY_ID': creds.access_key,
        'AWS_SECRET_ACCESS_KEY': creds.secret_key,
        'TF_VAR_region': get_aws_region(),
        'TF_VAR_ecr_image_uri': ecr_image,
        'TF_VAR_vpc_id': get_default_vpc_id(),
        'TF_VAR_repo_name': sanitize_repo_name(load_config().get("repo_name")),
        'TF_VAR_ecs_execution_role_arn': get_ecs_execution_role_arn(),
        'TF_VAR_subnet_ids': json.dumps(get_default_subnets()),
        'TF_VAR_monitoring_ami_id': get_default_amazon_linux_ami(),
        'TF_VAR_ec2_key_name': get_default_key_pair_name()
    })
    if creds.token:
        env['AWS_SESSION_TOKEN'] = creds.token
    subprocess.run(["terraform", "destroy", "-auto-approve"], cwd="terraform", env=env, check=True)
    print(" Terraform destroy completed successfully.")

def run_terraform(creds, ecr_image, ec2_ami_id, key_pair_name):
    env = os.environ.copy()
    env.update({
        'AWS_ACCESS_KEY_ID': creds.access_key,
        'AWS_SECRET_ACCESS_KEY': creds.secret_key,
        'TF_VAR_region': get_aws_region(),
        'TF_VAR_ecr_image_uri': ecr_image,
        'TF_VAR_vpc_id': get_default_vpc_id(),
        'TF_VAR_repo_name': sanitize_repo_name(load_config().get("repo_name")),
        'TF_VAR_ecs_execution_role_arn': get_ecs_execution_role_arn(),
        'TF_VAR_subnet_ids': json.dumps(get_default_subnets()),
        'TF_VAR_monitoring_ami_id': ec2_ami_id,
        'TF_VAR_ec2_key_name': key_pair_name
    })
    if creds.token:
        env['AWS_SESSION_TOKEN'] = creds.token
    subprocess.run(["terraform", "init"], cwd="terraform", env=env, check=True)
    subprocess.run(["terraform", "apply", "-auto-approve"], cwd="terraform", env=env, check=True)
    print(" Terraform applied successfully.")

def get_monitoring_instance_ip():
    ec2 = boto3.Session(profile_name=AWS_PROFILE).client('ec2')
    instances = ec2.describe_instances(Filters=[
        {'Name': 'tag:Name', 'Values': ['monitoring-instance']},
        {'Name': 'instance-state-name', 'Values': ['running']}
    ])
    for reservation in instances['Reservations']:
        for instance in reservation['Instances']:
            return instance['PublicIpAddress']
    return None

if __name__ == '__main__':
    cli()
