#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./deploy.sh prod

ENVIRONMENT="${1:-}"
TARGET="${2:-}"
if [[ -z "$ENVIRONMENT" ]]; then
  echo "Usage: $0 {prod} [worker]"
  exit 1
fi

PROFILE="personal"
ZIP_NAME="deploy.zip"
BUILD_DIR="build"
REQ_FILE="requirements.txt"
MAX_DIRECT_UPLOAD_BYTES=65000000
S3_BUCKET="${S3_BUCKET:-}"

case "$ENVIRONMENT" in
  prod)
    REGION="eu-west-1"
    DEFAULT_S3_BUCKET="ai-bot-prod-artifacts"
    if [[ "$TARGET" == "worker" ]]; then
      LAMBDA_NAME="transcribe-bot-worker"
    else
      LAMBDA_NAME="transcribe-bot"
    fi
    ;;
  *)
    echo "Unknown environment '$ENVIRONMENT' (use prod)"
    exit 1
    ;;
 esac

if [[ -z "$S3_BUCKET" ]]; then
  S3_BUCKET="$DEFAULT_S3_BUCKET"
fi

echo "========================================"
echo "Deploying Lambda"
echo "  Env:     $ENVIRONMENT"
echo "  Region:  $REGION"
echo "  Lambda:  $LAMBDA_NAME"
echo "  Profile: $PROFILE"
echo "========================================"

echo "==> Cleaning build artifacts"
rm -rf "$BUILD_DIR" "$ZIP_NAME"
mkdir -p "$BUILD_DIR"

if [[ -s "$REQ_FILE" ]]; then
  echo "==> Installing dependencies"
  pip install -r "$REQ_FILE" \
    --platform manylinux2014_x86_64 \
    --only-binary=:all: \
    --target "$BUILD_DIR"
fi

echo "==> Copying source files"
cp -r *.py services repository utils "$BUILD_DIR"/

echo "==> Creating deployment zip"
(
  cd "$BUILD_DIR"
  zip -r "../$ZIP_NAME" .
)

ZIP_SIZE_BYTES=$(wc -c < "$ZIP_NAME")
USE_S3_UPLOAD=false
if [[ -n "$S3_BUCKET" ]]; then
  USE_S3_UPLOAD=true
elif (( ZIP_SIZE_BYTES >= MAX_DIRECT_UPLOAD_BYTES )); then
  echo "Error: ZIP is ${ZIP_SIZE_BYTES} bytes (>=${MAX_DIRECT_UPLOAD_BYTES})."
  echo "Set S3_BUCKET to an S3 bucket for deploy artifacts."
  exit 1
fi

if [[ "$USE_S3_UPLOAD" == "true" ]]; then
  S3_KEY="${LAMBDA_NAME}/deploy-$(date +%Y%m%d%H%M%S).zip"
  echo "==> Uploading deployment zip to s3://$S3_BUCKET/$S3_KEY"
  aws s3 cp "$ZIP_NAME" "s3://$S3_BUCKET/$S3_KEY" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --no-cli-pager

  echo "==> Updating Lambda from S3"
  aws lambda update-function-code \
    --function-name "$LAMBDA_NAME" \
    --s3-bucket "$S3_BUCKET" \
    --s3-key "$S3_KEY" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --no-cli-pager \
    --query 'FunctionArn' \
    --output text
else
  echo "==> Uploading to AWS Lambda"
  aws lambda update-function-code \
    --function-name "$LAMBDA_NAME" \
    --zip-file "fileb://$ZIP_NAME" \
    --region "$REGION" \
    --profile "$PROFILE" \
    --no-cli-pager \
    --query 'FunctionArn' \
    --output text
fi

echo "✅ Deployment complete."
