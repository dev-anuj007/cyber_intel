"""EC2 PostgreSQL Infrastructure Provisioning module."""

import json
from typing import Optional
import pulumi
import pulumi_aws as aws


class EC2PostgresOutput:
    def __init__(
        self,
        instance: aws.ec2.Instance,
        security_group: aws.ec2.SecurityGroup,
        database_url: pulumi.Output[str],
        db_host: pulumi.Output[str],
        db_port: int = 5432,
        db_name: str = "sales_intel",
        db_user: str = "sales_admin",
    ):
        self.instance = instance
        self.security_group = security_group
        self.database_url = database_url
        self.db_host = db_host
        self.db_port = db_port
        self.db_name = db_name
        self.db_user = db_user


def provision_ec2_postgres(
    prefix: str,
    environment: str = "dev",
    instance_type: str = "t3.medium",
    db_name: str = "sales_intel",
    db_user: str = "sales_admin",
    db_password: Optional[str] = None,
    volume_size_gb: int = 30,
) -> EC2PostgresOutput:
    """Provisions a high-performance dedicated EC2 PostgreSQL 16 instance with automated cloud-init setup."""
    config = pulumi.Config()
    password = db_password or config.get_secret("dbPassword") or "SalesIntelSecurePass2026!"

    # 1. Look up latest Ubuntu 24.04 LTS AMI
    ubuntu_ami = aws.ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],  # Canonical
        filters=[
            aws.ec2.GetAmiFilterArgs(
                name="name",
                values=["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"],
            ),
            aws.ec2.GetAmiFilterArgs(name="virtualization-type", values=["hvm"]),
        ],
    )

    # 2. Security Group for PostgreSQL (Port 5432) & SSH (Port 22)
    postgres_sg = aws.ec2.SecurityGroup(
        f"{prefix}-postgres-sg",
        name=f"{prefix}-postgres-sg",
        description="Security group for Sales Intel PostgreSQL EC2 instance",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                description="PostgreSQL from VPC / Microservices",
                from_port=5432,
                to_port=5432,
                protocol="tcp",
                cidr_blocks=["0.0.0.0/0"],  # In production, restrict to VPC CIDR
            ),
            aws.ec2.SecurityGroupIngressArgs(
                description="SSH Admin Access",
                from_port=22,
                to_port=22,
                protocol="tcp",
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                from_port=0,
                to_port=0,
                protocol="-1",
                cidr_blocks=["0.0.0.0/0"],
            ),
        ],
        tags={"Name": f"{prefix}-postgres-sg", "Environment": environment},
    )

    # 3. Cloud-Init User Data Script to automatically install and configure PostgreSQL 16 & pg_trgm
    user_data_script = pulumi.Output.all(password).apply(
        lambda args: f"""#!/bin/bash
set -ex

# Update and install PostgreSQL 16
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y postgresql-16 postgresql-contrib-16 curl

# Configure postgresql.conf to listen on all network interfaces
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/16/main/postgresql.conf
echo "shared_buffers = 1GB" >> /etc/postgresql/16/main/postgresql.conf
echo "work_mem = 64MB" >> /etc/postgresql/16/main/postgresql.conf
echo "maintenance_work_mem = 256MB" >> /etc/postgresql/16/main/postgresql.conf
echo "effective_cache_size = 3GB" >> /etc/postgresql/16/main/postgresql.conf
echo "max_connections = 200" >> /etc/postgresql/16/main/postgresql.conf

# Configure pg_hba.conf to allow password authentication from any IP
cat << 'EOF' > /etc/postgresql/16/main/pg_hba.conf
local   all             postgres                                peer
local   all             all                                     md5
host    all             all             0.0.0.0/0               md5
host    all             all             ::/0                    md5
EOF

systemctl restart postgresql
systemctl enable postgresql

# Initialize database, user, and extensions
sudo -u postgres psql << EOF
CREATE USER {db_user} WITH PASSWORD '{args[0]}' SUPERUSER CREATEDB;
CREATE DATABASE {db_name} OWNER {db_user};
\\c {db_name}
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};
EOF

echo "PostgreSQL 16 initialized successfully" > /var/log/postgres_init.log
"""
    )

    # 4. EC2 Instance
    postgres_instance = aws.ec2.Instance(
        f"{prefix}-postgres-instance",
        instance_type=instance_type,
        ami=ubuntu_ami.id,
        vpc_security_group_ids=[postgres_sg.id],
        user_data=user_data_script,
        root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
            volume_size=volume_size_gb,
            volume_type="gp3",
            delete_on_termination=False,
            encrypted=True,
            tags={"Name": f"{prefix}-postgres-storage"},
        ),
        tags={
            "Name": f"{prefix}-postgres-ec2",
            "Environment": environment,
            "Role": "Database",
        },
    )

    # 5. Database Connection String Output
    db_host = postgres_instance.public_ip
    database_url = pulumi.Output.all(db_host, password).apply(
        lambda args: f"postgresql+psycopg://{db_user}:{args[1]}@{args[0]}:5432/{db_name}"
    )

    return EC2PostgresOutput(
        instance=postgres_instance,
        security_group=postgres_sg,
        database_url=database_url,
        db_host=db_host,
        db_port=5432,
        db_name=db_name,
        db_user=db_user,
    )
