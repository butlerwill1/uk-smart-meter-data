# Summary: Glue Data Catalog database and external table metadata for Athena over S3 parquet data.
# This file defines table schemas/locations for all queryable datasets in the pipeline.

# Glue database that namespaces all project tables.
resource "aws_glue_catalog_database" "energy" {
  name = var.glue_database_name

  # Keep default table permissions simple for portfolio/demo environments.
  create_table_default_permission {
    permissions = ["SELECT"]
    principal {
      data_lake_principal_identifier = "IAM_ALLOWED_PRINCIPALS"
    }
  }
}

# External read-only Bronze table mapped directly to source dataset.
resource "aws_glue_catalog_table" "raw_external" {
  name          = "raw_external_smart_meter"
  database_name = aws_glue_catalog_database.energy.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL = "TRUE"
  }

  storage_descriptor {
    location      = local.external_raw_location
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "raw-external-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "dataset_id"
      type = "string"
    }
    columns {
      name = "dno_alias"
      type = "string"
    }
    columns {
      name = "aggregated_device_count_active"
      type = "bigint"
    }
    columns {
      name = "total_consumption_active_import"
      type = "bigint"
    }
    columns {
      name = "data_collection_log_timestamp"
      type = "timestamp"
    }
    columns {
      name = "geometry"
      type = "struct<x:double,y:double>"
    }
    columns {
      name = "secondary_substation_unique_id"
      type = "string"
    }
    columns {
      name = "lv_feeder_unique_id"
      type = "string"
    }
    columns {
      name = "bbox"
      type = "struct<xmin:double,ymin:double,xmax:double,ymax:double>"
    }
  }
}

# Silver cleaned half-hourly table (partitioned by collection_date).
resource "aws_glue_catalog_table" "silver" {
  name          = "silver_smart_meter_half_hourly_clean"
  database_name = aws_glue_catalog_database.energy.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL = "TRUE"
  }

  storage_descriptor {
    location      = local.silver_location
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "silver-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "dataset_id"
      type = "string"
    }
    columns {
      name = "dno_alias"
      type = "string"
    }
    columns {
      name = "aggregated_device_count_active"
      type = "bigint"
    }
    columns {
      name = "total_consumption_active_import"
      type = "double"
    }
    columns {
      name = "data_collection_log_timestamp"
      type = "timestamp"
    }
    columns {
      name = "geometry"
      type = "struct<x:double,y:double>"
    }
    columns {
      name = "secondary_substation_unique_id"
      type = "string"
    }
    columns {
      name = "lv_feeder_unique_id"
      type = "string"
    }
    columns {
      name = "bbox"
      type = "struct<xmin:double,ymin:double,xmax:double,ymax:double>"
    }
    columns {
      name = "hour_of_day"
      type = "int"
    }
    columns {
      name = "minute_of_hour"
      type = "int"
    }
    columns {
      name = "half_hour_slot"
      type = "int"
    }
    columns {
      name = "day_of_week"
      type = "string"
    }
    columns {
      name = "is_weekend"
      type = "boolean"
    }
    columns {
      name = "composite_feeder_id"
      type = "string"
    }
    columns {
      name = "consumption_per_active_device"
      type = "double"
    }
  }

  partition_keys {
    name = "collection_date"
    type = "date"
  }
}

# Gold table: daily peak demand metrics by substation.
resource "aws_glue_catalog_table" "gold_peak" {
  name          = "gold_peak_demand_substation_day"
  database_name = aws_glue_catalog_database.energy.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL = "TRUE"
  }

  storage_descriptor {
    location      = local.gold_peak_location
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "gold-peak-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "dno_alias"
      type = "string"
    }
    columns {
      name = "secondary_substation_unique_id"
      type = "string"
    }
    columns {
      name = "peak_consumption"
      type = "double"
    }
    columns {
      name = "peak_timestamp"
      type = "timestamp"
    }
    columns {
      name = "daily_total_consumption"
      type = "double"
    }
    columns {
      name = "avg_half_hour_consumption"
      type = "double"
    }
    columns {
      name = "avg_active_devices"
      type = "double"
    }
    columns {
      name = "feeder_count"
      type = "bigint"
    }
    columns {
      name = "reading_count"
      type = "bigint"
    }
  }

  partition_keys {
    name = "consumption_date"
    type = "date"
  }
}

# Gold table: daily average load profile by half-hour slot.
resource "aws_glue_catalog_table" "gold_profile" {
  name          = "gold_avg_load_profile_day"
  database_name = aws_glue_catalog_database.energy.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL = "TRUE"
  }

  storage_descriptor {
    location      = local.gold_profile_location
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "gold-profile-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "hour_of_day"
      type = "int"
    }
    columns {
      name = "minute_of_hour"
      type = "int"
    }
    columns {
      name = "half_hour_slot"
      type = "int"
    }
    columns {
      name = "avg_consumption"
      type = "double"
    }
    columns {
      name = "total_consumption"
      type = "double"
    }
    columns {
      name = "reading_count"
      type = "bigint"
    }
    columns {
      name = "substation_count"
      type = "bigint"
    }
    columns {
      name = "feeder_count"
      type = "bigint"
    }
    columns {
      name = "avg_consumption_per_active_device"
      type = "double"
    }
  }

  partition_keys {
    name = "consumption_date"
    type = "date"
  }
}

# Run log table: one row per pipeline execution, partitioned by run_date.
resource "aws_glue_catalog_table" "run_log" {
  name          = "pipeline_run_log"
  database_name = aws_glue_catalog_database.energy.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL = "TRUE"
  }

  storage_descriptor {
    location      = local.run_log_location
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      name                  = "run-log-serde"
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "run_id"
      type = "string"
    }
    columns {
      name = "pipeline_name"
      type = "string"
    }
    columns {
      name = "started_at"
      type = "string"
    }
    columns {
      name = "finished_at"
      type = "string"
    }
    columns {
      name = "status"
      type = "string"
    }
    columns {
      name = "input_row_count"
      type = "bigint"
    }
    columns {
      name = "silver_row_count"
      type = "bigint"
    }
    columns {
      name = "peak_table_row_count"
      type = "bigint"
    }
    columns {
      name = "load_profile_row_count"
      type = "bigint"
    }
    columns {
      name = "error_message"
      type = "string"
    }
    columns {
      name = "code_version"
      type = "string"
    }
    columns {
      name = "metadata"
      type = "string"
    }
  }

  partition_keys {
    name = "run_date"
    type = "date"
  }
}
