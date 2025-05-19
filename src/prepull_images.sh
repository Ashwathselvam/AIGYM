#!/bin/bash

# Script to pre-pull Docker images for solution runner

# List of standard images to pull
IMAGES=(
  "python:3.11-slim"
  "node:16-slim"
  "openjdk:17-slim"
  "gcc:11"
  "golang:1.19"
  "rust:1.68"
)

echo "Pre-pulling Docker images for solution-runner..."

# Pull each image
for image in "${IMAGES[@]}"; do
  echo "Pulling $image..."
  docker pull "$image"
done

echo "All images pulled successfully!" 