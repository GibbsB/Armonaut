FROM ubuntu:17.10

# Python doesn't like LC_ALL=C/LANG=C
ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

# Install packages which are less likely to change.
RUN apt-get update && \
    apt-get install -y build-essential \
                       curl \
                       libssl-dev \
                       libffi-dev \
                       python3-dev \
                       python3-pip \
                       python3-venv \
                       postgresql \
                       libpq-dev && \
    cd /usr/bin && \
    ln -s idle3 idle && \
    ln -s pydoc3 pydoc && \
    ln -s python3 python && \
    ln -s pip3 pip && \
    ln -s python3-config python-config

WORKDIR /opt/armonaut

# Install Python requirements before copying code over so they
# won't be installed whenever code changes.
COPY requirements.txt dev-requirements.txt /opt/armonaut/
RUN python -m pip install -r requirements.txt -r dev-requirements.txt

# Finally copy our code over which will change often.
ADD . /opt/armonaut

# Remove all __pycache__ files as they mess with pytest
RUN find . | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf
