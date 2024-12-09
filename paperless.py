#!/usr/bin/env python3
# encoding: utf-8

from asyncio import subprocess
import os
import subprocess
import sys
import argparse
import keyring
import enum
import requests
import urllib.parse
from os import path
from dateutil.parser import parse
from unicodedata import normalize

import alfred_encoder
from cache import PaperlessCache

PAPERLESS_INSTANCE = os.environ['PAPERLESS_INSTANCE']
if not PAPERLESS_INSTANCE.endswith('/'):
    PAPERLESS_INSTANCE += '/'
PAPERLESS_API_ENDPOINT = PAPERLESS_INSTANCE + 'api/'
SERVICE_NAME = 'com.nelatmani.paperless'


class PaperlessStatus(enum.Enum):
    OK = 0
    ERROR_CREDENTIAL_INVALID = enum.auto()
    ERROR_CREDENTIAL_NOT_FOUND = enum.auto()
    ERROR_SEARCH_FAILED = enum.auto()
    ERROR_INVALID_ARGUMENT = enum.auto()


def alfred_return(cache, status, alfred_result=None):
    if status != PaperlessStatus.OK:
        if not alfred_result:
            sys.stdout.writelines(str(status) + '\n')
        else:
            result_list = alfred_encoder.AlfredResultList()
            result_list.append(alfred_result)
            result_list.send_to_alfred(cache)
        return 1
    return 0


def convert_paperless_json_to_alfred(cache, token, json_result, json_correspondents):
    alfred_results_list = alfred_encoder.AlfredResultList()

    if json_result['count'] == 0:
        alfred_results_list.append(
            alfred_encoder.AlfredResult("No result found",
                                        "Try another search term", "")
        )

    for result in json_result['results']:
        file_id = result['id']
        thumbnail_url = PAPERLESS_API_ENDPOINT + \
            'documents/' + str(file_id) + '/thumb/'
        thumbnail_name = '{}.png'.format(file_id)
        document_name = '{}.pdf'.format(file_id)
        subtitle_format = "ASN: {} | Correspondent: {} | Date created: {}"

        if not cache.exists(thumbnail_name):
            cache.cache_item(token, thumbnail_url, thumbnail_name)
        if cache.exists(document_name):
            result_type = 'file'
            arg = cache.get_path(document_name)
            subtitle = "↓ "
        else:
            result_type = 'default'
            arg = file_id
            subtitle = "⇣ "
        title = str(result['title'])
        if len(str(result['title'])) > 80:
            title = title[:80] + "..."
        asn = result['archive_serial_number'] or "None"
        date = parse(result['added']).date()

        correspondent = "None"
        correspondent_id = result['correspondent']
        if correspondent_id:
            correspondent = get_correspondent_name(json_correspondents, correspondent_id)

        subtitle += subtitle_format.format(asn, correspondent, date)
        icon = {'path': 'pdf.png'}
        alfred_results_list.append(
            alfred_encoder.AlfredResult(title, subtitle, arg, icon=icon, _type=result_type))

    return alfred_results_list

def query_api(token, endpoint, params=None):
    url = PAPERLESS_API_ENDPOINT + endpoint
    auth_header = {'Authorization': "Token " + token}

    if params:
        url += "?" + urllib.parse.urlencode(params)
    return requests.get(url, headers=auth_header)

def get_correspondents(token):
    connect_endpoint = 'correspondents/'
    results = query_api(token, connect_endpoint, {"format": "json"})
    if results.status_code != requests.codes.ok:
        return PaperlessStatus.ERROR_CREDENTIAL_INVALID

    return results.json()

def get_correspondent_name(correspondents, correspondent_id):
    if correspondents['count'] == 0:
        return None

    for correspondent in correspondents["results"]:
        if correspondent["id"] == correspondent_id:
            return correspondent["name"]

    return None

def search_documents(cache, token, term):
    connect_endpoint = 'documents/'
    term = normalize('NFC', term)
    results = query_api(token, connect_endpoint, {"query": term})
    if results.status_code != requests.codes.ok:
        return PaperlessStatus.ERROR_SEARCH_FAILED

    results = results.json()
    correspondents = get_correspondents(token)
    if correspondents == PaperlessStatus.ERROR_CREDENTIAL_INVALID:
        return PaperlessStatus.ERROR_CREDENTIAL_INVALID

    documents = convert_paperless_json_to_alfred(cache, token, results, correspondents)
    documents.send_to_alfred(cache)

    return PaperlessStatus.OK


def open_document(cache, token, arg):
    try:
        document_name = "{}.pdf".format(int(arg))
        document_url = PAPERLESS_API_ENDPOINT + \
            'documents/' + str(arg) + '/preview/'
        cache.cache_item(token, document_url, document_name)
        cache.sync()
    except Exception:
        document_name = path.basename(arg)

    subprocess.call(["open", cache.get_path(document_name)])


def save_credential(credentials):
    session = requests.session()
    connect_endpoint = 'token/'
    payload = {'username': credentials[0], 'password':  credentials[1]}

    url = PAPERLESS_API_ENDPOINT + connect_endpoint
    session.get(PAPERLESS_INSTANCE)
    csrftoken = session.cookies['csrftoken']
    token = session.post(url, headers={"X-CSRFToken": csrftoken}, json=payload)
    if token.status_code != requests.codes.ok:
        return PaperlessStatus.ERROR_CREDENTIAL_INVALID

    token = token.json()['token']
    keyring.set_password(SERVICE_NAME, 'token', token)
    return PaperlessStatus.OK


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--connect', dest='credentials', nargs=2, default=None)
    parser.add_argument('--open', dest='download', nargs=1)
    parser.add_argument('query', nargs='?')

    # Alfred does not pass argv properly, as such python detect only one big
    # argument, instead of a list. Work around that here for the parser to
    # understand the query properly
    connect_args = list(filter(lambda x: '--connect' in x, sys.argv))
    open_args = list(filter(lambda x: '--open' in x, sys.argv))
    if len(connect_args) > 0:
        args = parser.parse_args(connect_args[0].split())
    elif len(open_args) > 0:
        args = parser.parse_args(open_args[0].split())
    else:
        args = parser.parse_args(sys.argv[1:])

    cache = PaperlessCache(SERVICE_NAME)
    status = PaperlessStatus.OK

    if args.credentials:
        return alfred_return(cache, save_credential(args.credentials))

    token = keyring.get_password(SERVICE_NAME, 'token')
    if not token:
        return alfred_return(cache,
                             PaperlessStatus.ERROR_CREDENTIAL_NOT_FOUND,
                             alfred_encoder.AlfredResult("No credential found",
                                                         "Please run 'pplc <username> <password>' to set the API token",
                                                         arg=""))

    if args.query:
        status = alfred_return(
            cache, search_documents(cache, token, args.query))

    if args.download:
        status = alfred_return(cache, open_document(cache, token, args.download[0]))

    del cache
    return status


if __name__ == "__main__":
    exit(main())
