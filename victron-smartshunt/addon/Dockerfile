FROM python:3.11-alpine

ARG BUILD_VERSION
ARG BUILD_ARCH

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir 'pyserial==3.5' 'paho-mqtt==2.1.0'

COPY run.sh /run.sh
COPY shunt.py /shunt.py
RUN chmod a+x /run.sh

CMD ["/run.sh"]
