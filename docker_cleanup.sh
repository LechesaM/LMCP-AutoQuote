#!/bin/bash

echo "----------------------------------"
echo "LMCP Docker Maintenance Started"
date
echo "----------------------------------"

# Remove stopped containers
docker container prune -f

# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove unused networks
docker network prune -f

# Remove build cache
docker builder prune -a -f

echo "----------------------------------"
echo "Docker disk usage after cleanup:"
docker system df
echo "----------------------------------"

echo "LMCP Docker Maintenance Complete"
date
