# ─── Cloud Waste Sniper Mock Infrastructure ───
# This file simulates a realistic AWS environment with wasteful resources.

resource "aws_ebs_volume" "unused_data_volume" {
  count = 0 # Added by Cloud Waste Sniper
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"

  tags = {
    Name = "Production-Stale-Data"
  }
}

resource "aws_ebs_volume" "legacy_backup_volume" {
  count = 0 # Added by Cloud Waste Sniper
  availability_zone = "us-east-1b"
  size              = 200
  type              = "gp3"

  tags = {
    Name = "Legacy-Backup-Volume"
  }
}

resource "aws_instance" "overprovisioned_api" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.medium" # Downsized by Cloud Waste Sniper

  tags = {
    Environment = "Staging"
    Project     = "InternalAPI"
  }
}

resource "aws_instance" "zombie_worker" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.small" # Downsized by Cloud Waste Sniper

  tags = {
    Environment = "Production"
    Project     = "BatchWorker"
  }
}

resource "aws_ebs_snapshot" "orphaned_snapshot" {
  volume_id   = "vol-0000000000000dead"
  description = "Snapshot of deleted volume"

  tags = {
    Name = "OrphanedSnapshot"
  }
}

resource "aws_eip" "unused_eip" {
  domain = "vpc"

  tags = {
    Name = "Unassociated-EIP"
  }
}

resource "aws_nat_gateway" "idle_nat" {
  allocation_id = "eipalloc-00000000000000000"
  subnet_id     = "subnet-00000000000000000"

  tags = {
    Name = "Idle-NAT-Gateway"
  }
}

resource "aws_lb" "legacy_lb" {
  name               = "legacy-app-lb"
  internal           = false
  load_balancer_type = "application"
  subnets            = ["subnet-00000000000000000"]

  tags = {
    Name = "Legacy-App-LB"
  }
}