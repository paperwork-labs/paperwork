#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE filefree_test OWNER $POSTGRES_USER;
    CREATE DATABASE launchfree_dev OWNER $POSTGRES_USER;
    CREATE DATABASE brain_dev OWNER $POSTGRES_USER;
EOSQL
