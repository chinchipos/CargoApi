#!/usr/bin/bash

source /home/cargo/env/bin/activate
cd /home/cargo/cargonomica/api
celery -A src.celery_app.main:celery purge -f
celery -A src.celery_app.main:celery worker --loglevel=ERROR
deactivate
