import os
import requests
from dotenv import load_dotenv
from azure.identity import ClientSecretCredential
from azure.mgmt.dns import DnsManagementClient
from azure.core.exceptions import ResourceNotFoundError

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

TTL = 300  # 5 minutes

# Get current public IP
response = requests.get("https://api64.ipify.org?format=json")
public_ip = response.json()["ip"]

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