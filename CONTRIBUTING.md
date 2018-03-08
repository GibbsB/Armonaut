# Contributing to Armonaut

Thanks for considering contributing to Armonaut! Before contributing make sure you
are capable of and willing for your work being released under the
[Apache-2.0 license](https://github.com/SethMichaelLarson/Armonaut/blob/master/LICENSE)
such as if you're currently working for a client or corporation.

## Setting up your Tools and Workspace

This guide is written for Ubuntu 17.10 but the workflow will be similar compared to other Linux platforms.
Development is going to be tough on Windows systems because of Docker-Compose so I sadly can't recommend Windows
for anything beyond small changes. Sorry! (I use VirtualBox to virtualize Ubuntu 17.10 on my desktop)

Ensure that when you execute `python3 --version` the output is similar to the following:
```bash
$ python3 --version
Python 3.6.4
```

**NOTE:** Ubuntu 17.10 packages Python 3.6 by default. Armonaut requires Python 3.6+.
If you're using a different platform you must install Python 3.6 along with virtualenv
and pip another way.  I suggest [`pyenv`](https://github.com/pyenv/pyenv) but there are
other ways as well. Google is your friend!

### Installing Dependencies

```bash
sudo apt-get update
sudo apt-get install -y git \
                        build-essential \
                        apt-transport-https \
                        ca-certificates \
                        curl \
                        software-properties-common \
                        python3-venv \
                        python3-pip \
                        python3-dev \
                        libffi-dev
```

### Installing Docker Community Edition

```bash
# Installing Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get update
sudo apt-get install -y docker-ce

# Starting the dockerd service and making it auto-start on boot.
sudo service docker start
sudo systemctl enable docker

# Create the docker group and add the current user to the group.
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker # This command logs you into the docker group
```

After installing everything you should be able to run the following command:

**NOTE:** At the time of writing this the version of Docker CE was 17.12.0

```bash
$ docker --version
Docker version 17.12.0-ce, build c97c6d6
```

### Installing Docker-Compose

```bash
sudo curl -L https://github.com/docker/compose/releases/download/1.18.0/docker-compose-`uname -s`-`uname -m` -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

After installing this you should be able to run the following command:

**NOTE:** At the time of writing this the version of Docker CE was 1.18.0

```bash
docker-compose --version
```

### Creating a Fork of Armonaut

Sign in with your GitHub account and click the [fork] button for Armonaut.
This should create a repository in your GitHub account named `[YOUR ACCOUNT]/Armonaut`.

Open a terminal and `cd` to a directory where you'd like your fork to reside.
Run the following command in the terminal:

```bash
git clone https://github.com/[YOUR ACCOUNT]/Armonaut
```

After this completes there should be a directory in your current working directory
named `Armonaut`. Use `cd` to go into this directory.

Now we're going to set our upstream remote so that we can get upstream changes later.

```bash
git remote add upstream https://github.com/Armonaut/Armonaut
```

**NOTE:** Collaborators can use branches besides Master within the `Armonaut/Armonaut` repository.

### Setting up a Virtualenv

```bash
python -m venv venv/
source venv/bin/activate
python -m pip install -r requirements.txt -r dev-requirements.txt
```

From here you should have a functional fork for Armonaut. You can make sure you've
got everything configured properly by running the unit tests and integration tests (see below) 

To update all your dependencies use the following command:

```bash
python -m pip install -U -r requirements.txt -r dev-requirements.txt
```

To deactivate that virtualenv use the following command:

```bash
deactivate
```

### Building all Docker images with Docker-Compose

Run the following command to pull all containers required for running
Armonaut locally in development mode.

**NOTE:** This command will take a while to execute the first time.
Any time your run this command after this will be much faster due to caching of containers and their layers.
Every time you modify code should only take a few seconds to run the next time.

```bash
python -m armonaut ctrl up
# To stop hosting locally use Ctrl+C
```

With the containers running you should be able to open a browser and navigate to `http://localhost`
and see the Armonaut home-page.

Whenever you make modifications to the Armonaut codebase run the following commands to update the containers:

```bash
python -m armonaut ctrl build
```

### Syncing your Fork with the latest `master` branch

When your local fork becomes out of date with other changes that have been merged into `master`
you must update your local fork in order to make merging future Pull Requests from your fork go smoothly.

```bash
# Checkout the `master` branch
git checkout master

# Reset hard against HEAD to make sure you have no local changes
git reset --hard HEAD

# Pull the latest changes from `upstream/master`
git pull upstream master

# Push the latest changes to GitHub for your fork
git push origin master
```

### Installing PyCharm (Optional)

PyCharm (created by JetBrains) is the IDE that I use to develop Armonaut.
I highly suggest it for people who don't already have a workflow solidified.

```bash
sudo apt-get install -y ubuntu-make
umake ide pycharm
```

**NOTE:** If you're using Ubuntu <=17.04 then you must add the following repository before installing `umake`.
```bash
sudo add-apt-repository -y ppa:ubuntu-desktop/ubuntu-make
sudo apt-get update
```

Once you launch and open Armonaut in your PyCharm IDE go into `File -> Settings -> Project: Armonaut -> Project Interpreter`
select the gear/cog to add a local virtual environment. Select `Existing Environment` and choose your `.../Armonaut/venv/bin/python`.
This will allow you to use hinting and auto-complete for all your installed modules.

## Making Changes to Armonaut

### Running Tests

Before submitting and throughout development of your change you should run the test suite.
To run the entire test suite (which should be done before committing!) run the following
command:

```bash
python -m armonaut ctrl test
```

See below on how to run subsets of the test suite.

#### Running Unit Tests

Unit tests are smaller and faster running tests that only test specific sub-components
of the system instead of the system as a whole.

Unit tests are run and must pass for each commit that is submitted to GitHub.

```bash
python -m armonaut ctrl test tests/unit/
```

#### Running Integration Tests

Integration tests are longer tests that test the full functionality of the system
and launch browsers to ensure that the web application renders correctly on
all major browsers. Only run integration tests once all unit tests are passing.

Integration tests are run and must pass for each commit that is submitted to GitHub.

```bash
python -m armonaut ctrl test tests/integration/
```

#### Running A Specific Test

If you want to just run one set of tests within a file you can pass just the file
path and only those tests will be executed.

```bash
python -m armonaut ctrl test tests/unit/test_sessions.py
```

### Debugging with a Shell

This will start all containers except the web container and allow you to debug
the container itself if needed. Press Ctrl+D to exit the shell session.

```bash
python -m armonaut ctrl shell
```

### Using the Pyramid Debug Toolbar

The debug toolbar can be found by clicking the red box on the right side of
any page rendered on the web application running in `DEVELOPMENT` mode.
After clicking this button you will be brought to a menu with many options
for debugging how the views and requests are processed by the web application.

Use this for initial performance testing and debugging purposes.

See additional [documentation about the toolbar](https://docs.pylonsproject.org/projects/pyramid_debugtoolbar/en/latest/#usage) for more information.

### Linting your Code with Flake8

Armonaut uses [flake8](http://flake8.pycqa.org/en/latest/) as a code linting tool
in order to catch defects and to keep code maintainability high. Our only modification
to flake8's default configuration is increasing maximum line length to 99 characters
instead of 79 due to modern IDEs and screen sizes.

You can run this command whenever the virtualenv is active:

```bash
python -m armonaut ctrl lint
```

### Style Guide

- In general follow [PEP8](https://www.python.org/dev/peps/pep-0008/#module-level-dunder-names).
- Use single quotes (`'`) for single-line strings.
- Use triple-double quotes (`"""`) for docstrings.
- Docstrings should have no spaces after triple-double quotes
  and should end with the closing triple-double quotes on their own line.
  ```python
  def function():
      """This is a doc-string.
      """
      return 'ret'
  ```
- Doc-string parameters and return types should be like this:
  ```python
  def add(x, y):
      """Adds two integers

      :param x: Operand 1
      :param y: Operand 2
      :type x: int
      :type y: int
      :rtype: int
      :returns: Sum of two integers
      """
      return x + y
  ```

## Submitting Pull Requests

- Always follow the template for Pull Requests and issues to help save time analyzing and reviewing.
  Pull Requests or issues that don't follow the template will be closed and the author directed to this guide.
- Small one-off changes like spelling, grammar, docstrings, etc do not require an issue to be made.
- Before considering submitting a Pull Request, open and issue to start a discussion
  so other community members can chime in about the problem you'd like to fix or
  enhancement you'd like to make.
- Pull Request title should be a short description of the changes being made.
- Within the Pull Request body should have the phrase `Closes #123` where `123`
  is the issue that has been created for the changes within the Pull Request.
- Commit early and often! Your Pull Request will be squashed into one commit when merged.
- Unless the Pull Request is against 
- **Important for Collaborators**: When merging commits make sure to include a short description of the changes in the Pull Request
  as well as a listing of all individual changes in the long message. Include the Pull Request number
  (eg: `This is a summary of changes (#123)` in the commit summary.

## Creating a Release

- Releases should always be tagged on the `master` branch.
- Tags should always be the exact version string (ie `1.0.0` not `v1.0.0`, etc)
- When creating a release there should be a Pull Request to the `master` branch with the
  only changes being incrementing the `__version__` string in `armonaut/__about__.py` and
  changing `CHANGELOG.md` to not mention `Unreleased` and instead point to the tagged release
  and commits.
- Use a rebase merge for committing to `master`, not squash.

## Additional Documentation

- [Pyramid](https://trypyramid.com/)
- [Pyramid Debugtoolbar](https://docs.pylonsproject.org/projects/pyramid_debugtoolbar/en/latest)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [PyCharm](https://www.jetbrains.com/pycharm/documentation/)
- [Pytest](https://docs.pytest.org/en/latest/contents.html)
- [Needle](https://needle.readthedocs.io/en/latest/)
- [Docker](https://docs.docker.com/)
- [Flake8](http://flake8.pycqa.org/en/latest/)
