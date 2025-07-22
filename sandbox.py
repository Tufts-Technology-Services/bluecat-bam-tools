import sys
import argparse
import getpass
import json

from requests.exceptions import ConnectionError, Timeout, HTTPError, RequestException

from bluecat_bam_tools.bluecat_client import BluecatClient

try:
    import yaml
except ImportError:
    print("Error: PyYAML package is required for sandbox.py")
    print("Please install it with: pip install PyYAML")
    sys.exit(1)

try:
    import keyring
except ImportError:
    print("Error: The keyring package is required but not installed")
    print("")
    print("This script uses keyring to securely store and retrieve credentials.")
    print("Install the package with: pip install keyring")
    print("")
    print("For additional options:")
    print("  - For password manager integration (Bitwarden, 1Password, etc.):")
    print("    https://keyring.readthedocs.io/en/latest/#third-party-backends")
    print("")
    print("  - For headless servers or automated environments:")
    print("    pip install keyring keyrings.alt")
    print("")
    sys.exit(1)


def get_password(hostname, username, save_password=False):
    """Get password from keyring or prompt user if needed"""

    # service_name should be something unique to your application, and also unique to your hostname
    service_name = f"bluecat-bam-tools-{hostname}"

    if save_password:
        password = getpass.getpass(f"Enter password for {username}@{hostname}: ")
        keyring.set_password(service_name, username, password)
        print(f"Password saved in keyring for {username}@{hostname}")

    password = keyring.get_password(service_name, username)

    if not password:
        print(f"No password found in keyring for {username}@{hostname}")
        print("Run with --save-password to save your password in the keyring")
        sys.exit(1)

    return password


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Sandbox script for testing BluecatClient functionality")

    # "store_true" means if "--save-password" was provided, `args.save_password` will be True.
    # otherwise, it'll be False. The name "save_password" is automatically derived from the arg name.
    parser.add_argument("--save-password", action="store_true", help="Save password in keyring")
    return parser.parse_args()


def ipaddress_to_int(address_str: str):
    ip_octets = [int(octet) for octet in address_str.split('.')]
    ip_int = (ip_octets[0] << 24) + (ip_octets[1] << 16) + \
             (ip_octets[2] << 8) + ip_octets[3]
    return ip_int


def is_near_ipaddress(first_ipaddress: str, second_ipaddress: str, threshold: int) -> bool:
    first_int = ipaddress_to_int(first_ipaddress)
    second_int = ipaddress_to_int(second_ipaddress)
    return abs(first_int - second_int) <= threshold


def main():
    args = parse_args()

    try:
        with open('sandbox_config.yaml', 'r') as config_file:
            config = yaml.safe_load(config_file)
    except FileNotFoundError:
        print("Error: sandbox_config.yaml not found")
        print("Please copy sandbox_config_example.yaml to sandbox_config.yaml and update it")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML configuration: {e}")
        sys.exit(1)

    hostname = config.get('hostname')
    username = config.get('username')
    verify_ssl = config.get('verify_ssl', True)  # Default to True if not specified

    if not hostname or not username:
        print("Error: hostname and username must be specified in sandbox_config.yaml")
        sys.exit(1)

    # Get password from keyring or prompt user
    password = get_password(hostname, username, args.save_password)

    with BluecatClient(hostname, username, password, verify_ssl=verify_ssl) as bam:
        try:
            bam.login()
        except ConnectionError as e:
            print("Error: Unable to connect to the server.", file=sys.stderr)
            sys.exit(1)
        except Timeout:
            print("Error: Request timed out.", file=sys.stderr)
            sys.exit(1)
        except HTTPError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.reason}", file=sys.stderr)
            sys.exit(1)
        except RequestException as e:
            print(f"An unexpected error occurred: {e}", file=sys.stderr)
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response: {e}", file=sys.stderr)
            sys.exit(1)

        ip_address = '10.10.10.10'
        cidr = bam.get_cidr_contains_ip(ip_address)
        cidr_first_ipaddress = cidr.split('/')[0]

        # Demonstrate get_network_by_cidr()
        network = bam.get_network_by_cidr(cidr)
        print("Found network:")
        print(f"{network}")
        print("")

        # Demonstrate get_unassigned_addresses_in_network_by_cidr()
        unassigned_addresses = bam.get_unassigned_addresses_in_network_by_cidr(cidr)
        if not unassigned_addresses:
            print("No unassigned addresses found")
        else:
            print(f"Found {len(unassigned_addresses)} unassigned addresses in network {cidr}. Here's the first one:")
            print(f"{unassigned_addresses[0]}")

        # Demonstrate using some custom logic
        found_free_ip_address = False
        for unassigned_address in unassigned_addresses:
            unassigned_address_str = unassigned_address['address']

            # Enforce a policy that the first 30 IP addresses of any network will not be assigned; they are reserved
            # for network equipment and such
            if not is_near_ipaddress(unassigned_address_str, cidr_first_ipaddress, 30):
                found_free_ip_address = True
                break

        if not found_free_ip_address:
            raise RuntimeError("No unassigned addresses found in network")

        # Now we've got an unassigned_address. Assign it.
        # Demonstrate record_a_create()
        fqdn = 'test.example.com'
        zones = ['internal','external']
        bam.record_a_create(zones, fqdn, unassigned_address_str)

        # Demonstrate get_view()
        view_internal = bam.get_view('internal')

    print("Done")


if __name__ == "__main__":
    main()
