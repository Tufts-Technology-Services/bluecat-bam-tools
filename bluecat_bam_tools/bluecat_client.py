import requests
import json
import base64
from bluecat_bam_tools.exceptions import *
from typing import Union, List, Dict

class BluecatClient:
    """
    Client for interacting with the Bluecat Address Manager (BAM) REST API v2.

    This class provides methods to authenticate with the BAM server,
    query network information, and manage IP addresses and related resources.
    """

    def __init__(self, hostname: str, username: str, password: str, verify_ssl: bool = True):
        """
        Initialize the Bluecat client.

        Args:
            hostname (str): The hostname of the Bluecat server
            username (str): Username for authentication
            password (str): Password for authentication
            verify_ssl (bool): Whether to verify SSL certificates, defaults to True
        """
        if not isinstance(hostname, str):
            raise TypeError("hostname must be a string")
        if not isinstance(username, str):
            raise TypeError("username must be a string")
        if not isinstance(password, str):
            raise TypeError("password must be a string")
        if not isinstance(verify_ssl, bool):
            raise TypeError("verify_ssl must be a boolean")

        self.hostname = hostname
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.api_token = None
        self.url_base = f"https://{self.hostname}"
        self.url_api_path = "/api/v2"
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

    def login(self, debug: bool = False) -> bool:
        """
        Attempts to create a session on the BAM server using credentials provided in the constructor.

        Args:
            debug (bool, optional): When False (default), any errors will raise a simplified LoginError with a helpful
                message. This is recommended for most usage because common errors (e.g. wrong password, server not
                reachable, etc) will be easily understood by the user. When True, raises the original exception with
                full stack trace for debugging purposes; useful for troubleshooting, overkill for most usage.

        Returns:
            bool: True if login was successful

        Raises:
            bluecat_bam_tools.exceptions.LoginError: When debug=False and login fails for any reason
            requests.exceptions.ConnectionError: When debug=True and unable to connect to the server
            requests.exceptions.Timeout: When debug=True and request times out
            requests.exceptions.HTTPError: When debug=True and the server returns an HTTP error status code
            requests.exceptions.RequestException: When debug=True and some other request-related error occurs
            json.JSONDecodeError: When debug=True and the response contains invalid JSON
        """
        try:
            url = f"{self.url_base}{self.url_api_path}/sessions"
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

        return True

    def logout(self) -> None:
        """
        This method is automatically called by the `__exit__()` method, so you only need to call `logout()` explicitly
        if you're **not** using a `with` block.

        Returns:
            None

        Raises:
            requests.exceptions.HTTPError: If the server returns an error response
        """
        if self.session and self.logged_in:
            url = f"{self.url_base}{self.url_api_path}/sessions/current"

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

    def http_get_limited(self, endpoint_path: str) -> dict:
        """
        Makes a GET request with no pagination handling.

        Args:
            endpoint_path (str): The API endpoint path (e.g., '/networks' or 'networks'). Leading '/' is optional;
            it will be added automatically if needed.

        Returns:
            dict: The raw JSON response from the API as a dictionary

        Raises:
            RuntimeError: If called before logging in
            requests.exceptions.HTTPError: If the server returns an error response
        """
        if not self.logged_in:
            raise RuntimeError("You must call login() before using this method.")

        if not endpoint_path.startswith('/'):
            endpoint_path = f"/{endpoint_path}"

        if endpoint_path.startswith(self.url_api_path):
            url = f"{self.url_base}{endpoint_path}"
        else:
            url = f"{self.url_base}{self.url_api_path}{endpoint_path}"

        response = self.session.get(url, verify=self.verify_ssl)
        response.raise_for_status()
        response_json = response.json()
        return response_json

    def http_get_all(self, endpoint_path: str) -> List[Dict]:
        """
        Returns data from the GET request. Handles pagination internally to return all data at once.

        Args:
            endpoint_path (str): The API endpoint path (e.g., '/networks' or 'networks'). Leading '/' is optional; it will be
            added automatically if needed.

        Returns:
            List[Dict]: A combined list of all data objects from all pages of results

        Raises:
            RuntimeError: If called before logging in
            requests.exceptions.HTTPError: If the server returns an error response
            TypeError: If the response data is not in the expected format
            AssertionError: If the response doesn't contain the expected structure
        """
        if not self.logged_in:
            raise RuntimeError("You must call login() before using this method.")

        if not endpoint_path.startswith('/'):
            endpoint_path = f"/{endpoint_path}"

        if endpoint_path.startswith(self.url_api_path):
            url = f"{self.url_base}{endpoint_path}"
        else:
            url = f"{self.url_base}{self.url_api_path}{endpoint_path}"

        all_data = []
        while url:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            response_json = response.json()

            # When the response_json is not paginated, the BAM returns a dict with 2 items, 'count' and 'data'
            # where response_json['count'] == len(response_json['data'])
            # When the response_json is paginated, it also includes '_links' in the response_json

            if not ('count' in response_json):
                raise RuntimeError("'count' not found in response_json")

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

    def get_network_by_cidr(self, target_cidr: str) -> Union[Dict, None]:
        """Find a network by its CIDR notation.

        Args:
            target_cidr (str): The CIDR notation to search for (e.g., '10.0.0.0/24')

        Returns:
            dict or None: The network object if found, None otherwise

        Raises:
            ValueError: If multiple networks match the CIDR (which should not happen)
            RuntimeError: If called before logging in
        """
        endpoint_path = f"/networks?filter=range:eq('{target_cidr}')"
        response = self.http_get_all(endpoint_path)

        if len(response) == 0:
            return None

        if len(response) != 1:
            raise ValueError(f"Expected 1 network, got {len(response)}")

        return response[0]

    def get_cidr_contains_ip(self, ip_address: str) -> Union[str, None]:
        """Find a network that contains the specified IP address.

        Args:
            ip_address (str): The IP address to search for (e.g., '10.0.0.15')

        Returns:
            str or None: The cidr range of the network (e.g., '10.0.0.0/24')

        Raises:
            ValueError: If there isn't exactly 1 network that contains the IP address
            RuntimeError: If called before logging in
        """
        endpoint_path = f"/networks?filter=range:contains('{ip_address}')"
        response = self.http_get_all(endpoint_path)

        if len(response) != 1:
            raise ValueError(f"Expected 1 network, got {len(response)}")

        return response[0]['range']

    def get_unassigned_addresses_in_network_by_cidr(self, target_cidr: str) -> List[dict]:
        """
        Retrieves a list of unassigned IP addresses within a network identified by CIDR notation.

        This method looks for both explicitly unassigned addresses (state='UNASSIGNED') and
        static addresses with no associated resource records, which are effectively unassigned.
        The latter case handles situations where users delete DNS records but neglect
        the checkbox "Delete linked IP addresses if orphaned" in the web UI

        Args:
            target_cidr (str): The CIDR notation of the network to search within (e.g., '10.0.0.0/24')

        Returns:
            list[dict]: A list of address objects that are considered unassigned, each is a `dict` containing
                      details like 'id', 'properties', 'name', 'type', etc.

        Raises:
            ValueError: If the network cannot be found or if multiple networks match the CIDR
            RuntimeError: If called before logging in
        """
        unassigned_addresses = []

        network = self.get_network_by_cidr(target_cidr)

        endpoint_path = f"/networks/{network['id']}/addresses?fields=embed(resourceRecords)&filter=state:eq('UNASSIGNED') or state:eq('STATIC')"
        addresses = self.http_get_all(endpoint_path)

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

    def get_view(self, view_name: str) -> Union[dict, None]:
        """
        Retrieves a DNS view by its name from the BAM server.

        Args:
            view_name (str): The name of the view to retrieve. For example, "external", "internal", "registration",
                or "quarantine".

        Returns:
            dict or None: If found, the view object containing details like 'id', 'name', etc. Otherwise, None.

        Raises:
            AssertionError: If server response is not as expected
            RuntimeError: If called before logging in
        """
        view = self.http_get_all(f"/views?filter=name:eq('{view_name}')")
        if not view:
            return None
        if len(view) != 1:
            raise RuntimeError(f"Expected 1 view, got {len(view)}")
        return view[0]

    def find_parent_zones(self, fqdn: str) -> Union[List[Dict], None]:
        """
        Find the parent zone by progressively removing sections from the hostname.

        Args:
            fqdn (str): The fully qualified domain name (FQDN) to find the parent zone of

        Returns:
            Union[List[Dict], None]: The parent zone objects if found. Typically returns multiple zones, because each zone
            in a different view is a different object.
        """
        name_parts = fqdn.split('.')

        # Start with the full hostname and progressively remove sections from the beginning
        while len(name_parts) > 1:  # Keep at least one part (TLD)
            search_name = '.'.join(name_parts)
            zones = self.http_get_all(f"zones?filter=absoluteName:eq('{search_name}')")

            if zones:
                return zones

            # Remove the leftmost part and try again
            name_parts.pop(0)

        return None

    def record_a_create(self, views: List[str], fqdn: str, ipaddresses: Union[str, List[str]], change_control_comment: Union[str, None] = None):
        """
        Creates an A record with the specified FQDN and IP address(es) in the specified view(s).

        Args:
            views (List[str]): List of view names (e.g., ['internal', 'external']) to create the record in
            fqdn (str): The fully qualified domain name for the record
            ipaddresses (Union[str, List[str]]): One or more IP addresses to associate with the FQDN
            change_control_comment (str | None, optional): Comment to include with the change for audit purposes

        Returns:
            bool: True if the record was successfully created

        Raises:
            TypeError: If any parameter is of incorrect type
            ValueError: If views list is empty, ipaddresses list is empty, or parent zone cannot be found
            requests.exceptions.HTTPError: If the server returns an error response
            RuntimeError: If called before logging in
        """
        if not isinstance(views, list):
            raise TypeError("views must be a list of strings")
        if not views:
            raise ValueError("views must contain at least one item")
        if not all(isinstance(view, str) for view in views):
            raise TypeError("all items in views must be strings")

        if isinstance(ipaddresses, list):
            if len(ipaddresses) == 0:
                raise ValueError("ipaddresses must contain at least one item")
            if not all(isinstance(ip, str) for ip in ipaddresses):
                raise TypeError("all items in ipaddresses must be strings")
        elif isinstance(ipaddresses, str):
            # It's ok if the user only provided a single IP address. Internally we're going to use a list with 1 item.
            ipaddresses = [ipaddresses]
        else:
            raise TypeError("ipaddresses must be a string, or list of strings")

        if not isinstance(fqdn, str):
            raise TypeError("fqdn must be a string")
        
        if change_control_comment is not None and not isinstance(change_control_comment, str):
            raise TypeError("change_control_comment must be a string or None")

        # Typically returns multiple zones, because each zone in a different view is a different object.
        zones = self.find_parent_zones(fqdn)

        if not isinstance(zones, list) or len(zones) == 0:
            raise ValueError(f"Unable to find parent zone for {fqdn}")

        # Filter zones to only include those where the view name is in the views list
        zones = [zone for zone in zones if zone['view']['name'] in views]

        if len(zones) == 0:
            raise ValueError(f"Parent zone for {fqdn} does not exist in views {views}")

        relative_domain_name = fqdn.rstrip(f".{zones[0]['absoluteName']}")

        # Create data object for POST based on the provided ipaddresses
        addresses = []
        for ip in ipaddresses:
            addresses.append({
                "type": "IPv4Address",
                "address": ip,
                "state": "STATIC"
            })

        # Prepare the request data
        data = {
            "type": "HostRecord",
            "name": relative_domain_name,
            "addresses": addresses
        }

        # Make a local copy of session headers and add change control comment if provided
        headers = self.session.headers.copy()
        if change_control_comment:
            headers["x-bcn-change-control-comment"] = change_control_comment

        for zone in zones:
            endpoint_path = f"{self.url_base}{self.url_api_path}/zones/{zone['id']}/resourceRecords"
            response = self.session.post(endpoint_path, json=data, headers=headers, verify=self.verify_ssl)
            response.raise_for_status()

        return True
