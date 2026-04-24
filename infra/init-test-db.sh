#!/bin/bash
# Creates per-product dev and test databases on first postgres boot.
# The POSTGRES_DB env var already creates `filefree_dev` (the default).
# This script covers every other database the monorepo needs.
#
# See docs/INFRA.md for the full dev-stack architecture.

set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- FileFree (pytest)
    CREATE DATABASE filefree_test   OWNER $POSTGRES_USER;

    -- LaunchFree
    CREATE DATABASE launchfree_dev  OWNER $POSTGRES_USER;
    CREATE DATABASE launchfree_test OWNER $POSTGRES_USER;

    -- Brain
    CREATE DATABASE brain_dev       OWNER $POSTGRES_USER;
    CREATE DATABASE brain_test      OWNER $POSTGRES_USER;

    -- AxiomFolio
    CREATE DATABASE axiomfolio_dev  OWNER $POSTGRES_USER;
    CREATE DATABASE axiomfolio_test OWNER $POSTGRES_USER;
EOSQL
