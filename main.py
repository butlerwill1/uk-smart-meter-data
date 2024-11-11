# %% Use Pyspark to read Weave Energy data from an s3 bucket
import pyspark
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("EnergyData").getOrCreate()

energy_df = spark.read.parquet("s3://weave.energy/smart-meter.parquet")

energy_df.printSchema()
# %%
