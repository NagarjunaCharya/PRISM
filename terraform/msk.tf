resource "aws_security_group" "msk_sg" {
  name        = "siih2026-msk-sg"
  description = "Security group for MSK Kafka Cluster"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 9094
    to_port         = 9094
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }
}

resource "aws_msk_cluster" "kafka" {
  cluster_name           = "siih2026-kafka-${var.environment}"
  kafka_version          = "3.5.1"
  number_of_broker_nodes = 3

  broker_node_group_info {
    instance_type   = "kafka.m5.large"
    client_subnets  = module.vpc.private_subnets
    security_groups = [aws_security_group.msk_sg.id]
    
    storage_info {
      ebs_storage_info {
        volume_size = 500
      }
    }
  }

  encryption_info {
    encryption_at_rest_kms_key_arn = aws_kms_key.msk_kms.arn
    encryption_in_transit {
      client_broker = "TLS"
      in_cluster    = true
    }
  }

  configuration_info {
    arn      = aws_msk_configuration.kafka_config.arn
    revision = aws_msk_configuration.kafka_config.latest_revision
  }
}

resource "aws_kms_key" "msk_kms" {
  description = "KMS key for MSK encryption"
  enable_key_rotation = true
}

resource "aws_msk_configuration" "kafka_config" {
  name = "siih2026-kafka-config"
  server_properties = <<EOF
auto.create.topics.enable = true
default.replication.factor = 3
min.insync.replicas = 2
num.io.threads = 8
num.network.threads = 5
num.partitions = 3
num.replica.fetchers = 2
replica.lag.time.max.ms = 30000
socket.receive.buffer.bytes = 102400
socket.request.max.bytes = 104857600
socket.send.buffer.bytes = 102400
unclean.leader.election.enable = true
zookeeper.session.timeout.ms = 18000
EOF
}
