#!/bin/bash -e

sed -e "s=HOST_NAME=$(hostname -s)=g" \
	-e "s=DOMAIN_NAME=${DOMAIN_NAME}=g" \
	-e "s=REALM_NAME=${REALM_NAME}=g" \
	/etc/krb5.conf.template > /etc/krb5.conf

sed -e "s/^kdc *=.*/kdc = STDERR/" -i /etc/heimdal-kdc/kdc.conf

echo package heimdal/realm string ${REALM_NAME} | debconf-set-selections
dpkg-reconfigure -f noninteractive heimdal-kdc

echo
echo PRINCIPALS
echo ==========
env | egrep "^PRINCIPAL_" | cut -d= -f2- | while IFS=: read -r PRINCIPAL PASSWORD; do
	echo "${PRINCIPAL}:${PASSWORD}"
	kadmin -l add --password="${PASSWORD}" --use-defaults "${PRINCIPAL}"
done

echo
echo KEYTABS
echo =======
env | egrep "^KEYTAB_" | cut -d= -f2- | while IFS=: read -r PRINCIPAL KEYTAB; do
	KEYTAB="${KEYTAB:-foo}"
	kadmin -l ext_keytab -k "/export/${KEYTAB}" "${PRINCIPAL}"
	echo "${KEYTAB}: $(base64 -w 0 "/export/${KEYTAB}")"
done

nohup python -m SimpleHTTPServer 8000 &

echo
echo KDC LOGS
echo ========
exec /usr/lib/heimdal-servers/kdc --config-file=/etc/heimdal-kdc/kdc.conf -P 88
