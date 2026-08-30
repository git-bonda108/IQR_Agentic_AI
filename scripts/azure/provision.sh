#!/usr/bin/env bash
# IQR on Azure — one-shot provisioning.
# Creates: resource group, storage (blob WORM evidence store + tables),
# Azure AI Foundry account + project + model deployment, Azure AI Search
# (the Foundry IQ knowledge-base engine).
#
# Cost posture (POC): Search=free tier, gpt-4o-mini deployment, LRS storage.
# Everything is idempotent: re-running updates rather than duplicates.
set -euo pipefail

LOC="${IQR_AZ_LOCATION:-eastus2}"
RG="${IQR_AZ_RG:-rg-iqr-sox}"
SA="${IQR_AZ_STORAGE:-stiqrsox$RANDOM}"          # override to pin a name
FOUNDRY="${IQR_AZ_FOUNDRY:-iqr-foundry}"
PROJECT="${IQR_AZ_PROJECT:-iqr-sox}"
SEARCH="${IQR_AZ_SEARCH:-iqr-search}"
DEPLOYMENT="${IQR_AZ_DEPLOYMENT:-gpt-4o-mini}"
MODEL_NAME="${IQR_AZ_MODEL:-gpt-4o-mini}"
MODEL_VERSION="${IQR_AZ_MODEL_VERSION:-2024-07-18}"

echo "== resource group"
az group create -n "$RG" -l "$LOC" -o none

echo "== storage account (blob + table)"
az storage account create -n "$SA" -g "$RG" -l "$LOC" \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2 \
  --allow-blob-public-access false -o none
KEY=$(az storage account keys list -n "$SA" -g "$RG" --query "[0].value" -o tsv)

for c in evidence-store run-ledgers audit-packs plans knowledge source-evidence; do
  az storage container create -n "$c" --account-name "$SA" --account-key "$KEY" -o none
done
# Immutability on the evidence store: chain of custody, WORM for 366 days.
az storage container immutability-policy create \
  --account-name "$SA" -c evidence-store --period 366 \
  --allow-protected-append-writes true -o none 2>/dev/null || true

for t in runs exceptions; do
  az storage table create -n "$t" --account-name "$SA" --account-key "$KEY" -o none
done

echo "== Azure AI Foundry (AIServices account + project)"
az cognitiveservices account create -n "$FOUNDRY" -g "$RG" -l "$LOC" \
  --kind AIServices --sku S0 --custom-domain "$FOUNDRY" -o none
SUB=$(az account show --query id -o tsv)
az rest --method put \
  --url "https://management.azure.com/subscriptions/$SUB/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$FOUNDRY/projects/$PROJECT?api-version=2025-04-01-preview" \
  --body "{\"location\": \"$LOC\", \"identity\": {\"type\": \"SystemAssigned\"}, \"properties\": {\"description\": \"IQR SOX 404 validation\"}}" -o none

echo "== model deployment ($DEPLOYMENT)"
az cognitiveservices account deployment create -n "$FOUNDRY" -g "$RG" \
  --deployment-name "$DEPLOYMENT" --model-name "$MODEL_NAME" \
  --model-version "$MODEL_VERSION" --model-format OpenAI \
  --sku-name GlobalStandard --sku-capacity 10 -o none

echo "== Azure AI Search (Foundry IQ knowledge bases)"
az search service create -n "$SEARCH" -g "$RG" -l "$LOC" --sku free -o none \
  || az search service create -n "$SEARCH" -g "$RG" -l "$LOC" --sku basic -o none

FOUNDRY_KEY=$(az cognitiveservices account keys list -n "$FOUNDRY" -g "$RG" --query key1 -o tsv)
SEARCH_KEY=$(az search admin-key show --service-name "$SEARCH" -g "$RG" --query primaryKey -o tsv)

cat <<EOF

== DONE. Add to .env:
AZURE_FOUNDRY_ENDPOINT=https://$FOUNDRY.openai.azure.com
AZURE_FOUNDRY_API_KEY=$FOUNDRY_KEY
AZURE_FOUNDRY_DEPLOYMENT=$DEPLOYMENT
FOUNDRY_IQ_ENDPOINT=https://$SEARCH.search.windows.net
FOUNDRY_IQ_API_KEY=$SEARCH_KEY
FOUNDRY_IQ_KNOWLEDGE_BASE=iqr-knowledge
IQR_AZ_STORAGE_ACCOUNT=$SA
IQR_AZ_STORAGE_KEY=$KEY
EOF
