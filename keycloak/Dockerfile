FROM quay.io/keycloak/keycloak:26.2.4

COPY realm-export.json /opt/keycloak/data/import/realm-export.json
COPY themes/smarthome /opt/keycloak/themes/smarthome

ENTRYPOINT ["/bin/sh", "-c", "/opt/keycloak/bin/kc.sh start-dev --import-realm --http-port=${PORT:-8080}"]
