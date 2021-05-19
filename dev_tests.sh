#!/bin/bash

run_tests() {
  docker exec -it $(docker ps -q -f name=ida-nextcloud) tests/run-tests
}

run_tests
