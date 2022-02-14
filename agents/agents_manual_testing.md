# Testing the batch freeze logic

Batch messages should only be consumed once all standard messages have been consumed. This can be tested in Docker as follows:

1. Enter Nextcloud container
```
docker exec -it $(docker ps -q -f name=ida-nextcloud) sudo su -l www-data -s /bin/bash
```

2. Generate files for test_project_a and test_project_b
```
cd /var/ida/tests/utils
./initialize_max_files test_project_a
./initialize_max_files test_project_b
```

3. Login to ida.fd-dev.csc.fi as "test_user_a"/"test"

4. Go to the "staging" area

5. Go to folder "test_project_a/testdata/MaxFiles/5000_files/500_files_1"

6. In the UI, manually freeze four (4) of the folders by clicking "Freeze" -> "Yes"

7. Back in the Nextcloud container, do a batch freeze for test_project_b:
```
cd /var/ida/utils/admin
./execute-batch-action test_project_b freeze /testdata/MaxFiles/5000_files/500_files_1/100_files_1
./execute-batch-action test_project_b freeze /testdata/MaxFiles/5000_files/500_files_1/100_files_2
./execute-batch-action test_project_b freeze /testdata/MaxFiles/5000_files/500_files_1/100_files_3
```

8. In the UI, manually freeze the last (1) of the folders

9. Go to 0.0.0.0:15672 (RabbitMQ web console), login with "admin"/"test"

10. Go to "Queues" and observe the results.

The `metadata` and `replication` queues should be utilized for the five (5) messages coming from the UI actions. The `batch-metadata` and `batch-metadata` queues should be utilized for the (1) message coming from the batch freeze action.

11. All messages in the `metadata` queue should be consumed before the message in `batch-metadata` is processed.

This can be verified by checking the "Completed" timestamp on each of the actions.
