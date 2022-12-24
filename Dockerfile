FROM ubuntu:22.04
LABEL maintainer="Sandor Balazsi <sandor.balazsi@gmail.com>"

ENV DEBIAN_FRONTEND=noninteractive
ENV DEBCONF_NOWARNINGS=yes
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONPYCACHEPREFIX=/tmp
RUN apt-get update && apt-get install --yes \
      software-properties-common psmisc \
      python3 python3-pip \
    && pip3 install --upgrade pip \
    && pip3 install marionette_driver exchangelib \
      google-api-python-client google-auth-httplib2 google-auth-oauthlib

COPY files/firefox_force_deb.pref /etc/apt/preferences.d
RUN add-apt-repository --yes ppa:mozillateam/ppa \
    && apt-get install --yes firefox
COPY files/firefox_settings.js /usr/lib/firefox/defaults/pref

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /workdir
ENV PATH=$PATH:/workdir
