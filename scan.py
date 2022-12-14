#!/usr/bin/env python
import subprocess
import dns.resolver
import dns.zone
import dns.query
import tldextract
import requests
import argparse
import random
import socket
import string
import signal
import time
import json
import sys
import os
from multiprocessing import Pool

from contextlib import contextmanager

ROOT_NAMESERVER_LIST = [
    "e.root-servers.net.",
    "h.root-servers.net.",
    "l.root-servers.net.",
    "i.root-servers.net.",
    "a.root-servers.net.",
    "d.root-servers.net.",
    "c.root-servers.net.",
    "b.root-servers.net.",
    "j.root-servers.net.",
    "k.root-servers.net.",
    "g.root-servers.net.",
    "m.root-servers.net.",
    "f.root-servers.net.",
]

GLOBAL_DNS_CACHE = {
    "A": {},
    "NS": {},
    "CNAME": {},
    "SOA": {},
    "WKS": {},
    "PTR": {},
    "MX": {},
    "TXT": {},
    "RP": {},
    "AFSDB": {},
    "SRV": {},
    "A6": {},
}

# http://stackoverflow.com/a/287944/1195812
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class DNSTool:
    def __init__( self, verbose = True ):
        self.verbose = verbose
        self.domain_cache = {}
        self.RECORD_MAP = {
            1: 'A',
            2: 'NS',
            5: 'CNAME',
            6: 'SOA',
            11: 'WKS',
            12: 'PTR',
            15: 'MX',
            16: 'TXT',
            17: 'RP',
            18: 'AFSDB',
            33: 'SRV',
            38: 'A6'
        }

    def get_base_domain( self, hostname ):
        ''' Little extra parsing to accurately return a TLD string '''
        url = "http://" + hostname.lower()
        tld = tldextract.extract( url )
        if tld.suffix == '':
            return tld.domain
        else:
            return "%s.%s" % ( tld.domain, tld.suffix )

    def statusmsg( self, msg, mtype = 'status' ):
        '''
        Status messages
        '''
        if self.verbose:
            if mtype == 'status':
                print '[ STATUS ] ' + msg
            elif mtype == 'warning':
                print bcolors.WARNING + '[ WARNING ] ' + msg + bcolors.ENDC
            elif mtype == 'error':
                print bcolors.FAIL + '[ ERROR ] ' + msg + bcolors.ENDC
            elif mtype == 'success':
                print bcolors.OKGREEN + '[ SUCCESS ] ' + msg + bcolors.ENDC

    def typenum_to_name( self, num ):
        '''
        Turn DNS type number into it's corresponding DNS record name
        e.g. 5 => CNAME, 1 => A
        '''
        if num in self.RECORD_MAP:
            return self.RECORD_MAP[ num ]
        return "UNK"

    @contextmanager
    def time_limit( self, seconds ):
        '''
        Timeout handler to hack around a bug in dnspython with AXFR not obeying it's timeouts 
        '''
        def signal_handler(signum, frame):
            raise Exception("TIMEOUT")
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)

    def get_nameserver_list( self, domain ):
        self.statusmsg( "Grabbing nameserver list for " + domain )

        if domain in GLOBAL_DNS_CACHE[ "NS" ]:
            return GLOBAL_DNS_CACHE[ "NS" ][ domain ]

        '''
        Query the list of authoritative nameservers for a domain

        It is important to query all of these as it only takes one misconfigured server to give away the zone.
        '''
        try:
            answers = dns.resolver.query( domain, 'NS' )
        except dns.resolver.NXDOMAIN:
            self.statusmsg( "NXDOMAIN - domain name doesn't exist", 'error' )
            return []
        except dns.resolver.NoNameservers:
            self.statusmsg( "No nameservers returned!", 'error' )
            return []
        except dns.exception.Timeout:
            self.statusmsg( "Nameserver request timed out (wat)", 'error' )
            return []
        except dns.resolver.NoAnswer:
            self.statusmsg( "No answer", 'error' )
            return []
        except dns.name.EmptyLabel:
            return []
        nameservers = []
        for rdata in answers:
            nameservers.append( str( rdata ) )

        GLOBAL_DNS_CACHE[ "NS" ][ domain ] = nameservers

        return nameservers

    def parse_tld( self, domain ):
        '''
        Parse DNS CNAME external pointer to get the base domain (stolen from moloch's source code, sorry buddy)
        '''
        url = 'http://' + str( domain ) # Hack to get parse_tld to work with us
        tld = tldextract.extract(url)
        if tld.suffix == '':
            return tld.domain
        else:
            return "%s.%s" % (tld.domain, tld.suffix)

    def get_root_tlds( self ):
        self.statusmsg( "Grabbing IANA's list of TLDs...")
        response = requests.get( "https://data.iana.org/TLD/tlds-alpha-by-domain.txt", )
        lines = response.text.split( "\n" )
        tlds = []
        for line in lines:
            if not "#" in line and not line == "":
                tlds.append( line.strip().lower() )
        return tlds

def get_json_from_file( filename ):
    file_handler = open( filename, "r" )
    result = json.loads(
        file_handler.read()
    )
    file_handler.close()
    return result

def write_to_json( filename, json_serializable_dict ):
    file_handler = open( filename, "w" )
    file_handler.write(
        json.dumps( json_serializable_dict )
    )
    file_handler.close()

def get_root_tld_dict( from_cache=True ):
    if from_cache:
        return get_json_from_file(
            "./cache/tld_dict.json",
        )

    dnstool = DNSTool()
    tlds = dnstool.get_root_tlds()
    root_map = {}
    for tld in tlds:
        root_map[ tld ] = dnstool.get_nameserver_list(
            tld + ".",
        )
    write_to_json(
        "./cache/tld_dict.json",
        root_map
    )
    return root_map

def pprint( input_dict ):
    '''
    Prints dicts in a JSON pretty sort of way
    '''
    print(
        json.dumps(
            input_dict, sort_keys=True, indent=4, separators=(',', ': ')
        )
    )

def write_dig_output( hostname, nameserver, dig_output, is_gzipped ):
    if not zone_transfer_succeeded( dig_output ):
        # skip writing
        return

    if hostname == ".":
        hostname = "root"

    if hostname.endswith( "." ):
        dir_path = "./archives/" + hostname[:-1] + "/"
    else:
        dir_path = "./archives/" + hostname + "/"

    if not os.path.exists( dir_path ):
        os.makedirs( dir_path )

    filename = dir_path + nameserver + "zone"

    file_handler = open( filename, "w" )
    file_handler.write(
        dig_output
    )
    file_handler.close()

    if is_gzipped:
        proc = subprocess.Popen([
            "/bin/gzip", "-f", filename
        ], stdout=subprocess.PIPE)
        output = proc.stdout.read()

def get_dig_axfr_output( hostname, nameserver ):
    proc = subprocess.Popen([
        "/usr/bin/dig", "AXFR", hostname, "@" + nameserver, "+nocomments", "+nocmd", "+noquestion", "+nostats", "+time=15"
    ], stdout=subprocess.PIPE)
    output = proc.stdout.read()
    return output

def zone_transfer_succeeded( zone_data ):
    if "Transfer failed." in zone_data:
        return False

    if "failed: connection refused." in zone_data:
        return False

    if "communications error" in zone_data:
        return False

    if "failed: network unreachable." in zone_data:
        return False

    if "failed: host unreachable." in zone_data:
        return False

    if "connection timed out; no servers could be reached" in zone_data:
        return False

    if zone_data == "":
        return False

    return True

if __name__ == "__main__":
    dnstool = DNSTool()

    zone_transfer_enabled_list = []

    for root_ns in ROOT_NAMESERVER_LIST:
        zone_data = get_dig_axfr_output(
            ".",
            root_ns,
        )

        if zone_transfer_succeeded( zone_data ):
            zone_transfer_enabled_list.append({
                "nameserver": root_ns,
                "hostname": "."
            })

        if( len( zone_data ) > 99614720 ): # Max github file size.
            write_dig_output(
                ".",
                root_ns,
                zone_data,
                True,
            )
        else:
            write_dig_output(
                ".",
                root_ns,
                zone_data,
                False,
            )

    tlds = dnstool.get_root_tlds()

    def get_one_tld(tld):
        full_tld = tld + "."

        nameservers = dnstool.get_nameserver_list(
            full_tld
        )

        for nameserver in nameservers:
            zone_data = get_dig_axfr_output(
                full_tld,
                nameserver,
            )

            if( len( zone_data ) > 99614720 ): # Max github file size.
                write_dig_output(
                    full_tld,
                    nameserver,
                    zone_data,
                    True,
                )
            else:
                write_dig_output(
                    full_tld,
                    nameserver,
                    zone_data,
                    False,
                )

            if zone_transfer_succeeded( zone_data ):
                return {
                    "nameserver": nameserver,
                    "hostname": tld,
                }

    pool = Pool(25)
    zone_transfer_enabled_list += [x for x in pool.map(get_one_tld, tlds) if x is not None]

    # Create markdown file and tab-separated list of zone-transfer enabled nameservers
    zone_transfer_enabled_markdown = "# List of TLDs & Roots With Zone Transfers Currently Enabled\n\n"
    zone_transfer_enabled_tsv = ""

    for zone_status in zone_transfer_enabled_list:
        if zone_status["hostname"] == ".":
            zone_transfer_enabled_markdown += "* `" + zone_status["hostname"] + "` via `" +  zone_status["nameserver"] + "`: [Click here to view zone data.](" + "archives/root/" + zone_status["nameserver"] + "zone)\n"
        else:
            filename = "archives/" + zone_status["hostname"] + "/" + zone_status["nameserver"] + "zone"
            zone_transfer_enabled_markdown += "* `" + zone_status["hostname"] + "` via `" +  zone_status["nameserver"] + "`: [Click here to view zone data.](" + filename + ")\n"
            zone_transfer_enabled_tsv += zone_status["hostname"] + "\t" + zone_status["nameserver"] + "\t" + filename + "\n"

    file_handler = open( "transferable_zones.md", "w" )
    file_handler.write(
        zone_transfer_enabled_markdown
    )
    file_handler.close()

    file_handler = open( "transferable_zones.tsv", "w" )
    file_handler.write(
        zone_transfer_enabled_tsv
    )
    file_handler.close()
