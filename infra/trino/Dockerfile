FROM trinodb/trino:483

# PostgreSQL JDBC driver for the Iceberg JDBC metadata catalog.
# Downloaded by `make infra-libs` (see infra/trino/lib/).
COPY lib/postgresql.jar /usr/lib/trino/plugin/iceberg/postgresql.jar