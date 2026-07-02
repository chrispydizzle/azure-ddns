import os
import sys
import re
import ipaddress
import argparse
import requests
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.mgmt.dns import DnsManagementClient
from azure.core.exceptions import ResourceNotFoundError

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Update Azure DNS records with current public IP")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
args, _ = parser.parse_known_args()

verbose = args.verbose

# Load environment variables from .env file
load_dotenv()

# Azure credentials
TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
RESOURCE_GROUP = os.getenv("RESOURCE_GROUP")
DNS_ZONE = os.getenv("DNS_ZONE")
SUBDOMAINS = os.getenv("SUBDOMAINS", "").split(",")
ROUTER_URL = os.getenv("ROUTER_URL")

TTL = 300  # 5 minutes


def get_ip_from_dd_wrt(url):
    """Read the WAN IP from a DD-WRT router info page ('wan_ipaddr' field)."""
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    match = re.search(r'id="wan_ipaddr">\s*([0-9A-Fa-f:.]+)', response.text)
    if not match:
        raise ValueError("could not find 'wan_ipaddr' in router page")
    raw_ip = match.group(1).split("/")[0].strip()  # drop any CIDR suffix (e.g. /24)
    return str(ipaddress.ip_address(raw_ip))


def get_ip_from_ipify():
    """Read the public IP from the ipify external service (fallback)."""
    response = requests.get("https://api64.ipify.org?format=json", timeout=10)
    response.raise_for_status()
    return str(ipaddress.ip_address(response.json()["ip"]))


def get_public_ip():
    """Return the current WAN IP, preferring the router and falling back to ipify."""
    try:
        ip = get_ip_from_dd_wrt(ROUTER_URL)
        if verbose:
            print(f"Got WAN IP from router {ROUTER_URL}: {ip}")
        return ip
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Could not get WAN IP from router ({ROUTER_URL}): {e}")
        print("Falling back to ipify...")

    try:
        ip = get_ip_from_ipify()
        if verbose:
            print(f"Got WAN IP from ipify: {ip}")
        return ip
    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        print(f"Failed to get public IP: {e}")
        sys.exit(1)


public_ip = get_public_ip()

# Authenticate with Azure
credentials = ClientSecretCredential(TENANT_ID, CLIENT_ID, CLIENT_SECRET)
dns_client = DnsManagementClient(credentials, SUBSCRIPTION_ID)

# Process each subdomain
for subdomain in SUBDOMAINS:
    subdomain = subdomain.strip()
    if not subdomain:
        continue
    
    try:
        record_set = dns_client.record_sets.get(RESOURCE_GROUP, DNS_ZONE, subdomain, "A")
        if record_set.a_records and record_set.a_records[0].ipv4_address == public_ip:
            if verbose:
                print(f"No update needed for {subdomain}.{DNS_ZONE}")
        else:
            print(f"Updating DNS: {subdomain}.{DNS_ZONE} -> {public_ip}")
            dns_client.record_sets.create_or_update(
                RESOURCE_GROUP,
                DNS_ZONE,
                subdomain,
                "A",
                {
                    "ttl": TTL,
                    "a_records": [{"ipv4_address": public_ip}]
                }
            )
    except ResourceNotFoundError:
        print(f"Record {subdomain}.{DNS_ZONE} not found. Creating new record -> {public_ip}")
        dns_client.record_sets.create_or_update(
            RESOURCE_GROUP,
            DNS_ZONE,
            subdomain,
            "A",
            {
                "ttl": TTL,
                "a_records": [{"ipv4_address": public_ip}]
            }
        )