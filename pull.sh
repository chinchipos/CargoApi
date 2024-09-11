#!/usr/bin/bash

git pull origin experimental
chmod u+x ./*.sh
chmod u+x ./alembic_make_revision
chmod u+x ./alembic_upgrade_db
