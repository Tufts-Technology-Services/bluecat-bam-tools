# bluecat-bam-tools

In this document, Bluecat Address Manager is abbreviated BAM.

This project is public open source, MIT licensed.

## Requirements

This project requires **Python 3.9 or greater**.

## Usage

To use the `bluecat_bam_tools` module in your project, `pip install` the following line, or add it to your `requirements.txt`. Notice the tagged version `@v0.1.2` in the URL and modify as appropriate.

Please see `sandbox.py` for example usage, including a typical usage of the `keyring` module to securely store credentials.

    git+https://github.com/Tufts-Technology-Services/bluecat-bam-tools.git@v0.1.2#egg=bluecat_bam_tools

Then

```python
from bluecat_bam_tools.bluecat_client import BluecatClient

hostname = "example.org"  # hostname of your BAM
username = "exampleuser"
password = "examplepassword" # optionally, see sandbox.py for example of using keyring
verify_ssl = true  # require valid SSL cert

with BluecatClient(hostname, username, password, verify_ssl=verify_ssl) as bam:
    # Optionally, handle exceptions during login() for more friendly output.
    # Exceptions include: ConnectionError, Timeout, HTTPError, RequestException
    # But I'm not doing that for this simple example.
    bam.login()
    cidr = '10.10.10.0/24'
    
    # Returns the dict describing the network
    network = bam.get_network_by_cidr(cidr)
    
    # Returns a list of dicts, each describing the IP address object
    # Includes UNASSIGNED and STATIC addresses, if there are
    # no resourceRecords (DNS entries) pointing at the IP address
    addresses = bam.get_unassigned_addresses_in_network_by_cidr(cidr)
```

Methods:
* **`BluecatClient(hostname, username, password, verify_ssl=True)`**
  Constructor for the BluecatClient class.

  * Args:
    * `hostname (str)`: The hostname of the Bluecat server
    * `username (str)`: Username for authentication
    * `password (str)`: Password for authentication
    * `verify_ssl (optional bool, default True)`: Whether to verify HTTPS certificates

  * Example Usage:

    ```python
    bam = BluecatClient("example.org", "exampleuser", "examplepassword")
    ```

* **`login(debug=False)`**
  Attempts to create a session on the BAM server using credentials provided in the constructor.

  * Args:
    * `debug (bool, optional)`: When False (default), any errors will raise a simplified LoginError with a helpful message. This is recommended for most usage because common errors (e.g. wrong password, server not reachable, etc) will be easily understood by the user. When True, raises the original exception with full stack trace for debugging purposes; useful for troubleshooting, overkill for most usage.
    
  * Returns:
    * `bool`: True if login was successful, False otherwise

  * Raises:
    * `bluecat_bam_tools.exceptions.LoginError`: When debug=False and login fails for any reason
    * `requests.exceptions.ConnectionError`: When debug=True and unable to connect to the server
    * `requests.exceptions.Timeout`: When debug=True and request times out
    * `requests.exceptions.HTTPError`: When debug=True and the server returns an HTTP error status code
    * `requests.exceptions.RequestException`: When debug=True and some other request-related error occurs
    * `json.JSONDecodeError`: When debug=True and the response contains invalid JSON

  * Example Usage:

    ```python
    bam.login()
    ```

* **`logout()`**
  This method is automatically called by the `__exit__()` method, so you only need to call `logout()` explicitly if you're **not** using a `with` block.

  * Raises:
    * `requests.exceptions.HTTPError`: If the server returns an error response

  * Example Usage:

    ```python
    bam.logout()
    ```

* **`http_get_all(url)`**
  Returns data from the GET request. Handles pagination internally to return all data at once.

  * Args:
    * `url (str)`: The API endpoint path (e.g., '/networks' or 'networks'). Leading '/' is optional; it will be added automatically if needed.
    
  * Returns:
    * `list`: A combined list of all data objects from all pages of results

  * Raises:
    * `RuntimeError`: If called before logging in
    * `requests.exceptions.HTTPError`: If the server returns an error response
    * `TypeError`: If the response data is not in the expected format
    * `AssertionError`: If the response doesn't contain the expected structure

  * Example Usage:

    ```python
    configurations = bam.http_get_all('/configurations')
    ```

  * **`http_get_limited(endpoint_path)`**
  Makes a GET request with no pagination handling.

  * Args:
    * `endpoint_path (str)`: The API endpoint path (e.g., '/networks' or 'networks'). Leading '/' is optional; it will be added automatically if needed.

  * Returns:
    * `dict`: The raw JSON response from the API as a dictionary

  * Raises:
    * `RuntimeError`: If called before logging in
    * `requests.exceptions.HTTPError`: If the server returns an error response

  * Example Usage:

    ```python
    response = bam.http_get_limited('/configurations')
    ```

* **`get_network_by_cidr(target_cidr)`**
  Find a network by its CIDR notation.

  * Args:
    * `target_cidr (str)`: The CIDR notation to search for (e.g., '10.0.0.0/24')

  * Returns:
    * `dict`: The network object if found, None otherwise

  * Raises:
    * `ValueError`: If multiple networks match the CIDR (which should not happen)
    * `RuntimeError`: If called before logging in

  * Example Usage:

    ```python
    network = bam.get_network_by_cidr('10.10.10.0/24')
    ```

  * **`get_cidr_contains_ip(ip_address)`**
  Find a network that contains the specified IP address.

  * Args:
    * `ip_address (str)`: The IP address to search for (e.g., '10.0.0.15')

  * Returns:
    * `str`: The cidr range of the network (e.g., '10.0.0.0/24')

  * Raises:
    * `ValueError`: If there isn't exactly 1 network that contains the IP address
    * `RuntimeError`: If called before logging in

  * Example Usage:

    ```python
    cidr_range = bam.get_cidr_contains_ip('10.10.10.15')
    ```

* **`get_unassigned_addresses_in_network_by_cidr(target_cidr)`**
  Retrieves a list of unassigned IP addresses within a network identified by CIDR notation.

  This method looks for both explicitly unassigned addresses (state='UNASSIGNED') and static addresses with no associated resource records, which are effectively unassigned. The latter case handles situations where users delete DNS records but neglect the checkbox "Delete linked IP addresses if orphaned" in the web UI.

  * Args:
    * `target_cidr (str)`: The CIDR notation of the network to search within (e.g., '10.0.0.0/24')

  * Returns:
    * `List[Dict]`: A list of address objects that are considered unassigned, each is a `dict` containing
            details like 'id', 'properties', 'name', 'type', etc.

  * Raises:
    * `ValueError`: If the network cannot be found or if multiple networks match the CIDR
    * `RuntimeError`: If called before logging in

  * Example Usage:

    ```python
    addresses = bam.get_unassigned_addresses_in_network_by_cidr('10.10.10.0/24')
    ```

* **`get_view(view_name)`**
  Retrieves a DNS view by its name from the BAM server.

  * Args:
    * `view_name (str)`: The name of the view to retrieve. For example, "external", "internal", "registration", or "quarantine".

  * Returns:
    * `Union[Dict, None]`: If found, the view object containing details like 'id', 'name', etc. Otherwise, None.

  * Raises:
    * `AssertionError`: If server response is not as expected
    * `RuntimeError`: If called before logging in

  * Example Usage:

    ```python
    internal_view = bam.get_view('internal')
    ```

* **`find_parent_zones(fqdn)`**
  Find the parent zone by progressively removing sections from the hostname.

  * Args:
    * `fqdn (str)`: The fully qualified domain name (FQDN) to find the parent zone of

  * Returns:
    * `list[dict] | None`: The parent zone objects if found. Typically returns multiple zones, because each zone in a different view is a different object.

  * Example Usage:

    ```python
    zones = bam.find_parent_zones('host.example.com')
    ```

* **`record_a_create(views, fqdn, ipaddresses, change_control_comment=None)`**
  Creates an A record with the specified FQDN and IP address(es) in the specified view(s).

  * Args:
    * `views (List[str])`: List of view names (e.g., ['internal', 'external']) to create the record in
    * `fqdn (str)`: The fully qualified domain name for the record
    * `ipaddresses (Union[str, List[str]])`: One or more IP addresses to associate with the FQDN
    * `change_control_comment (Union[str, None], optional)`: Comment to include with the change for audit purposes

  * Returns:
    * `bool`: True if the record was successfully created

  * Raises:
    * `TypeError`: If any parameter is of incorrect type
    * `ValueError`: If views list is empty, ipaddresses list is empty, or parent zone cannot be found
    * `requests.exceptions.HTTPError`: If the server returns an error response
    * `RuntimeError`: If called before logging in

  * Example Usage:

    ```python
    bam.record_a_create(['internal', 'external'], 'host.example.com', '192.168.1.100')
    ```

## Developer Notes

If you plan to do development on this project, such as editing or running `sandbox.py`, several packages are necessary to support the sandbox, which are not needed by any public users who just `pip install` our package. To set up the development environment:

```bash
pip install -r requirements-dev.txt
```

Join the developer community ([Bluecat Network VIP](https://bluecatnetworks.com/network-vip/)). When prompted what product you use, BAM is part of the "Integrity" line. Choose Integrity. I have had a fantastic experience with this community. It's a small community but each question I've asked got immediate helpful replies.

## Comparison of bluecat automation options

Several options were considered, for management of bluecat resources. Discussion was had ([this is a link to the discussion](https://community.bluecatnetworks.com/integrity-20/automating-bluecat-address-manager-2036?postid=12416#post12416)) in the bluecat [community forum](https://community.bluecatnetworks.com) and a bluecat employee chimed in. All members of the community recommended the DIY v2 API approach, so that is what's used in this project.

#### 1. The DIY v2 API

This was the community recommended option.

Bluecat v2 API docs:

1. Login to your BAM Web UI
2. In the top-right, click the (?) icon, and "API Documentation"

Links to additional resources:

[Bluecat Address Manager RESTful v2 API Guide](https://docs.bluecatnetworks.com/r/Address-Manager-RESTful-v2-API-Guide)

[Bluecat Address Manager RESTful v2 API examples](https://docs.bluecatnetworks.com/r/Address-Manager-RESTful-v2-API-Guide/RESTful-v2-API-examples/9.5.0)

On the official [Bluecat Documentation](https://docs.bluecatnetworks.com) page, the BAM is part of the "Integrity" line of products, so click [Browse the Integrity Bookshelf](https://docs.bluecatnetworks.com/search/books?filters=ft%253AisUnstructured~%2522false%2522*prodname~%2522BlueCat+Integrity%2522&content-lang=en-US) and then you'll find the above links to the RESTful v2 API Guide.

The v2 API is extremely well organized and documented, but that didn't prevent me from getting confused. Join the bluecat [community forum](https://community.bluecatnetworks.com), and ask questions. My experience there has been excellent.

#### 2. The [bluecat-libraries](https://pypi.org/project/bluecat-libraries/) pip package

This pip package interfaces both the v1 API and v2 API. They strongly discourage use of the v1 API. When you use this package to interact with the v2 API, you still need to craft your own URLs. The package does a good job of handling `login()` and `logout()` for you, but it does not handle pagination for you. Ultimately we did not find this package to be worthwhile for v2 API work; we wrote our own `login()`, `logout()`, and handle pagination.

Documentation here: [BlueCat Library Address Manager REST v2 API client reference](https://docs.bluecatnetworks.com/r/BlueCat-Python-Library-Guide/BlueCat-Library-Address-Manager-REST-v2-API-client-reference/25.1.1)

#### 3. Using the OpenAPI auto-generated SDK (for python)

I had problems with the auto-generated python SDK, because the bluecat `openapi.json` schema apparently has circular class references, (e.g. `abstract_server.py` imports `network_interface.py` and `network_interface.py` imports `abstract_server.py` and so on). Python cannot handle circular class references. I spent some time on it, and gave up. Maybe somebody else knows how to make it work? If you get it working, it might be slightly nicer than DIY v2 API.

Until further notice, consider the following abandoned:

When you browse the v2 API docs (login to BAM Web UI, in the top-right click the (?) icon, and "API Documentation") you'll notice they provide a downloadable `openapi.json` file. This file documents the v2 API, and can be used by `openapi-generator` to generate an SDK for any language, so it should be at least as good as using the v2 API directly. The question of what's better: the SDK or DIY with the v2 API, is a question of whether you find the SDK to provide value on top of using the v2 API directly.

1. Install openapi-generator. 
   1. Option 1: with homebrew

        ```bash
        brew install openapi-generator
        ```

   2. Option 2: with java

        (install java, example for on debian/ubuntu) 
        ```bash
        sudo apt install default-jre
        ```

        (then set up `openapi-generator`)
        ```bash
        wget https://repo1.maven.org/maven2/org/openapitools/openapi-generator-cli/7.6.0/openapi-generator-cli-7.6.0.jar -O openapi-generator-cli.jar
        alias openapi-generator='java -jar ~/path/to/openapi-generator-cli.jar'
        ```

2. After `openapi-generator` is available, download `openapi.json` from the BAM, into your git repository, and run:

    ```bash
    openapi-generator generate -i openapi.json -g python -o openapi_client
    ```

#### 4. Using the [bluecat terraform provider](https://registry.terraform.io/providers/bluecatlabs/bluecat/latest/docs)

Ignore the message that says "API version 25.0.0 or above." This is just confusing terminology. Their "integrity API" project has a version number which is completely unrelated to the version numbers you see in your BAM product.

Yes, you should expect a good experience using the bluecat terraform provider. It's stable and officially supported.

#### 5. The Bluecat Ansible Module

I'm confused about this. BAM is an Integrity product, but this stuff all talks about Bluecat Gateway. Don't understand what the product lines are from Bluecat, and whether this applies to BAM customers.

Links:

* https://bluecatnetworks.com/integrations/ansible-module/
* https://bluecatnetworks.com/blog/bluecat-ansible-integration/
* https://www.youtube.com/watch?v=HJ09lY5it9I
* I'm not sure which of these is better. They are both called "Ansible Module Administration Guide," but one of them is version 2.9 and the other 23.1
  * https://docs.bluecatnetworks.com/r/en-US/Ansible-Module-Administration-Guide/2.9
  * https://docs.bluecatnetworks.com/r/en-US/Ansible-Module-Administration-Guide/23.1

## To-Do

- Find a free IP address for a CIDR subnet (done; could rename the method if  we decide upon some logical way to organize method names etc)

- Assign IP address (create A and PTR records, internal/external/both)

- Delete IP address (and associated records pointing at the IP), internal/external/both

- The above imply need for creating/deleting/changing A records

- Create / Delete "external" hosts. In the internal/external/both views

- Create / Delete CNAMEs

- (something to think about) search for unused records, like TXT and _acme-challenge records in the internal view, or no longer used.
