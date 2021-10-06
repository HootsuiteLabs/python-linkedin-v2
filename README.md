# Python LinkedIn V2

Python interface to the LinkedIn API V2

[![LinkedIn](http://developer.linkedin.com/sites/default/files/LinkedIn_Logo60px.png)](http://developer.linkedin.com)

This library provides a pure Python interface to the LinkedIn **Profile** and **Connections** REST APIs.

[LinkedIn](http://developer.linkedin.com) provides a service that lets people bring their LinkedIn profiles and networks with them to your site or application via their OAuth based API. This library provides a lightweight interface over a complicated LinkedIn OAuth based API to make it for python programmers easy to use.

## Installation

[![Build Status](https://travis-ci.org/ozgur/python-linkedin.png?branch=master)](https://travis-ci.org/ozgur/python-linkedin)

You can install **python-linkedin-v2** library via pip:

    $ pip install python-linkedin-v2

## Authentication

The LinkedIn REST API now supports the **OAuth 2.0** protocol for authentication. This package provides a full OAuth 2.0 implementation for connecting to LinkedIn as well as an option for using an OAuth 1.0a flow that can be helpful for development purposes or just accessing your own data.

### HTTP API example

Set `LINKEDIN_API_KEY` and `LINKEDIN_API_SECRET`, configure your app to redirect to `http://localhost:8080/code`, then execute:

  0. `http_api.py`
  1. Visit `http://localhost:8080` in your browser, curl or similar
  2. A tab in your browser will open up, give LinkedIn permission there
  3. You'll then be presented with a list of available routes, hit any, e.g.:
  4. `curl -XGET http://localhost:8080/get_profile`

### Developer Authentication

To connect to LinkedIn as a developer or just to access your own data, you don't even have to implement an OAuth 2.0 flow that involves redirects. You can simply use the 4 credentials that are provided to you in your LinkedIn appliation as part of an OAuth 1.0a flow and immediately access your data. Here's how:

```python
from linkedin_v2 import linkedin

# Define CONSUMER_KEY, CONSUMER_SECRET,  
# USER_TOKEN, and USER_SECRET from the credentials 
# provided in your LinkedIn application

# Instantiate the developer authentication class

authentication = linkedin.LinkedInDeveloperAuthentication(CONSUMER_KEY, CONSUMER_SECRET, 
                                                          USER_TOKEN, USER_SECRET, 
                                                          RETURN_URL, linkedin.PERMISSIONS.enums.values())

# Pass it in to the app...

application = linkedin.LinkedInApplication(authentication)

# Use the app....

application.get_profile()
```


### Production Authentication
In order to use the LinkedIn OAuth 2.0, you have an **application key** and **application secret**. You can get more detail from [here](http://developers.linkedin.com/documents/authentication).

For debugging purposes you can use the credentials below. It belongs to my test application. Nothing's harmful.

```python
KEY = 'wFNJekVpDCJtRPFX812pQsJee-gt0zO4X5XmG6wcfSOSlLocxodAXNMbl0_hw3Vl'
SECRET = 'daJDa6_8UcnGMw1yuq9TjoO_PMKukXMo8vEMo7Qv5J-G3SPgrAV0FqFCd0TNjQyG'
```
You can also get those keys from [here](http://developer.linkedin.com/rest).

LinkedIn redirects the user back to your website's URL after granting access (giving proper permissions) to your application. We call that url **RETURN URL**. Assuming your return url is **http://localhost:8000**, you can write something like this:

```python
from linkedin_v2 import linkedin

API_KEY = 'wFNJekVpDCJtRPFX812pQsJee-gt0zO4X5XmG6wcfSOSlLocxodAXNMbl0_hw3Vl'
API_SECRET = 'daJDa6_8UcnGMw1yuq9TjoO_PMKukXMo8vEMo7Qv5J-G3SPgrAV0FqFCd0TNjQyG'
RETURN_URL = 'http://localhost:8000'

authentication = linkedin.LinkedInAuthentication(API_KEY, API_SECRET, RETURN_URL, linkedin.PERMISSIONS.enums.values())
# Optionally one can send custom "state" value that will be returned from OAuth server
# It can be used to track your user state or something else (it's up to you)
# Be aware that this value is sent to OAuth server AS IS - make sure to encode or hash it
#authorization.state = 'your_encoded_message'
print(authentication.authorization_url)  # open this url on your browser
application = linkedin.LinkedInApplication(authentication)
```
When you grant access to the application, you will be redirected to the return url with the following query strings appended to your **RETURN_URL**:

```python
"http://localhost:8000/?code=AQTXrv3Pe1iWS0EQvLg0NJA8ju_XuiadXACqHennhWih7iRyDSzAm5jaf3R7I8&state=ea34a04b91c72863c82878d2b8f1836c"
```

This means that the value of the **authorization_code** is **AQTXrv3Pe1iWS0EQvLg0NJA8ju_XuiadXACqHennhWih7iRyDSzAm5jaf3R7I8**. After setting it by hand, we can call the **.get_access_token()** to get the actual token.

```python
authentication.authorization_code = 'AQTXrv3Pe1iWS0EQvLg0NJA8ju_XuiadXACqHennhWih7iRyDSzAm5jaf3R7I8'
token = authentication.get_access_token()
```

you can retrieve the access token though the namedtuple returned by the get_access_token method

```python
print(token.access_token)
print(token.expires_in)
```

optionally, LinkedIn supports programmatic refresh tokens for all approved Marketing Developer Platform (MDP) partners, so
you can obtain a new access token passing a refresh token to the refresh_access_token method, more info [here](https://docs.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens)

```python
refresh_token = token.refresh_token # the token previously obtained via Oauth
authentication = linkedin.LinkedInAuthentication(API_KEY, API_SECRET)
new_token = authentication.refresh_access_token(refresh_token)
print(new_token.access_token)
print(new_token.expires_in)
print(new_token.refresh_token)
print(new_token.refresh_token_expires_in)
```

After you get the access token, you are now permitted to make API calls on behalf of the user who granted access to you app. In addition to that, in order to prevent from going through the OAuth flow for every consecutive request,
one can directly assign the access token obtained before to the application instance.

```python
application = linkedin.LinkedInApplication(token='AQTFtPILQkJzXHrHtyQ0rjLe3W0I')
```

## Profile API
The Profile API returns a member's LinkedIn profile. For more information, check out the [documentation](http://developers.linkedin.com/documents/profile-api).

```python
application.get_profile()
{
  "id": "yrZCpj2Z12",
  "firstName": {
    "localized": {
      "en_US": "Bob"
    },
    "preferredLocale": {
      "country": "US",
      "language": "en"
    }
  },
  "lastName": {
    "localized": {
      "en_US": "Smith"
    },
    "preferredLocale": {
      "country": "US",
      "language": "en"
    }
  },
  "location": {
    "countryCode": "us",
    "postalCode": "94101",
    "standardizedLocationUrn": "urn:li:standardizedLocationKey:(us,94101)"
  },
  "positions": {
    "660879450": {
      "companyName": {
        "localized": {
          "en_US": "LinkedIn"
        },
        "preferredLocale": {
          "country": "US",
          "language": "en"
        }
      },
      "id": 660879450,
      "title": {
        "localized": {
          "en_US": "Staff Software Engineer"
        },
        "preferredLocale": {
          "country": "US",
          "language": "en"
        }
      }
    }
  },
  "headline": {
    "localized": {
      "en_US": "API Enthusiast at LinkedIn"
    },
    "preferredLocale": {
      "country": "US",
      "language": "en"
    }
  }
}
```

## Connections API
The Connections API returns a list of **1st degree** connections for a user who has granted access to their account. For more information, you check out its [documentation](http://developers.linkedin.com/documents/connections-api).

To fetch your connections, you simply call **.get_connections()** method with proper GET querystring:

```python
application.get_connections()
{
  "elements": [
    {
      "to": "urn:li:person:9HfhE6QlBz"
    }
  ],
  "paging": {
    "total": 1,
    "count": 50,
    "start": 0,
    "links": []
  }
}

application.get_connections(totals_only=True)
{
   "elements":[

   ],
   "paging":{
      "total":303,
      "count":0,
      "start":0
   }
}
```

## Throttle Limits

LinkedIn API keys are throttled by default. You should take a look at the [Throttle Limits Documentation](http://developer.linkedin.com/documents/throttle-limits) to get more information about it.
