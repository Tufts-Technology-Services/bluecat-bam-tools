# bluecat-bam-tools

In this document, Bluecat Address Manager is abbreviated BAM.

This project is public open source, MIT licensed.

## Usage

To use the `bluecat_bam_tools` module in your project, `pip install` the following line, or add it to your `requirements.txt`. Notice the tagged version `@v0.1.1` in the URL and modify as appropriate.

Please see `sandbox.py` for example usage, including a typical usage of the `keyring` module to securely store credentials.

    git+https://github.com/Tufts-Technology-Services/bluecat-bam-tools.git@v0.1.1#egg=bluecat_bam_tools

Then

```python
from bluecat_bam_tools.bluecat_client import BluecatClient

hostname = "example.org"  # hostname of your BAM
username = "exampleuser"
password = "examplepassword"
verify_ssl = true  # require valid SSL cert

with BluecatClient(hostname, username, password, verify_ssl=verify_ssl) as client:
    # Optionally, handle exceptions during login() for more friendly output.
    # Exceptions include: ConnectionError, Timeout, HTTPError, RequestException
    # But I'm not doing that for this simple example.
    client.login()
    cidr = '10.10.10.0/24'
    
    # Returns the dict describing the network
    network = client.get_network_by_cidr(cidr)
    
    # Returns a list of dicts, each describing the IP address object
    # Includes UNASSIGNED and STATIC addresses, if there are
    # no resourceRecords (DNS entries) pointing at the IP address
    addresses = client.get_unassigned_addresses_in_network_by_cidr(cidr)
```

Methods:
* **`login()`**
  Attempts to log in
  Raises `ConnectionError`, `Timeout`, `HTTPError`,  `RequestException`
  
  ```python
  # Example:
  client.login()
  ```
* **`logout()`**
  You should use a `with` block instead, to guarantee this will be called instead of you calling it.
  
  ```python
  # Example:
  client.logout()
  ```
* **`http_get(url: str)`**
  Performs HTTP GET, automatically handles pagination for you.
  `url` should be in the form `"/foobar"` excluding `"/api/v2"`. The URL base `https://{hostname}/api/v2` is prepended automatically for you.
  
  ```python
  # Example:
  configurations = client.http_get('/configurations')
  ```
* **`get_network_by_cidr(cidr: str)`**
  Returns a `dict` describing the network
  Raises `ValueError` if the network is not found
  
  ```python
  # Example:
  network = client.get_network_by_cidr('10.10.10.0/24')
  ```
* **`get_unassigned_addresses_in_network_by_cidr(cidr: str)`**
  Returns a `list` of `dict`, each describing unassigned IP addresses within a specified network
  This method retrieves all IP addresses in the specified network that are either:
  
  1. Explicitly marked as UNASSIGNED in BlueCat Address Manager
  2. Marked as STATIC but have no associated resource records (DNS entries)
  
  The second case handles situations where users delete DNS records but neglect
  to check the "Delete linked IP addresses if orphaned" option in the web UI
  
  ```python
  # Example:
  addresses = client.get_unassigned_addresses_in_network_by_cidr('10.10.10.0/24')
  ```

## Developer Notes

If you plan to do development on this project, such as editing or running `sandbox.py`, several packages are necessary to support the sandbox, which are not needed by any public users who just `pip install` our package. To set up the development environment:

```bash
pip install -r requirements-dev.txt
```

Join the developer community ([Bluecat Network VIP](https://bluecatnetworks.com/network-vip/)). When prompted what product you use, BAM is part of the "Integrity" line. Choose Integrity. I have had a fantastic experience with this community. It's a small community but each question I've asked got immediate helpful replies.

## Comparison of bluecat automation options

Four options were considered, for management of bluecat resources. Discussion was had ([this is a link to the discussion](https://community.bluecatnetworks.com/integrity-20/automating-bluecat-address-manager-2036?postid=12416#post12416)) in the bluecat [community forum](https://community.bluecatnetworks.com) and a bluecat employee chimed in. All members of the community recommended the DIY v2 API approach, so that is what's used in this project.

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
