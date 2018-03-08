# Copyright 2018 Seth Michael Larson
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pretend
from armonaut.utils.crypto import random_token


def test_random_token(monkeypatch):
    urandom = pretend.call_recorder(lambda _: b'7f\xd2\xe2\xc4\x978p%\xf3\xdc-8ri\xbc\x02\x9e\x9a\xaf>K\xa6\x87\x9e$CpE\x8af\xbd')
    monkeypatch.setattr(os, 'urandom', urandom)

    token = random_token()

    assert token == 'N2bS4sSXOHAl89wtOHJpvAKemq8-S6aHniRDcEWKZr0'
    assert urandom.calls == [pretend.call(32)]
