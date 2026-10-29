#!/bin/sh
# Runs once, on the first start of an empty data volume.
# Creates the runtime roles with passwords; the baseline migration then skips
# creating them and only grants privileges.
set -eu

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v app_pw="$EDUZONE_APP_PASSWORD" -v admin_pw="$EDUZONE_ADMIN_PASSWORD" <<'SQL'
CREATE ROLE eduzone_app LOGIN PASSWORD :'app_pw';
CREATE ROLE eduzone_admin LOGIN BYPASSRLS PASSWORD :'admin_pw';
SQL
