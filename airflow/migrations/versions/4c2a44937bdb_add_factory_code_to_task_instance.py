#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""add factory_code to task instance

Revision ID: 4c2a44937bdb
Revises: 4ccdfe292cdc
Create Date: 2020-07-08 10:49:28.239610

"""

# revision identifiers, used by Alembic.
revision = '4c2a44937bdb'
down_revision = '4ccdfe292cdc'
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('task_instance', sa.Column('factory_code', sa.String(100)))


def downgrade():
    op.drop_column('task_instance', 'factory_code')
