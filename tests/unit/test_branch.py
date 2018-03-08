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

import re
import os
import pytest
import subprocess
import semver
from armonaut.__about__ import __version__

GIT_BRANCH = subprocess.check_output('git rev-parse --abbrev-ref HEAD', shell=True).strip()

# These tests only run on the master branch. They're used for checking the __version__ string and CHANGELOG format.
master_branch_only = pytest.mark.skipif(GIT_BRANCH != 'master', reason='Test only runs on the master branch.')

develop_branch_only = pytest.mark.skipif(GIT_BRANCH == 'master', reason='Test only runs on the non-master branches.')


def test__version__():
    assert semver.parse(__version__) is not None


@master_branch_only
def test_master_changelog():
    changelog = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'CHANGELOG.md'
    )

    with open(changelog) as f:
        data = f.read()

        assert '## [Unreleased]' not in data
        assert f'## [{__version__}]' in data
        assert f'[{__version__}]: https://github.com/Armonaut/Armonaut/compare' in data


@develop_branch_only
def test_develop_changelog():
    changelog = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'CHANGELOG.md'
    )

    with open(changelog) as f:
        data = f.read()

        assert '## [Unreleased]' in data

        match = re.search(r'\[Unreleased\]: https://github\.com/Armonaut/Armonaut/compare/[a-f0-9]+...HEAD', data)
        assert match is not None
