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

    with BluecatClient(hostname, username, password, verify_ssl=verify_ssl) as client:
        try:
            client.login()
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

        cidr = '10.10.10.0/24'
        network = client.get_network_by_cidr(cidr)
        print("Found network:")
        print(f"{network}")
        print("")

        addresses = client.get_unassigned_addresses_in_network_by_cidr(cidr)
        if not addresses:
            print("No unassigned addresses found")
        else:
            print(f"Found {len(addresses)} unassigned addresses in network {cidr}. Here's the first one:")
            print(f"{addresses[0]}")

    print("Done")


if __name__ == "__main__":
    main()
