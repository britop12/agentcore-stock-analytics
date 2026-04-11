# ---------------------------------------------------------------------------
# IAM role for Bedrock Knowledge Base service
# ---------------------------------------------------------------------------

resource "aws_iam_role" "kb_role" {
  name = "${var.app_name}-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "bedrock.amazonaws.com" }
        Action    = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = var.account_id
          }
        }
      }
    ]
  })
}

resource "aws_iam_policy" "kb_policy" {
  name = "${var.app_name}-kb-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockEmbedding"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"
      },
      {
        Sid    = "S3DataRead"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.kb_data.arn,
          "${aws_s3_bucket.kb_data.arn}/*"
        ]
      },
      {
        Sid    = "S3SupplementalReadWrite"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket",
          "s3:AbortMultipartUpload"
        ]
        Resource = [
          aws_s3_bucket.kb_supplemental.arn,
          "${aws_s3_bucket.kb_supplemental.arn}/*"
        ]
      },
      {
        Sid    = "S3VectorsReadWrite"
        Effect = "Allow"
        Action = [
          "s3vectors:CreateIndex",
          "s3vectors:PutVectors",
          "s3vectors:QueryVectors",
          "s3vectors:GetVectors",
          "s3vectors:DeleteVectors",
          "s3vectors:ListVectors"
        ]
        Resource = [
          aws_s3vectors_vector_bucket.this.vector_bucket_arn,
          "${aws_s3vectors_vector_bucket.this.vector_bucket_arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "kb_attach" {
  role       = aws_iam_role.kb_role.name
  policy_arn = aws_iam_policy.kb_policy.arn
}

# ---------------------------------------------------------------------------
# S3 bucket for source documents (PDFs)
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "kb_data" {
  bucket = "${var.app_name}-kb-data"
  tags = {
    Name        = "${var.app_name}-kb-data"
    Application = var.app_name
  }
}

resource "aws_s3_bucket_public_access_block" "kb_data" {
  bucket                  = aws_s3_bucket.kb_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_data" {
  bucket = aws_s3_bucket.kb_data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# ---------------------------------------------------------------------------
# S3 bucket for supplemental chunk text storage
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "kb_supplemental" {
  bucket = "${var.app_name}-kb-supplemental"
  tags = {
    Name        = "${var.app_name}-kb-supplemental"
    Application = var.app_name
  }
}

resource "aws_s3_bucket_public_access_block" "kb_supplemental" {
  bucket                  = aws_s3_bucket.kb_supplemental.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "kb_supplemental" {
  bucket = aws_s3_bucket.kb_supplemental.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# ---------------------------------------------------------------------------
# S3 Vectors — vector bucket + index
# ---------------------------------------------------------------------------

resource "aws_s3vectors_vector_bucket" "this" {
  vector_bucket_name = "${var.app_name}-kb-vectors"
}

resource "aws_s3vectors_index" "this" {
  index_name         = "${var.app_name}-kb-index"
  vector_bucket_name = aws_s3vectors_vector_bucket.this.vector_bucket_name

  data_type       = "float32"
  dimension       = 1024
  distance_metric = "cosine"
}

# ---------------------------------------------------------------------------
# Bedrock Knowledge Base with S3 Vectors + supplemental data in S3
# ---------------------------------------------------------------------------

resource "aws_bedrockagent_knowledge_base" "this" {
  name     = "${var.app_name}-kb"
  role_arn = aws_iam_role.kb_role.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = 1024
          embedding_data_type = "FLOAT32"
        }
      }
      supplemental_data_storage_configuration {
        storage_location {
          type = "S3"
          s3_location {
            uri = "s3://${aws_s3_bucket.kb_supplemental.bucket}/"
          }
        }
      }
    }
  }

  storage_configuration {
    type = "S3_VECTORS"
    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.this.index_arn
    }
  }
}

# ---------------------------------------------------------------------------
# Data source — S3 bucket with the financial PDFs
# ---------------------------------------------------------------------------

resource "aws_bedrockagent_data_source" "this" {
  name              = "${var.app_name}-kb-datasource"
  knowledge_base_id = aws_bedrockagent_knowledge_base.this.id

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.kb_data.arn
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 200
        overlap_percentage = 10
      }
    }
  }
}

# ---------------------------------------------------------------------------
# Upload the three Amazon financial PDFs to the data bucket
# ---------------------------------------------------------------------------

resource "null_resource" "upload_pdfs" {
  depends_on = [aws_s3_bucket.kb_data]

  triggers = {
    bucket = aws_s3_bucket.kb_data.bucket
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      BUCKET="${aws_s3_bucket.kb_data.bucket}"

      curl -sL "https://s2.q4cdn.com/299287126/files/doc_financials/2025/ar/Amazon-2024-Annual-Report.pdf" \
        | aws s3 cp - "s3://$BUCKET/Amazon-2024-Annual-Report.pdf"

      curl -sL "https://s2.q4cdn.com/299287126/files/doc_financials/2025/q3/AMZN-Q3-2025-Earnings-Release.pdf" \
        | aws s3 cp - "s3://$BUCKET/AMZN-Q3-2025-Earnings-Release.pdf"

      curl -sL "https://s2.q4cdn.com/299287126/files/doc_financials/2025/q2/AMZN-Q2-2025-Earnings-Release.pdf" \
        | aws s3 cp - "s3://$BUCKET/AMZN-Q2-2025-Earnings-Release.pdf"
    EOT
    interpreter = ["bash", "-c"]
  }
}

# ---------------------------------------------------------------------------
# Trigger data source sync after PDFs are uploaded
# ---------------------------------------------------------------------------

resource "null_resource" "sync_data_source" {
  depends_on = [null_resource.upload_pdfs, aws_bedrockagent_data_source.this]

  triggers = {
    data_source_id    = aws_bedrockagent_data_source.this.data_source_id
    knowledge_base_id = aws_bedrockagent_knowledge_base.this.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      set -e
      aws bedrock-agent start-ingestion-job \
        --region "${var.region}" \
        --knowledge-base-id "${aws_bedrockagent_knowledge_base.this.id}" \
        --data-source-id "${aws_bedrockagent_data_source.this.data_source_id}"
    EOT
    interpreter = ["bash", "-c"]
  }
}
