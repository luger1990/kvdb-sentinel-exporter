#!/bin/bash

# 检查是否传入了 TAG 参数
if [ -z "$1" ]; then
  echo "❌ Error: TAG parameter is missing."
  echo "Usage: $0 <tag>"
  exit 1
fi

TAG="$1"
IMAGE_NAME="luger1990/kvdb-sentinel-exporter"

# 构建镜像
echo "🚀 Building image ${IMAGE_NAME}:${TAG}..."
docker build -t ${IMAGE_NAME}:${TAG} .
if [ $? -ne 0 ]; then
  echo "❌ Docker build failed!"
  exit 1
fi

# 确认是否推送镜像
read -p "❓ Do you want to push the image '${IMAGE_NAME}:${TAG}' and 'latest'? [Y/n]: " confirm
confirm=${confirm:-n}

if [[ "$confirm" != [Yy] ]]; then
  echo "❌ Push aborted by user."
  exit 0
fi

# 推送指定版本
echo "📦 Pushing image ${IMAGE_NAME}:${TAG}..."
docker push ${IMAGE_NAME}:${TAG}
if [ $? -ne 0 ]; then
  echo "❌ Docker push for ${TAG} failed!"
  exit 1
fi

# 给镜像打上 latest 标签
echo "🏷️ Tagging image ${IMAGE_NAME}:latest..."
docker tag ${IMAGE_NAME}:${TAG} ${IMAGE_NAME}:latest

# 推送 latest 版本
echo "📦 Pushing image ${IMAGE_NAME}:latest..."
docker push ${IMAGE_NAME}:latest
if [ $? -ne 0 ]; then
  echo "❌ Docker push for latest failed!"
  exit 1
fi

echo "✅ All done!"
