# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import contextlib
import hashlib
import random

try:
    from urllib.parse import quote
except ImportError:
    from urllib import quote

import requests
from requests_oauthlib import OAuth1

from .models import AccessToken
from .utils import enum, to_utf8, raise_for_error, StringIO


__all__ = ['LinkedInAuthentication', 'LinkedInApplication', 'PERMISSIONS']

PERMISSIONS = enum('Permission',
                   COMPANY_ADMIN='rw_company_admin',
                   LITE_PROFILE='r_liteprofile',
                   BASIC_PROFILE='r_basicprofile',
                   FULL_PROFILE='r_fullprofile',
                   EMAIL_ADDRESS='r_emailaddress',
                   NETWORK='r_network',
                   CONTACT_INFO='r_contactinfo',
                   NETWORK_UPDATES='rw_nus',
                   GROUPS='rw_groups',
                   MESSAGES='w_messages')

ENDPOINTS = enum('LinkedInURL',
                 BASE='https://api.linkedin.com/v2',
                 CONNECTIONS='https://api.linkedin.com/v2/connections',
                 PEOPLE='https://api.linkedin.com/v2/people',
                 PEOPLE_SEARCH='https://api.linkedin.com/v2/people-search',
                 GROUPS='https://api.linkedin.com/v2/groups',
                 POSTS='https://api.linkedin.com/v2/posts',
                 COMPANIES='https://api.linkedin.com/v2/companies',
                 COMPANY_SEARCH='https://api.linkedin.com/v2/company-search',
                 JOBS='https://api.linkedin.com/v2/jobs',
                 JOB_SEARCH='https://api.linkedin.com/v2/job-search')

NETWORK_UPDATES = enum('NetworkUpdate',
                       APPLICATION='APPS',
                       COMPANY='CMPY',
                       CONNECTION='CONN',
                       JOB='JOBS',
                       GROUP='JGRP',
                       PICTURE='PICT',
                       EXTENDED_PROFILE='PRFX',
                       CHANGED_PROFILE='PRFU',
                       SHARED='SHAR',
                       VIRAL='VIRL')

PROJECTIONS = enum('Projection',
                   EXPAND_PROFILE_PICTURE={'projection': '(id,firstName,lastName,profilePicture(displayImage~:playableStreams))'},
                   EXPAND_EMAIL={'q': 'members', 'projection': '(elements*(handle~))'})


class LinkedInDeveloperAuthentication(object):
    """
    Uses all four credentials provided by LinkedIn as part of an OAuth 1.0a
    flow that provides instant API access with no redirects/approvals required.
    Useful for situations in which users would like to access their own data or
    during the development process.
    """

    def __init__(self, consumer_key, consumer_secret, user_token, user_secret,
                 redirect_uri, permissions=[]):
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.user_token = user_token
        self.user_secret = user_secret
        self.redirect_uri = redirect_uri
        self.permissions = permissions


class LinkedInAuthentication(object):
    """
    Implements a standard OAuth 2.0 flow that involves redirection for users to
    authorize the application to access account data.
    """
    AUTHORIZATION_URL = 'https://www.linkedin.com/oauth/v2/authorization'
    ACCESS_TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'

    def __init__(self, key, secret, redirect_uri, permissions=None):
        self.key = key
        self.secret = secret
        self.redirect_uri = redirect_uri
        self.permissions = permissions or []
        self.state = None
        self.authorization_code = None
        self.token = None
        self._error = None

    @property
    def authorization_url(self):
        qd = {'response_type': 'code',
              'client_id': self.key,
              'scope': (' '.join(self.permissions)).strip(),
              'state': self.state or self._make_new_state(),
              'redirect_uri': self.redirect_uri}
        # urlencode uses quote_plus when encoding the query string so,
        # we ought to be encoding the qs by on our own.
        qsl = ['%s=%s' % (quote(k), quote(v)) for k, v in qd.items()]
        return '%s?%s' % (self.AUTHORIZATION_URL, '&'.join(qsl))

    @property
    def last_error(self):
        return self._error

    def _make_new_state(self):
        return hashlib.md5(
            '{}{}'.format(random.randrange(0, 2 ** 63), self.secret).encode("utf8")
        ).hexdigest()

    def get_access_token(self, timeout=60):
        assert self.authorization_code, 'You must first get the authorization code'
        qd = {'grant_type': 'authorization_code',
              'code': self.authorization_code,
              'redirect_uri': self.redirect_uri,
              'client_id': self.key,
              'client_secret': self.secret}
        response = requests.post(self.ACCESS_TOKEN_URL, data=qd, timeout=timeout)
        raise_for_error(response)
        response = response.json()
        self.token = AccessToken(response['access_token'], response['expires_in'])
        return self.token


class LinkedInSelector(object):
    @classmethod
    def parse(cls, selector):
        with contextlib.closing(StringIO()) as result:
            if type(selector) == dict:
                for k, v in selector.items():
                    result.write('%s:(%s)' % (to_utf8(k), cls.parse(v)))
            elif type(selector) in (list, tuple):
                result.write(','.join(map(cls.parse, selector)))
            else:
                result.write(to_utf8(selector))
            return result.getvalue()


class LinkedInApplication(object):
    BASE_URL = 'https://api.linkedin.com'

    def __init__(self, authentication=None, token=None):
        assert authentication or token, 'Either authentication instance or access token is required'
        self.authentication = authentication
        if not self.authentication:
            self.authentication = LinkedInAuthentication('', '', '')
            self.authentication.token = AccessToken(token, None)

    def make_request(self, method, url, data=None, params=None, headers=None,
                     timeout=60):
        if headers is None:
            headers = {'x-li-format': 'json', 'Content-Type': 'application/json'}
        else:
            headers.update({'x-li-format': 'json', 'Content-Type': 'application/json'})

        if params is None:
            params = {}
        kw = dict(data=data, params=params,
                  headers=headers, timeout=timeout)

        if isinstance(self.authentication, LinkedInDeveloperAuthentication):
            # Let requests_oauthlib.OAuth1 do *all* of the work here
            auth = OAuth1(self.authentication.consumer_key, self.authentication.consumer_secret,
                          self.authentication.user_token, self.authentication.user_secret)
            kw.update({'auth': auth})
        else:
            params.update({'oauth2_access_token': self.authentication.token.access_token})

        return requests.request(method.upper(), url, **kw)

    def get_connections(self, totals_only=None, params=None, headers=None):
        count = '50'
        if totals_only:
            count = '0'
        url = '%s?q=viewer&start=0&count=%s' % (ENDPOINTS.CONNECTIONS, count)
        response = self.make_request('GET', url, params=params, headers=headers)
        raise_for_error(response)
        return response.json()

    def get_profile(self, member_id=None, member_url=None, selectors=None,
                    params=None, headers=None):
        connections = 0
        if selectors is not None and 'num-connections' in selectors:
            connections_response = self.get_connections(totals_only=True)
            connections_body = connections_response.get('paging', None)
            connections = connections_body.get('total', 0)
        
        url = '%s/me' % ENDPOINTS.BASE
        response = self.make_request('GET', url, params=params, headers=headers)
        raise_for_error(response)
        json_response = response.json()
        json_response.update({'numConnections': connections})
        return json_response

    def get_email(self):
        url = '%s/emailAddress' % ENDPOINTS.BASE
        response = self.make_request('GET', url, params=PROJECTIONS.EXPAND_EMAIL)
        raise_for_error(response)
        return response.json()
