# vim: set ts=4:et
from charmhelpers.core.hookenv import (
    config,
    relation_ids,
    related_units,
    relation_get,
    local_unit,
    unit_get,
    log
)
from charmhelpers.contrib.openstack.context import (
    OSContextGenerator,
    HAProxyContext,
    context_complete
)
from charmhelpers.contrib.hahelpers.apache import (
    get_cert
)
from charmhelpers.contrib.network.ip import (
    get_ipv6_addr
)

from charmhelpers.core.host import pwgen

from base64 import b64decode
import os


class HorizonHAProxyContext(HAProxyContext):
    def __call__(self):
        '''
        Horizon specific HAProxy context; haproxy is used all the time
        in the openstack dashboard charm so a single instance just
        self refers
        '''
        cluster_hosts = {}
        l_unit = local_unit().replace('/', '-')
        if config('prefer-ipv6'):
            cluster_hosts[l_unit] = get_ipv6_addr(exc_list=[config('vip')])[0]
        else:
            cluster_hosts[l_unit] = unit_get('private-address')

        for rid in relation_ids('cluster'):
            for unit in related_units(rid):
                _unit = unit.replace('/', '-')
                addr = relation_get('private-address', rid=rid, unit=unit)
                cluster_hosts[_unit] = addr

        log('Ensuring haproxy enabled in /etc/default/haproxy.')
        with open('/etc/default/haproxy', 'w') as out:
            out.write('ENABLED=1\n')

        ctxt = {
            'units': cluster_hosts,
            'service_ports': {
                'dash_insecure': [80, 70],
                'dash_secure': [443, 433]
            }
        }
        return ctxt


class IdentityServiceContext(OSContextGenerator):
    def __call__(self):
        ''' Provide context for Identity Service relation '''
        ctxt = {}
        for r_id in relation_ids('identity-service'):
            for unit in related_units(r_id):
                ctxt['service_host'] = relation_get('service_host',
                                                    rid=r_id,
                                                    unit=unit)
                ctxt['service_port'] = relation_get('service_port',
                                                    rid=r_id,
                                                    unit=unit)
                ctxt['service_protocol'] = relation_get('service_protocol',
                                                        rid=r_id,
                                                        unit=unit) or 'http'
                if context_complete(ctxt):
                    return ctxt
        return {}


class HorizonContext(OSContextGenerator):
    def __call__(self):
        ''' Provide all configuration for Horizon '''
        ctxt = {
            'compress_offline': config('offline-compression') in ['yes', True],
            'debug': config('debug') in ['yes', True],
            'default_role': config('default-role'),
            "webroot": config('webroot'),
            "ubuntu_theme": config('ubuntu-theme') in ['yes', True],
            "secret": config('secret') or pwgen(),
            'support_profile': config('profile')
            if config('profile') in ['cisco'] else None,
            "neutron_network_lb": config("neutron-network-lb"),
            "neutron_network_firewall": config("neutron-network-firewall"),
            "neutron_network_vpn": config("neutron-network-vpn"),
        }

        return ctxt


class ApacheContext(OSContextGenerator):
    def __call__(self):
        ''' Grab cert and key from configuraton for SSL config '''
        ctxt = {
            'http_port': 70,
            'https_port': 433
        }
        return ctxt


class ApacheSSLContext(OSContextGenerator):
    def __call__(self):
        ''' Grab cert and key from configuration for SSL config '''
        (ssl_cert, ssl_key) = get_cert()
        if None not in [ssl_cert, ssl_key]:
            with open('/etc/ssl/certs/dashboard.cert', 'w') as cert_out:
                cert_out.write(b64decode(ssl_cert))
            with open('/etc/ssl/private/dashboard.key', 'w') as key_out:
                key_out.write(b64decode(ssl_key))
            os.chmod('/etc/ssl/private/dashboard.key', 0600)
            ctxt = {
                'ssl_configured': True,
                'ssl_cert': '/etc/ssl/certs/dashboard.cert',
                'ssl_key': '/etc/ssl/private/dashboard.key',
            }
        else:
            # Use snakeoil ones by default
            ctxt = {
                'ssl_configured': False,
            }
        return ctxt


class RouterSettingContext(OSContextGenerator):
    def __call__(self):
        ''' Enable/Disable Router Tab on horizon '''
        ctxt = {
            'disable_router': False if config('profile') in ['cisco'] else True
        }
        return ctxt
