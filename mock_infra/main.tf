resource "aws_ebs_volume" "unused_data_volume" {
  availability_zone = "us-east-1a"
  size              = 100
  type              = "gp3"

  tags = {
    Name = "Production-Stale-Data"
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