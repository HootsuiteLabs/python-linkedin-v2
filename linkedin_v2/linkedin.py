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

from .models import *
from .utils import enum, to_utf8, raise_for_error, StringIO
import json
import urllib


__all__ = ['LinkedInAuthentication', 'LinkedInApplication', 'PERMISSIONS']

PERMISSIONS = enum('Permission',
                   COMPANY_ADMIN='rw_company_admin',
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
                 COMPANY_SEARCH='https://api.linkedin.com/v2/search?q=companiesV2',
                 JOBS='https://api.linkedin.com/v2/jobs',
                 JOB_SEARCH='https://api.linkedin.com/v2/job-search',
                 SHARE='https://api.linkedin.com/v2/shares')

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


REDIRECT_URI_ERROR_MESSAGE = 'You must init LinkedInAuthentication with a redirect_url'
AUTHORIZATION_CODE_ERROR_MESSAGE = 'You must first get the authorization code'

class LinkedInAuthentication(object):
    """
    Implements a standard OAuth 2.0 flow that involves redirection for users to
    authorize the application to access account data.
    """
    AUTHORIZATION_URL = 'https://www.linkedin.com/uas/oauth2/authorization'
    ACCESS_TOKEN_URL = 'https://www.linkedin.com/uas/oauth2/accessToken'

    def __init__(self, key, secret, redirect_uri=None, permissions=None):
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
        assert self.redirect_uri, REDIRECT_URI_ERROR_MESSAGE
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
            '{}{}'.format(random.randrange(0, 2 ** 63),
                          self.secret).encode("utf8")
        ).hexdigest()

    @staticmethod
    def _get_token_from_response(response):
        response = response.json()
        access_token = response.get(ACCESS_TOKEN_KEY)
        expires_in = response.get(EXPIRES_IN_KEY)
        refresh_token = response.get(REFRESH_TOKEN_KEY)
        refresh_token_expires_in = response.get(REFRESH_TOKEN_EXPIRES_IN_KEY)

        return AccessToken(
            access_token,
            expires_in,
            refresh_token or None,
            refresh_token_expires_in or None
        )

    def get_access_token(self, timeout=TIMEOUT):
        assert self.authorization_code, AUTHORIZATION_CODE_ERROR_MESSAGE
        assert self.redirect_uri, REDIRECT_URI_ERROR_MESSAGE
        qd = {'grant_type': 'authorization_code',
              'code': self.authorization_code,
              'redirect_uri': self.redirect_uri,
              'client_id': self.key,
              'client_secret': self.secret}
        response = requests.post(self.ACCESS_TOKEN_URL, data=qd, timeout=timeout)
        raise_for_error(response)

        self.token = self._get_token_from_response(response)
        return self.token

    def refresh_access_token(self, refresh_token, timeout=TIMEOUT):
        """
        Exchanges a Refresh Token for a New Access Token
        :param refresh_token: str
        :param timeout: int
        :return: AccessToken
        """
        qd = {
            'grant_type': 'refresh_token',
            REFRESH_TOKEN_KEY: refresh_token,
            'client_id': self.key,
            'client_secret': self.secret
        }
        response = requests.post(self.ACCESS_TOKEN_URL, data=qd, timeout=timeout)
        raise_for_error(response)

        self.token = self._get_token_from_response(response)
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
            self.authentication.token = AccessToken(token, None, None, None)

    def make_request(self, method, url, data=None, params=None, headers=None,
                     timeout=TIMEOUT):
        if headers is None:
            headers = {'x-li-format': 'json',
                       'Content-Type': 'application/json'}
        else:
            headers.update(
                {'x-li-format': 'json', 'Content-Type': 'application/json'})

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
            params.update(
                {'oauth2_access_token': self.authentication.token.access_token})

        return requests.request(method.upper(), url, **kw)

    def make_get_request(self, url):
        print(url)
        response = self.make_request('GET', url)
        # raise_for_error(response)
        return response.json()

    def get_connections(self, totals_only=None, params=None, headers=None):
        count = '50'
        if totals_only:
            count = '0'
        url = '%s?q=viewer&start=0&count=%s' % (ENDPOINTS.CONNECTIONS, count)
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        # raise_for_error(response)
        return response.json()

    def get_profile(self, member_id=None, member_url=None, selectors=None,
                    params=None, headers=None):
        connections = 0
        if selectors is not None and 'num-connections' in selectors:
            connections_response = self.get_connections(totals_only=True)
            connections_body = connections_response.get('paging', None)
            connections = connections_body.get('total', 0)

        url = '%s/me' % ENDPOINTS.BASE
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        raise_for_error(response)
        json_response = response.json()
        json_response.update({'numConnections': connections})
        return json_response

    def get_shares(self, totals_only=None, params=None, headers=None):
        count = '100'
        if totals_only:
            count = '0'
        url = '%s?q=owners&owners=urn:li:person:%s&sharesPerOwner=100' % (
            ENDPOINTS.SHARE, self.get_profile()['id'])
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        raise_for_error(response)
        return response.json()

    def search_profile(self, params):
        url = '%s/clientAwareMemberHandles?q=handleString&%s&projection=(elements*(member~))' % (
            ENDPOINTS.BASE, urllib.parse.urlencode(params))
        print(url)
        response = self.make_request('GET', url)
        raise_for_error(response)
        return response.json()

    def post_share(self, post_type='person', company_id=None, title=None, description=None,
                   submitted_url=None, submitted_image_url=None):

        if post_type == 'organization':
            post_owner = "urn:li:organization:%s" % company_id
        else:
            post_owner = "urn:li:person:%s" % self.get_profile()['id']

        post = {
            "owner": post_owner,
            "text": {
                "text": ""
            },
            "subject": "",
            "distribution": {
                "linkedInDistributionTarget": {}
            },
            "content": {
                "contentEntities": [],
                "title": ""
            }
        }

        content_entity = {
            "entityLocation": "",
            "thumbnails": []
        }

        if title is not None:
            post['content']['title'] = title
            post['subject'] = title

        if description is not None:
            post['text']['text'] = description

        if submitted_url is not None:
            content_entity['entityLocation'] = submitted_url

        if submitted_image_url is not None:
            content_entity['thumbnails'] = [{"imageSpecificContent": {}, "resolvedUrl": submitted_image_url}]

        post['content']['contentEntities'] = [content_entity]

        response = self.make_request(
            'POST', ENDPOINTS.SHARE, data=json.dumps(post))
        return response.json()

    def search_company(self, params):
        url = '%s/search?q=companiesV2&%s' % (
            ENDPOINTS.BASE, urllib.parse.urlencode(params))
        response = self.make_request('GET', url)
        # raise_for_error(response)
        return response.json()

    def get_organization(self, organization_id, params=None, headers=None):
        url = '%s/organizations/%s' % (ENDPOINTS.BASE, organization_id)
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        raise_for_error(response)
        return response.json()

    def get_brand(self, brand_id, params=None, headers=None):
        url = '%s/organizationBrands/%s' % (ENDPOINTS.BASE, brand_id)
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        raise_for_error(response)
        return response.json()

    def send_invitation(self, invitee_email):
        post = {
            "invitee": "urn:li:email:%s" % invitee_email,
            "message": {
                "com.linkedin.invitations.InvitationMessage": {
                    "body": "Let's connect!"
                }
            }
        }
        response = self.make_request(
            'POST', '%s/invitations' % ENDPOINTS.BASE, data=json.dumps(post))
        raise_for_error(response)
        return response.json()

    def search_job(self):
        url = '%s/recommendedJobs?q=byMember' % ENDPOINTS.BASE
        return self.make_get_request(url)

    def get_job(self, **kwargs):
        return self.search_job()

    def get_post_comments(self, selectors, params=None, **kwargs):
        url = '%s/socialActions/urn:li:share:%s/comments' % (
            ENDPOINTS.BASE, kwargs['post_id'])
        print(url)
        response = self.make_request(
            'GET', url, params=params)
        raise_for_error(response)
        return response.json()

    def get_group(self, group_id, params=None, headers=None):
        url = '%s/groupDefinitions/%s' % (ENDPOINTS.BASE, group_id)
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        raise_for_error(response)
        return response.json()

    def get_group_by_ids(self, group_ids, params=None, headers=None):
        url = '%s/groupDefinitions/?ids=List(%s)' % (ENDPOINTS.BASE, group_ids)
        response = self.make_request(
            'GET', url, params=params, headers=headers)
        raise_for_error(response)
        return response.json()

    def get_memberships(self, group_id):
        post = {
            "action": "SEND_REQUEST",
            "group": "urn:li:group:%s" % group_id,
            "members": [
                "urn:li:person:%s" % self.get_profile['id'],
            ]
        }
        response = self.make_request(
            'POST', '%s/groupMemberships?action=membershipAction' % ENDPOINTS.BASE, data=json.dumps(post))
        raise_for_error(response)
        return response.json()

    def submit_group_post(self, group_id, title, description,
                          shareCommentary):
        post = {
            "author": "urn:li:person:%s" % self.get_profile()['id'],
            "containerEntity": "urn:li:group:%s" % group_id,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "media": [
                        {
                            "title": {
                                "attributes": [],
                                "text": title
                            },
                            "description": {
                                "attributes": [],
                                "text": description
                            },
                            "thumbnails": [],
                            "status": "READY"
                        }
                    ],
                    "shareCommentary": {
                        "attributes": [],
                        "text": ""
                    }
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "CONTAINER"
            }
        }
        if shareCommentary is not None:
            post['specificContent']['shareCommentary'] = shareCommentary
        response = self.make_request(
            'POST', ENDPOINTS.SHARE, data=json.dumps(post))
        raise_for_error(response)
        return response.json()

    def get_company_updates(self, organization_id, post):
        url = '%s/people/id=%s/organizations/%s' % (
            ENDPOINTS.SHARE, self.get_profile['id'], organization_id)
        response = self.make_request(
            'POST', url, data=json.dumps(post))
        raise_for_error(response)
        return response.json()

    def get_group(self):
        print(ENDPOINTS.BASE)
        url = "%s/groupMemberships?q=member&member=urn:li:person:%s&membershipStatuses=List(MEMBER,OWNER)" % (
            ENDPOINTS.BASE, self.get_profile()['id'])
        response = self.make_request('GET', url)
        # raise_for_error(response)
        return response.json()

    def submit_company_share(self, **kwargs):
        submitted_url, submitted_image_url, visibility_code = None, None, None
        if kwargs["submitted_url"]:
            submitted_url = kwargs["submitted_url"]
        if kwargs["submitted_image_url"]:
            submitted_image_url = kwargs["submitted_image_url"]
        if kwargs["visibility_code"]:
            visibility_code = kwargs["visibility_code"]
        response = self.post_share(post_type='organization', company_id=kwargs["company_id"], comment=None,
                                   title=kwargs["title"], description=kwargs["description"],
                                   submitted_url=submitted_url, submitted_image_url=submitted_image_url,
                                   visibility_code=visibility_code)
        return response

    def find_member_organization_access_info(self, **kwargs):
        # https://api.linkedin.com/v2/organizationalEntityAcls?q=roleAssignee
        url = "%s/organizationalEntityAcls?q=roleAssignee&role=ADMINISTRATOR&projection=(elements*(*,roleAssignee~(localizedFirstName, localizedLastName), organizationalTarget~(localizedName)))" % ENDPOINTS.BASE
        return self.make_get_request(url)

    def find_organization_access_control_info(self, organization_id):
        # https://api.linkedin.com/v2/organizationalEntityAcls?q=organizationalTarget&organizationalTarget={URN}
        url = "%s/organizationalEntityAcls?q=organizationalTarget&organizationalTarget=urn:li:organization:%s" % (
            ENDPOINTS.BASE, organization_id)
        return self.make_get_request(url)

    def retrieve_lifetime_follower_statistics(self, organization_id):
        # https://api.linkedin.com/v2/organizationalEntityFollowerStatistics?q=organizationalEntity&organizationalEntity={organization URN}
        url = "%s/organizationalEntityFollowerStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:%s" % (
            ENDPOINTS.BASE, organization_id)
        print(url)
        return self.make_get_request(url)

    def retrieve_time_bound_follower_statistics(self, organization_id, range_start, range_end):
        # https://api.linkedin.com/v2/organizationalEntityFollowerStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:2414183&timeIntervals.timeGranularityType=DAY&timeIntervals.timeRange.start=1451606400000&timeIntervals.timeRange.end=1452211200000
        url = "%s/organizationalEntityFollowerStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:%s&timeIntervals.timeGranularityType=DAY&timeIntervals.timeRange.start=%s&timeIntervals.timeRange.end=%s" % (
            ENDPOINTS.BASE, organization_id, range_start, range_end)
        return self.make_get_request(url)

    def retrieve_organization_page_statistics(self, organization_id):
        # https://api.linkedin.com/v2/organizationPageStatistics?q=organization&organization={organization URN}
        url = "%s/organizationPageStatistics?q=organization&organization=urn:li:organization:%s" % (
            ENDPOINTS.BASE, organization_id)
        return self.make_get_request(url)

    def retrieve_share_statistics(self, organization_id):
        # https://api.linkedin.com/v2/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity={organization URN}
        url = "%s/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:%s" % (
            ENDPOINTS.BASE, organization_id)
        return self.make_get_request(url)

    def retrieve_organization_brand_page_statistics(self, brand_id):
        # https://api.linkedin.com/v2/brandPageStatistics?q=brand&brand=urn:li:organizationBrand:3617422
        url = "%s/brandPageStatistics?q=brand&brand=urn:li:organizationBrand:%s" % (
            ENDPOINTS.BASE, brand_id)
        return self.make_get_request(url)

    def delete_share(self, share_id):
        # https://api.linkedin.com/v2/shares/{share ID}
        url = "%s/shares/%s" % (ENDPOINTS.BASE, share_id)
        response = self.make_request('DELETE', url)
        # raise_for_error(response)
        return response.json()

    def retrieve_likes_on_shares(self, share_id):
        # https://api.linkedin.com/v2/socialActions/{shareUrn|ugcPostUrn|commentUrn|groupPostUrn}/likes
        url = "%s/socialActions/urn:li:share:%s/likes" % (
            ENDPOINTS.BASE, share_id)
        return self.make_get_request(url)

    def retrieve_comments_on_shares(self, share_id):
        # https://api.linkedin.com/v2/socialActions/{shareUrn|ugcPostUrn|commentUrn|groupPostUrn}/comments
        url = "%s/socialActions/urn:li:share:%s/comments" % (
            ENDPOINTS.BASE, share_id)
        return self.make_get_request(url)

    def retrieve_statistics_specific_shares(self, organization_id, share_ids):
        # https://api.linkedin.com/v2/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:2414183&shares[0]=urn:li:share:1000000&shares[1]=urn:li:share:1000001
        shaer_str = ''
        count = 0
        for item in share_ids:
            shaer_str = '&shares['+str(count)+']=urn:li:share:'+item
            count = count + 1
        url = "%s/organizationalEntityShareStatistics?q=organizationalEntity&organizationalEntity=urn:li:organization:%s%s" % (
            ENDPOINTS.BASE, organization_id, shaer_str)
        return self.make_get_request(url)
