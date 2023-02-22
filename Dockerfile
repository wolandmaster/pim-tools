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
      google-api-python-client google-auth-httplib2 google-auth-oauthlib \
      python-dateutil

RUN printf '%s\n' \
      'Package: *' \
      'Pin: release o=LP-PPA-mozillateam' \
      'Pin-Priority: 1001' >/etc/apt/preferences.d/firefox_force_deb.pref \
    && add-apt-repository --yes ppa:mozillateam/ppa \
    && apt-get install --yes firefox \
    && printf '%s\n' \
      'pref("full-screen-api.ignore-widgets", true);' \
      > /usr/lib/firefox/defaults/pref/firefox_settings.js

RUN rm -rf /var/lib/apt/lists/*

WORKDIR /workdir
ENV PATH=$PATH:/workdir
