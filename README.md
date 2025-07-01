# bluecat-bam-tools

In this document, Bluecat Address Manager is abbreviated BAM.

This project is public open source, MIT licensed.

## Usage

To use the `bluecat_bam_tools` module in your project, `pip install` the following line, or add it to your `requirements.txt`. Notice the tagged version `@v0.1.0` in the URL and modify as appropriate.

Please see `sandbox.py` for example usage, including a typical usage of the `keyring` module to securely store credentials.

    git+https://github.com/Tufts-Technology-Services/bluecat-bam-tools.git@v0.1.0#egg=bluecat_bam_tools

## Developer Notes

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

#### 2. The [bluecat-libraries](https://pypi.org/project/bluecat-libraries/) pip module

There is nothing wrong with using this. It uses the v1 API but why would you care. Maybe someday the old API will become deprecated and this module along with it? Probably not anytime soon. In the bluecat community, it was not the recommended approach, but there are no objections to it either.

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
