# Summary: Lake Formation permissions for Athena querying of Glue catalog tables and S3 data locations.
# This file grants query access to configured principals for database/table metadata and data reads.

locals {
  # Effective principal set combines explicit principals plus optional auto-detected current caller.
  lakeformation_effective_principals = toset(distinct(concat(
    var.lakeformation_principal_arns,
    var.enable_lakeformation_auto_grant_current_principal ? [local.caller_iam_principal_arn] : [],
  )))

  # All project tables that Athena users should be able to query.
  lakeformation_table_names = [
    aws_glue_catalog_table.raw_external.name,
    aws_glue_catalog_table.silver.name,
    aws_glue_catalog_table.gold_peak.name,
    aws_glue_catalog_table.gold_profile.name,
    aws_glue_catalog_table.run_log.name,
  ]

  # Owned S3 locations for Lake Formation DATA_LOCATION_ACCESS grants.
  # External source bucket is intentionally excluded.
  lakeformation_data_location_arns = toset([
    local.data_bucket_arn,
    aws_s3_bucket.athena_results.arn,
  ])

  # Cross-product map of principal x table for table-level grants.
  lakeformation_table_grants = {
    for pair in setproduct(local.lakeformation_effective_principals, toset(local.lakeformation_table_names)) :
    "${pair[0]}|${pair[1]}" => {
      principal  = pair[0]
      table_name = pair[1]
    }
  }

  # Cross-product map of principal x location for data-location grants.
  lakeformation_location_grants = {
    for pair in setproduct(local.lakeformation_effective_principals, local.lakeformation_data_location_arns) :
    "${pair[0]}|${pair[1]}" => {
      principal    = pair[0]
      location_arn = pair[1]
    }
  }
}

# Optional S3 location registration in Lake Formation.
resource "aws_lakeformation_resource" "s3_location" {
  for_each = var.enable_lakeformation_register_resources ? local.lakeformation_data_location_arns : toset([])

  arn                     = each.value
  use_service_linked_role = true
}

# Database-level DESCRIBE permission allows principals to browse database metadata.
resource "aws_lakeformation_permissions" "database_describe" {
  for_each = local.lakeformation_effective_principals

  principal   = each.value
  permissions = ["DESCRIBE"]

  database {
    catalog_id = data.aws_caller_identity.current.account_id
    name       = aws_glue_catalog_database.energy.name
  }
}

# Table-level SELECT/DESCRIBE permissions allow query execution in Athena.
resource "aws_lakeformation_permissions" "table_select_describe" {
  for_each = local.lakeformation_table_grants

  principal   = each.value.principal
  permissions = ["SELECT", "DESCRIBE"]

  table {
    catalog_id    = data.aws_caller_identity.current.account_id
    database_name = aws_glue_catalog_database.energy.name
    name          = each.value.table_name
  }
}

# Optional data-location permissions for S3 buckets used by source/results datasets.
resource "aws_lakeformation_permissions" "data_location_access" {
  for_each = var.enable_lakeformation_data_location_permissions ? local.lakeformation_location_grants : {}

  principal   = each.value.principal
  permissions = ["DATA_LOCATION_ACCESS"]

  data_location {
    catalog_id = data.aws_caller_identity.current.account_id
    arn        = each.value.location_arn
  }

  depends_on = [aws_lakeformation_resource.s3_location]
}
