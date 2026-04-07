#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./deploy.sh
#   ./deploy.sh main
#   ./deploy.sh worker
#   ./deploy.sh drive
#   ./deploy.sh transcript

TARGET="${1:-all}"

PROFILE="personal"
ZIP_NAME="deploy.zip"
BUILD_DIR="build"
REQ_FILE="requirements.txt"
MAX_DIRECT_UPLOAD_BYTES=65000000
S3_BUCKET="${S3_BUCKET:-}"
REGION="eu-west-1"
DEFAULT_S3_BUCKET="ai-bot-prod-artifacts"

case "$TARGET" in
  all)
    LAMBDAS=(
      "transcribe-bot"
      "transcribe-bot-worker"
      "transcribe-bot-drive-worker"
      "transcribe-bot-transcript"
    )
    ;;
  main)
    LAMBDAS=("transcribe-bot")
    ;;
  worker)
    LAMBDAS=("transcribe-bot-worker")
    ;;
  drive)
    LAMBDAS=("transcribe-bot-drive-worker")
    ;;
  transcript)
    LAMBDAS=("transcribe-bot-transcript")
    ;;
  *)
    echo "Usage: $0 [main|worker|drive|transcript]"
    exit 1
    ;;
esac

if [[ -z "$S3_BUCKET" ]]; then
  S3_BUCKET="$DEFAULT_S3_BUCKET"
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Error: python3 is not available on PATH."
  exit 1
fi

echo "========================================"
echo "Deploying Lambda(s)"
echo "  Region:  $REGION"
echo "  Target:  $TARGET"
echo "  Profile: $PROFILE"
echo "========================================"

echo "==> Cleaning build artifacts"
rm -rf "$BUILD_DIR" "$ZIP_NAME"
mkdir -p "$BUILD_DIR"

if [[ -s "$REQ_FILE" ]]; then
  echo "==> Installing dependencies"
  python3 -m pip install -r "$REQ_FILE" \
    --platform manylinux2014_x86_64 \
    --python-version 312 \
    --only-binary=:all: \
    --implementation cp \
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
  for LAMBDA_NAME in "${LAMBDAS[@]}"; do
    S3_KEY="${LAMBDA_NAME}/deploy-$(date +%Y%m%d%H%M%S).zip"
    echo "==> Uploading deployment zip to s3://$S3_BUCKET/$S3_KEY"
    aws s3 cp "$ZIP_NAME" "s3://$S3_BUCKET/$S3_KEY" \
      --region "$REGION" \
      --profile "$PROFILE" \
      --no-cli-pager

    echo "==> Updating ${LAMBDA_NAME} from S3"
    aws lambda update-function-code \
      --function-name "$LAMBDA_NAME" \
      --s3-bucket "$S3_BUCKET" \
      --s3-key "$S3_KEY" \
      --region "$REGION" \
      --profile "$PROFILE" \
      --no-cli-pager \
      --query 'FunctionArn' \
      --output text
  done
else
  for LAMBDA_NAME in "${LAMBDAS[@]}"; do
    echo "==> Uploading to AWS Lambda: ${LAMBDA_NAME}"
    aws lambda update-function-code \
      --function-name "$LAMBDA_NAME" \
      --zip-file "fileb://$ZIP_NAME" \
      --region "$REGION" \
      --profile "$PROFILE" \
      --no-cli-pager \
      --query 'FunctionArn' \
      --output text
  done
fi

echo "✅ Deployment complete."
