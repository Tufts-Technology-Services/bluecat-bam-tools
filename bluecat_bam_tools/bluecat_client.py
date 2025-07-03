import requests
import json
import base64
from bluecat_bam_tools.exceptions import *

class BluecatClient:
    """
    Client for interacting with the Bluecat Address Manager (BAM) REST API v2.

    This class provides methods to authenticate with the BAM server,
    query network information, and manage IP addresses and related resources.
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

    def _handle_login_exception(self, exc, message, debug):
        if debug:
            raise exc
        else:
            raise LoginError(message)

    def login(self, debug=False):
        """
        Attempts to create a session on the BAM server using credentials provided in the constructor.

        Args:
            debug (bool, optional): When False (default), any errors will raise a simplified LoginError with a helpful
                message. This is recommended for most usage because common errors (e.g. wrong password, server not
                reachable, etc) will be easily understood by the user. When True, raises the original exception with
                full stack trace for debugging purposes; useful for troubleshooting, overkill for most usage.

        Returns:
            bool: True if login was successful, False otherwise

        Raises:
            bluecat_bam_tools.exceptions.LoginError: When debug=False and login fails for any reason
            requests.exceptions.ConnectionError: When debug=True and unable to connect to the server
            requests.exceptions.Timeout: When debug=True and request times out
            requests.exceptions.HTTPError: When debug=True and the server returns an HTTP error status code
            requests.exceptions.RequestException: When debug=True and some other request-related error occurs
            json.JSONDecodeError: When debug=True and the response contains invalid JSON
        """
        try:
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
        except requests.exceptions.ConnectionError as e:
            self._handle_login_exception(e, "Unable to connect to the server", debug)
        except requests.exceptions.Timeout as e:
            self._handle_login_exception(e, "Request timed out", debug)
        except requests.exceptions.HTTPError as e:
            self._handle_login_exception(e, f"HTTP error occurred: {e.response.status_code} - {e.response.reason}", debug)
        except requests.exceptions.RequestException as e:
            self._handle_login_exception(e, f"An unexpected error occurred: {e}", debug)
        except json.JSONDecodeError as e:
            self._handle_login_exception(e, f"Error decoding JSON response: {e}", debug)

    def logout(self):
        """
        This method is automatically called by the `__exit__()` method, so you only need to call `logout()` explicitly
        if you're **not** using a `with` block.

        Returns:
            None

        Raises:
            requests.exceptions.HTTPError: If the server returns an error response
        """
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

    def http_get_all(self, url):
        """
        Returns data from the GET request. Handles pagination internally to return all data at once.

        Args:
            url (str): The API endpoint path (e.g., '/networks' or 'networks'). Leading '/' is optional; it will be
            added automatically if needed.

        Returns:
            list: A combined list of all data objects from all pages of results

        Raises:
            RuntimeError: If called before logging in
            requests.exceptions.HTTPError: If the server returns an error response
            TypeError: If the response data is not in the expected format
            AssertionError: If the response doesn't contain the expected structure
        """
        if not self.logged_in:
            raise RuntimeError("You must call login() before using this method.")

        if url.startswith('/'):
            url = f"{self.url_base}{url}"
        else:
            url = f"{self.url_base}/{url}"

        all_data = []
        while url:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            response_json = response.json()

            # When the response_json is not paginated, the BAM returns a dict with 2 items, 'count' and 'data'
            # where response_json['count'] == len(response_json['data'])
            # When the response_json is paginated, it also includes '_links' in the response_json

            assert ('count' in response_json), "'count' not found in response_json"

            # If response_json['count'] == 0, I don't know if 'data' will be present, Null, empty list, empty dict,
            # or what. But I don't care. I'm done.
            if response_json['count'] == 0:
                return all_data

            data = response_json['data']
            if not isinstance(data, list):
                raise TypeError(f"Expected 'data' to be a list, got {type(data).__name__}. Please report this " + \
                    "issue. It should be easy to extend the code to handle this case.")

            all_data.extend(data)

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
            target_cidr (str): The CIDR notation to search for (e.g., '10.0.0.0/24')

        Returns:
            dict: The network object if found, None otherwise

        Raises:
            ValueError: If multiple networks match the CIDR (which should not happen)
            RuntimeError: If called before logging in
        """
        url = f"/networks?filter=range:eq('{target_cidr}')"
        response = self.http_get_all(url)

        if len(response) == 0:
            return None

        if len(response) != 1:
            raise ValueError(f"Expected 1 network, got {len(response)}")

        return response[0]

    def get_unassigned_addresses_in_network_by_cidr(self, target_cidr):
        """
        Retrieves a list of unassigned IP addresses within a network identified by CIDR notation.

        This method looks for both explicitly unassigned addresses (state='UNASSIGNED') and
        static addresses with no associated resource records, which are effectively unassigned.
        The latter case handles situations where users delete DNS records but neglect
        the checkbox "Delete linked IP addresses if orphaned" in the web UI

        Args:
            target_cidr (str): The CIDR notation of the network to search within (e.g., '10.0.0.0/24')

        Returns:
            list: A list of address objects that are considered unassigned, each is a `dict` containing
                  details like 'id', 'properties', 'name', 'type', etc.

        Raises:
            ValueError: If the network cannot be found or if multiple networks match the CIDR
            RuntimeError: If called before logging in
        """
        unassigned_addresses = []

        network = self.get_network_by_cidr(target_cidr)

        url = f"/networks/{network['id']}/addresses?fields=embed(resourceRecords)&filter=state:eq('UNASSIGNED') or state:eq('STATIC')"
        addresses = self.http_get_all(url)

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
