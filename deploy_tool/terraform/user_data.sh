#!/bin/bash
yum update -y
amazon-linux-extras enable docker
yum install docker -y
service docker start
usermod -a -G docker ec2-user

# Install Docker Compose v2 (plugin)
curl -SL https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose

# Create monitoring folder and docker-compose file
mkdir -p /home/ec2-user/monitoring
cat <<EOF > /home/ec2-user/monitoring/docker-compose.yml
version: '3'
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
  node_exporter:
    image: prom/node-exporter
    ports:
      - "9100:9100"
EOF

# Create default prometheus.yml config
cat <<EOF > /home/ec2-user/monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['localhost:9100']
EOF

# Start Docker Compose as ec2-user
chown -R ec2-user:ec2-user /home/ec2-user/monitoring
cd /home/ec2-user/monitoring
sudo -u ec2-user docker-compose up -d
