# -*- coding: utf-8 -*-
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

import json
from builtins import bytes
from typing import Any, List

from sqlalchemy import Column, Integer, String, Text, Boolean
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import synonym

from airflow.models.base import ID_LEN, Base
from airflow.models.crypto import get_fernet, InvalidFernetToken
from airflow.utils.db import provide_session
from airflow.utils.log.logging_mixin import LoggingMixin
from airflow.secrets import get_variable


class Variable(Base, LoggingMixin):
    __tablename__ = "variable"
    __NO_DEFAULT_SENTINEL = object()

    id = Column(Integer, primary_key=True)
    key = Column(String(ID_LEN), unique=True)
    is_curve_template = Column(Boolean, default=True)
    active = Column(Boolean, default=True)
    _val = Column('val', Text)
    is_encrypted = Column(Boolean, unique=False, default=False)

    def __repr__(self):
        # Hiding the value
        return '{} : {}'.format(self.key, self._val)

    def get_val(self):
        log = LoggingMixin().log
        if self._val is not None and self.is_encrypted:
            try:
                fernet = get_fernet()
                return fernet.decrypt(bytes(self._val, 'utf-8')).decode()
            except InvalidFernetToken:
                log.error("Can't decrypt _val for key={}, invalid token "
                          "or value".format(self.key))
                return None
            except Exception as e:
                log.error("Can't decrypt _val for key={}, FERNET_KEY "
                          "configuration missing: {}".format(self.key, repr(e)))
                return None
        else:
            return self._val

    def set_val(self, value):
        if value is not None:
            fernet = get_fernet()
            self._val = fernet.encrypt(bytes(value, 'utf-8')).decode()
            self.is_encrypted = fernet.is_encrypted
        else:
            self._val = None
            self.is_encrypted = False

    @declared_attr
    def val(cls):
        return synonym('_val',
                       descriptor=property(cls.get_val, cls.set_val))

    @classmethod
    def setdefault(cls, key, default, deserialize_json=False):
        """
        Like a Python builtin dict object, setdefault returns the current value
        for a key, and if it isn't there, stores the default value and returns it.

        :param key: Dict key for this Variable
        :type key: str
        :param default: Default value to set and return if the variable
            isn't already in the DB
        :type default: Mixed
        :param deserialize_json: Store this as a JSON encoded value in the DB
            and un-encode it when retrieving a value
        :return: Mixed
        """
        obj = Variable.get(key, default_var=None,
                           deserialize_json=deserialize_json)
        if obj is None:
            if default is not None:
                Variable.set(key, default, serialize_json=deserialize_json)
                return default
            else:
                raise ValueError('Default Value must be set')
        else:
            return obj

    @classmethod
    @provide_session
    def get(
        cls,
        key,  # type: str
        default_var=__NO_DEFAULT_SENTINEL,  # type: Any
        deserialize_json=False,  # type: bool
        session=None,
        is_all=False,
        fun_filter=lambda cls, key: cls.key == key
    ):
        objs = session.query(cls).filter(fun_filter(cls, key))
        if is_all:
            return objs.all()
        obj = objs.first()
        if obj is None:
            if default_var is not cls.__NO_DEFAULT_SENTINEL:
                return default_var
            else:
                raise KeyError('Variable {} does not exist'.format(key))
        else:
            if deserialize_json:
                return json.loads(obj.val)
            else:
                return obj.val

    @classmethod
    @provide_session
    def get_all_active_curve_tmpls(cls, session=None):
        tmpls: List[cls] = session.query(cls).filter(cls.active, cls.is_curve_template).all()
        ret = {}
        for tmpl in tmpls:
            ret[tmpl.key] = tmpl.val
        return ret

    @classmethod
    @provide_session
    def get_fuzzy_active(
        cls,
        key,  # type: str
        deserialize_json=False,  # type: bool
        session=None,
        default_var=__NO_DEFAULT_SENTINEL
    ):
        key_p = "%{}%".format(key)
        obj = session.query(cls).filter(cls.key.like(key_p), cls.active).first()
        if obj is None:
            if default_var is not cls.__NO_DEFAULT_SENTINEL:
                return key, default_var
            raise KeyError('Variable {} does not exist'.format(key))
        if deserialize_json:
            return obj.key, json.loads(obj.val)
        return obj.key, obj.val

    @classmethod
    @provide_session
    def set(
        cls,
        key,  # type: str
        value,  # type: Any
        serialize_json=False,  # type: bool
        is_curve_template=False,  # type: bool
        session=None
    ):

        if serialize_json:
            stored_value = json.dumps(value, indent=2, separators=(',', ': '), ensure_ascii=False)
        else:
            stored_value = str(value)

        Variable.delete(key, session=session)
        session.add(Variable(
            key=key,
            val=stored_value,
            is_curve_template=is_curve_template
        ))  # type: ignore
        session.flush()

    @classmethod
    @provide_session
    def update(
        cls,
        key,  # type: str
        value,  # type: Any
        serialize_json=False,  # type: bool
        session=None
    ):

        if serialize_json:
            stored_value = json.dumps(value, indent=2, separators=(',', ': '))
        else:
            stored_value = str(value)
        session.query(cls).filter(cls.key == key).update({cls.val: stored_value})  # type: ignore
        session.flush()

    @classmethod
    @provide_session
    def delete(cls, key, session=None):
        session.query(cls).filter(cls.key == key).delete()

    def rotate_fernet_key(self):
        fernet = get_fernet()
        if self._val and self.is_encrypted:
            self._val = fernet.rotate(self._val.encode('utf-8')).decode()
