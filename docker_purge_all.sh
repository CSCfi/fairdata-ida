#!/bin/bash
docker swarm leave --force 2>/dev/null
docker rmi -f `docker images -qa` 2>/dev/null
docker volume rm $(docker volume ls -q) 2>/dev/null
docker system prune -a -f
