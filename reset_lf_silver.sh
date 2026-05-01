#!/usr/bin/env bash
set -euo pipefail

REGION="eu-west-2"
DB="energy_smart_meter"
TBL="silver_smart_meter_half_hourly_clean"
P="arn:aws:iam::008768223997:user/Will"

for perm in ALTER DESCRIBE SELECT INSERT DELETE DROP; do
  aws lakeformation revoke-permissions --profile default --region "$REGION" \
    --principal "DataLakePrincipalIdentifier=$P" \
    --resource "{\"Table\":{\"DatabaseName\":\"$DB\",\"Name\":\"$TBL\"}}" \
    --permissions "$perm" >/dev/null 2>&1 || true
done

aws lakeformation revoke-permissions --profile default --region "$REGION" \
  --principal "DataLakePrincipalIdentifier=$P" \
  --resource "{\"TableWithColumns\":{\"DatabaseName\":\"$DB\",\"Name\":\"$TBL\",\"ColumnWildcard\":{}}}" \
  --permissions SELECT >/dev/null 2>&1 || true

aws lakeformation grant-permissions --profile default --region "$REGION" \
  --principal "DataLakePrincipalIdentifier=$P" \
  --resource "{\"Table\":{\"DatabaseName\":\"$DB\",\"Name\":\"$TBL\"}}" \
  --permissions ALTER DESCRIBE

aws lakeformation grant-permissions --profile default --region "$REGION" \
  --principal "DataLakePrincipalIdentifier=$P" \
  --resource "{\"TableWithColumns\":{\"DatabaseName\":\"$DB\",\"Name\":\"$TBL\",\"ColumnWildcard\":{}}}" \
  --permissions SELECT

echo "done"