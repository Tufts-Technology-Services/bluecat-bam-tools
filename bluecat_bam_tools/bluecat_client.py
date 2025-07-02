import requests
import json
import base64


class BluecatClient:
    """
    Client for interacting with Bluecat API.
    """

    def __init__(self, hostname, username, password, verify_ssl=True):
        """
        Initialize the Bluecat client.

        Args:
            hostname (str): The hostname of the Bluecat server
            username (str): Username for authentication
            password (str): Password for authentication
            verify_ssl (bool): Whether to verify SSL certificates, defaults to True
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.api_token = None
        self.url_base = f"https://{self.hostname}/api/v2"
        self.headers = None
        self.logged_in = False
        self.session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def login(self):
        """
        Creates a new session with the Bluecat server.

        Returns:
            bool: True if login was successful, False otherwise

        Raises:
            requests.exceptions.ConnectionError: If unable to connect to the server
            requests.exceptions.Timeout: If the request times out
            requests.exceptions.HTTPError: If the server returns an error status code
            requests.exceptions.RequestException: For other request-related errors
            json.JSONDecodeError: If the response contains invalid JSON
        """
        url = f"{self.url_base}/sessions"
        self.headers = {
            "Content-Type": "application/hal+json",
            "Accept": "application/hal+json"
        }
        data = {
            "username": self.username,
            "password": self.password
        }

        response = requests.post(url, headers=self.headers, data=json.dumps(data), verify=self.verify_ssl)
        response.raise_for_status()

        response_data = response.json()
        self.api_token = response_data.get("apiToken")

        if self.api_token is None:
            return False

        credentials = f"{self.username}:{self.api_token}"
        credentials_bytes = credentials.encode()  # convert str to bytes string
        credentials_b64_bytes = base64.b64encode(credentials_bytes)  # still a bytes string
        credentials_b64 = credentials_b64_bytes.decode()  # Now we have a base64 string

        self.headers = {
            "Content-Type": "application/hal+json",
            "Authorization": f"Basic {credentials_b64}",
            "Accept": "application/hal+json"
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)

        self.logged_in = True
        return True

    def logout(self):
        if self.session and self.logged_in:
            url = f"{self.url_base}/sessions/current"

            local_headers = self.session.headers.copy()
            local_headers.update({
                "Content-Type": "application/merge-patch+json",
                "x-bcn-change-control-comment": "Logging out"
            })

            response = self.session.patch(
                url,
                json={"state": "LOGGED_OUT"},
                headers=local_headers,
                verify=self.verify_ssl
            )
            response.raise_for_status()
            self.session.close()
            self.logged_in = False

    def http_get(self, url):
        if not self.logged_in:
            raise RuntimeError("You must call login() before using this method.")

        url = f"{self.url_base}{url}"

        all_data = []
        while url:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            response_json = response.json()

            # When the response_json is not paginated, the BAM returns a dict with 2 items, 'count' and 'data'
            # where response_json['count'] == len(response_json['data'])
            # When the response_json is paginated, it also includes '_links' in the response_json

            assert 'count' in response_json
            assert 'data' in response_json

            all_data.extend(response_json['data'])

            # If a next url was received for pagination continuation, get it.
            url = response_json.get('_links', {}).get('next', {}).get('href')

            # I don't know if it starts with 'http' or '/' or what. Just handle all those cases so we
            # don't need to think about it.
            if url:
                if not url.startswith('http'):
                    if url.startswith('/'):
                        url = f"https://{self.hostname}{url}"
                    else:
                        url = f"https://{self.hostname}/{url}"

        return all_data

    def get_network_by_cidr(self, target_cidr):
        """Find a network by its CIDR notation.

        Args:
            target_cidr (str): The CIDR notation to search for.

        Returns:
            dict: The network object if found.

        Raises:
            ValueError: If the network is not found.
        """
        url = f"/networks?filter=range:eq('{target_cidr}')"
        response = self.http_get(url)

        if len(response) == 0:
            raise ValueError(f"Network {target_cidr} not found")

        if len(response) != 1:
            raise ValueError(f"Expected 1 network, got {len(response)}")

        return response[0]

    def get_unassigned_addresses_in_network_by_cidr(self, target_cidr):
        unassigned_addresses = []

        network = self.get_network_by_cidr(target_cidr)

        url = f"/networks/{network['id']}/addresses?fields=embed(resourceRecords)&filter=state:eq('UNASSIGNED') or state:eq('STATIC')"
        addresses = self.http_get(url)

        for address in addresses:
            if address['state'] == 'UNASSIGNED':
                unassigned_addresses.append(address)
                continue
            if address['state'] == 'STATIC':
                # If there are no resourceRecords (dns entries pointed at this ip address), consider it to be
                # unassigned, even if its state is not "UNASSIGNED". This is because users often delete names
                # and neglect the checkbox "Delete linked IP addresses if orphaned." In the web UI, these appear
                # as IP addresses with no names, but the status icon is still blue instead of gray.
                if len(address['_embedded']['resourceRecords']) == 0:
                    unassigned_addresses.append(address)

        return unassigned_addresses
