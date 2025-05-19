#!/bin/bash
# Run AIGYM smoke tests

# Set colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}AIGYM Smoke Test Runner${NC}"
echo "=================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo -e "${RED}Error: Docker is not running. Please start Docker and try again.${NC}"
  exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
  echo -e "${RED}Error: docker-compose is not installed. Please install it and try again.${NC}"
  exit 1
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
  echo -e "${RED}Error: Python 3 is not installed. Please install it and try again.${NC}"
  exit 1
fi

echo -e "${YELLOW}Checking if AIGYM services are running...${NC}"
RUNNING_CONTAINERS=$(docker ps --format '{{.Names}}' | grep aigym | wc -l)

if [ "$RUNNING_CONTAINERS" -lt 7 ]; then
  echo -e "${YELLOW}Starting AIGYM services with docker-compose...${NC}"
  docker-compose up -d
  
  # Wait for services to be ready
  echo -e "${YELLOW}Waiting for services to be ready...${NC}"
  sleep 10
else
  echo -e "${GREEN}AIGYM services are already running.${NC}"
fi

# Install required Python packages for the smoke test
echo -e "${YELLOW}Installing required Python packages...${NC}"
pip install psycopg2-binary redis requests qdrant-client

# Run the smoke test
echo -e "${YELLOW}Running smoke tests...${NC}"
python3 tests/smoke_test.py

# Check the result
if [ $? -eq 0 ]; then
  echo -e "${GREEN}Smoke tests completed successfully!${NC}"
  exit 0
else
  echo -e "${RED}Smoke tests failed! Check the logs above for details.${NC}"
  exit 1
fi