#!/usr/bin/bash

source /home/cargo/env/bin/activate
cd /home/cargo/cargonomica/api || exit
celery -A src.celery_app.main:celery purge -f
celery -A src.celery_app.main:celery worker --loglevel=INFO
deactivate
