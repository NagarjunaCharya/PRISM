resource "aws_security_group" "opensearch_sg" {
  name        = "siih2026-opensearch-sg"
  description = "Security group for OpenSearch cluster"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.app_sg.id]
  }
}

resource "aws_opensearch_domain" "sif_nlp" {
  domain_name    = "siih2026-nlp-${var.environment}"
  engine_version = "OpenSearch_2.5" # Compatible with Elasticsearch 8 APIs

  cluster_config {
    instance_type          = "m6g.large.search"
    instance_count         = 3
    zone_awareness_enabled = true
    zone_awareness_config {
      availability_zone_count = 3
    }
  }

  vpc_options {
    subnet_ids         = module.vpc.private_subnets
    security_group_ids = [aws_security_group.opensearch_sg.id]
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 100
    volume_type = "gp3"
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }
}
