resource "aws_security_group" "rds_sg" {
  name        = "siih2026-rds-sg"
  description = "Security group for PostgreSQL RDS"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }
}

resource "aws_db_subnet_group" "rds_subnet_group" {
  name       = "siih2026-rds-subnet-group"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_db_instance" "postgresql" {
  identifier           = "siih2026-db-${var.environment}"
  allocated_storage    = 100
  max_allocated_storage = 1000
  storage_type         = "gp3"
  engine               = "postgres"
  engine_version       = "14" # REQ-1 (PRISM) relies on TimescaleDB, which requires PG14+
  instance_class       = "db.r6g.large"
  username             = "postgres_admin"
  password             = "REPLACE_WITH_SECURE_PASSWORD_IN_SECRETS_MANAGER"
  
  db_subnet_group_name   = aws_db_subnet_group.rds_subnet_group.name
  vpc_security_group_ids = [aws_security_group.rds_sg.id]

  skip_final_snapshot    = true
  multi_az               = true
  storage_encrypted      = true
  
  # Enabling TimescaleDB parameter group
  parameter_group_name = aws_db_parameter_group.timescaledb_pg.name
}

resource "aws_db_parameter_group" "timescaledb_pg" {
  name   = "siih2026-timescaledb-pg14"
  family = "postgres14"

  parameter {
    name  = "shared_preload_libraries"
    value = "timescaledb,pg_stat_statements"
    apply_method = "pending-reboot"
  }
}
