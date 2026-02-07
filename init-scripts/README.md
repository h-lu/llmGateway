# Postgres Init Scripts

This directory is mounted into the Postgres container at
`/docker-entrypoint-initdb.d` to allow optional initialization (schema, roles,
extensions) on first boot.

If you don't need any init scripts, it's safe for this directory to be empty.

