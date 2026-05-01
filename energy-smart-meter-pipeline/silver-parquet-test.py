import pyarrow.parquet as pq
pf = pq.ParquetFile('silver.parquet')
print("rows:", pf.metadata.num_rows)
print("row_groups:", pf.num_row_groups)