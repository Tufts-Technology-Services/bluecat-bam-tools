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
        if self.session and self.logged_in:
            self.session.close()

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

    def _get_next_url(self, response_json):
        """
        Extract the next URL for pagination from the response.

        Args:
            response_json (dict): The JSON response from the API
            hostname (str, optional): The hostname to use for relative URLs

        Returns:
            str or None: The next URL if available, None otherwise
        """
        url = None
        if '_links' in response_json and 'next' in response_json['_links'] and 'href' in response_json['_links']['next']:
            next_url = response_json['_links']['next']['href']
            if next_url:
                if next_url.startswith('http'):
                    url = next_url
                elif next_url.startswith('/'):
                    url = f"https://{self.hostname}{next_url}"
                else:
                    url = f"https://{self.hostname}/{next_url}"
        return url

    def get_network_by_cidr(self, target_cidr):
        """Find a network by its CIDR notation.

        Args:
            target_cidr (str): The CIDR notation to search for.

        Returns:
            dict: The network object if found.

        Raises:
            ValueError: If the network is not found.
        """
        if not self.logged_in:
            raise RuntimeError("You must call login() before using this method.")

        url = f"{self.url_base}/networks?filter=range:eq('{target_cidr}')"
        all_data = []

        while url:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            response_json = response.json()

            all_data.extend(response_json.get('data', []))

            # Check if there's a next link for pagination
            url = self._get_next_url(response_json)

        if len(all_data) == 0:
            raise ValueError(f"Network {target_cidr} not found")

        if len(all_data) != 1:
            raise RuntimeError(f"Expected 1 network, got {len(all_data)}")

        return all_data[0]

    def get_unassigned_addresses_in_network_by_cidr(self, target_cidr):
        if not self.logged_in:
            raise RuntimeError("You must call login() before using this method.")

        unassigned_addresses = []

        network = self.get_network_by_cidr(target_cidr)

        url = f"{self.url_base}/networks/{network['id']}/addresses?fields=embed(resourceRecords)&filter=state:eq('UNASSIGNED') or state:eq('STATIC')"

        while url:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            response_json = response.json()

            for address in response_json.get('data', []):
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

            # Check if there's a next link for pagination
            url = self._get_next_url(response_json)

        return unassigned_addresses
