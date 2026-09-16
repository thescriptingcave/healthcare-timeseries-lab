FROM apache/superset:109402b

USER root

COPY patch_trino_dialect.py /tmp/patch_trino_dialect.py

RUN pip install --no-cache-dir "sqlalchemy-trino==0.4.0" \
    && sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' /app/.venv/pyvenv.cfg \
    && /usr/local/bin/python /tmp/patch_trino_dialect.py \
    && rm /tmp/patch_trino_dialect.py

USER superset