import copy
import io
import json
import pytest
from requests.auth import _basic_auth_str
from TAXII2Server import TAXII2Server, APP, uuid, create_fields_list, MEDIA_TYPE_STIX_V20, MEDIA_TYPE_TAXII_V20, \
    create_query, convert_sco_to_indicator_sdo
import demistomock as demisto

HEADERS = {
    'Authorization': _basic_auth_str("username", "password"),
    'Accept': '*/*',
}


@pytest.fixture
def taxii2_server_v20(mocker):
    mocker.patch.object(demisto, 'getLicenseID', return_value='test')
    server = TAXII2Server(url_scheme='http',
                          host='demisto',
                          port=7000,
                          collections={'Collection1': 'type:IP', 'Collection2': 'sourceBrands:"Some Feed"'},
                          certificate='',
                          private_key='',
                          http_server=True,
                          credentials={'identifier': 'username',
                                       'password': 'password'},
                          version='2.0',
                          service_address=None,
                          fields_to_present=set())

    return server


@pytest.fixture
def taxii2_server_v21(mocker):
    mocker.patch.object(demisto, 'getLicenseID', return_value='test')
    server = TAXII2Server(url_scheme='http',
                          host='demisto',
                          port=7000,
                          collections={'Collection1': 'type:IP', 'Collection2': {'query': 'sourceBrands:"Some Feed"',
                                                                                 'description': 'Test desc'}},
                          certificate='',
                          private_key='',
                          http_server=True,
                          credentials={'identifier': 'username',
                                       'password': 'password'},
                          version='2.1',
                          service_address=None,
                          fields_to_present=set())

    return server


def util_load_json(path):
    with io.open(path, mode='r', encoding='utf-8') as f:
        return json.loads(f.read())


@pytest.mark.parametrize('fields, result', [("", {'name', 'type'}), ('all', set()),
                                            ('name,type,sha1', {'name', 'type', 'sha1'}),
                                            ('value,type,sha1', {'name', 'type', 'sha1'}),
                                            ('value,indicator_type,createdTime', {'name', 'type', 'createdTime'})])
def test_create_fields_list(fields, result):
    """
        Given
            fields list parameter, expected result
        When
            User enters filter_field param
        Then
            Validate right result returned
    """
    assert result == create_fields_list(fields)


@pytest.mark.parametrize('headers', [{'Authorization': _basic_auth_str("user", "pwd")}, {}])
def test_taxii_wrong_auth(mocker, headers, taxii2_server_v20):
    """
        Given
            Taxii server v2.0
        When
            Getting server discovery, with wrong auth
        Then
            Validate that the error and status code right
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch.object(demisto, 'error')
    mocker.patch.object(demisto, 'updateModuleHealth')
    with APP.test_client() as test_client:
        response = test_client.get('/taxii/', headers=headers)
        assert response.status_code == 401
        assert response.json == {'title': 'Authorization failed'}


@pytest.mark.parametrize('headers', [{'Authorization': _basic_auth_str("username", "password")},
                                     {'Authorization': _basic_auth_str("username", "password"),
                                      'Accept': 'wrong_type'}])
def test_taxii_wrong_accept(mocker, headers, taxii2_server_v20):
    """
        Given
            Taxii server v2.0
        When
            Getting server discovery, with wrong accept header
        Then
            Validate that the error and status code right
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch.object(demisto, 'error')
    mocker.patch.object(demisto, 'updateModuleHealth')
    with APP.test_client() as test_client:
        response = test_client.get('/taxii/', headers=headers)
        assert response.status_code == 406


def test_taxii20_server_discovery(mocker, taxii2_server_v20):
    """
        Given
            Taxii server v2.0
        When
            Getting server discovery
        Then
            Validate that the discovery output as expected
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    with APP.test_client() as test_client:
        response = test_client.get('/taxii/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.taxii+json; version=2.0'
        assert response.json.get('default') == 'http://demisto:7000/threatintel/'


def test_taxii21_server_discovery(mocker, taxii2_server_v21):
    """
        Given
            Taxii server v2.1
        When
            Call server discovery api request
        Then
            Validate that the discovery output as expected
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    with APP.test_client() as test_client:
        response = test_client.get('/taxii/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json.get('default') == 'http://demisto:7000/threatintel/'


def test_taxii20_api_root(mocker, taxii2_server_v20):
    """
        Given
            TAXII v2.0 server, api_root
        When
            Call api_root api request
        Then
            Validate that the api_root information returned as expected
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.taxii+json; version=2.0'
        assert response.json.get('title') == 'Cortex XSOAR TAXII2 Server ThreatIntel'


def test_taxii_wrong_api_root(mocker, taxii2_server_v20):
    """
        Given
            Taxii server v2.0, Not exiting api_root
        When
            Getting api root information, for wrong api_root
        Then
            Validate that the error and status code right
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch.object(demisto, 'error')
    mocker.patch.object(demisto, 'updateModuleHealth')
    with APP.test_client() as test_client:
        response = test_client.get('/not_exsisting_api_root/', headers=HEADERS)
        assert response.status_code == 404
        assert response.json.get('title') == 'Unknown API Root'


def test_taxii20_status(mocker, taxii2_server_v20):
    """
        Given
            Status api call
        When
            Calling a status request
        Then
            Validate the error returned.
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/status/1223456/', headers=HEADERS)
        assert response.status_code == 404


def test_taxii20_collections(mocker, taxii2_server_v20):
    """
        Given
            TAXII Server v2.0
        When
            Calling collections api request
        Then
            Validate that collections returned as expected
    """
    collections = util_load_json('test_data/collections20.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.taxii+json; version=2.0'
        assert response.json == collections


def test_taxii21_collections(mocker, taxii2_server_v21):
    """
        Given
            TAXII Server v2.1
        When
            Calling collections api request
        Then
            Validate that collections returned as expected
    """
    collections = util_load_json('test_data/collections21.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json == collections


def test_taxii20_collection(mocker, taxii2_server_v20):
    """
        Given
            TAXII Server v2.0, collection_id
        When
            Calling collection by id api request
        Then
            Validate that right collection returned
    """
    collections = util_load_json('test_data/collections20.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.taxii+json; version=2.0'
        assert response.json == collections.get('collections')[0]


def test_taxii20_get_collections(mocker, taxii2_server_v20):
    from TAXII2Server import get_server_collections_command

    collections = taxii2_server_v20.get_collections()

    integration_context = {
        'collections': collections['collections']
    }
    result = get_server_collections_command(integration_context=integration_context)

    assert result.outputs == integration_context['collections']


def test_taxii20_get_server_info(mocker, taxii2_server_v20):
    from TAXII2Server import get_server_info_command

    integration_context = {}
    integration_context['server_info'] = taxii2_server_v20.get_discovery_service(instance_execute=True)
    default_url = integration_context['server_info']['default']
    assert default_url == 'https://demisto/instance/execute/threatintel/'

    result = get_server_info_command(integration_context=integration_context)

    assert result.outputs == integration_context['server_info']


def test_taxii21_collection(mocker, taxii2_server_v21):
    """
        Given
            TAXII Server v2.1, collection_id
        When
            Calling collection by id api request
        Then
            Validate that right collection returned
    """
    collections = util_load_json('test_data/collections21.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json == collections.get('collections')[0]


def test_taxii_wrong_collection_id(mocker, taxii2_server_v21):
    """
        Given
            Taxii server v2.1, Not exiting collection_id
        When
            Getting collection information, for wrong collection_id
        Then
            Validate that the error and status code right
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    mocker.patch.object(demisto, 'error')
    mocker.patch.object(demisto, 'updateModuleHealth')
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/not_exsisting_collection_id/', headers=HEADERS)
        assert response.status_code == 404
        assert response.json.get('title') == 'Unknown Collection'


def test_taxii20_manifest(mocker, taxii2_server_v20):
    """
        Given
            TAXII Server v2.0, collection_id, range
        When
            Calling manifest api request for given collection
        Then
            Validate that right manifest returned.
    """
    iocs = util_load_json('test_data/ip_iocs.json')
    manifest = util_load_json('test_data/manifest20.json')
    headers = copy.deepcopy(HEADERS)
    headers['Range'] = 'items 0-4'
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/manifest/',
                                   headers=headers)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.taxii+json; version=2.0'
        assert response.json == manifest


def test_taxii21_manifest(mocker, taxii2_server_v21):
    """
        Given
            TAXII Server v2.1, collection_id
        When
            Calling manifest api request for given collection
        Then
            Validate that right manifest returned.
    """
    iocs = util_load_json('test_data/ip_iocs.json')
    manifest = util_load_json('test_data/manifest21.json')
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/manifest/?limit=4',
                                   headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json == manifest


def test_taxii20_objects(mocker, taxii2_server_v20):
    """
        Given
            TAXII Server v2.0, collection_id, content-range
        When
            Calling get objects api request for given collection
        Then
            Validate that right objects are returned.
    """
    iocs = util_load_json('test_data/ip_iocs.json')
    objects = util_load_json('test_data/objects20.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch.object(uuid, 'uuid4', return_value='1ffe4bee-95e7-4e36-9a17-f56dbab3c777')
    headers = copy.deepcopy(HEADERS)
    headers['Content-Range'] = 'items 0-2/5'
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/objects/',
                                   headers=headers)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.stix+json; version=2.0'
        assert response.json == objects
        assert response.headers.get('Content-Range') == 'items 0-2/5'


def test_taxii20_indicators_objects(mocker, taxii2_server_v20):
    """
        Given
            TAXII Server v2.0, collection_id, content-range, types_for_indicator_sdo
        When
            Calling get objects api request for given collection
        Then
            Validate that right objects are returned.
    """
    iocs = util_load_json('test_data/ip_iocs.json')
    objects = util_load_json('test_data/objects20-indicators.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch('TAXII2Server.SERVER.types_for_indicator_sdo', [
                 'ipv4-addr', 'domain-name', 'ipv6-addr', 'user-account',
                 'email-addr', 'windows-registry-key', 'file', 'url'])
    mocker.patch.object(uuid, 'uuid4', return_value='1ffe4bee-95e7-4e36-9a17-f56dbab3c777')
    headers = copy.deepcopy(HEADERS)
    headers['Content-Range'] = 'items 0-2/5'
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/objects/',
                                   headers=headers)
        assert response.status_code == 200
        assert response.content_type == 'application/vnd.oasis.stix+json; version=2.0'
        assert response.json == objects
        assert response.headers.get('Content-Range') == 'items 0-2/5'


@pytest.mark.parametrize('demisto_iocs_file,res_file,query_type', [
    ('malware_iocs', 'objects21_malware', 'malware'),
    ('file_iocs', 'objects21_file', 'file'),
    ('domain_iocs', 'objects21_domain', 'domain-name,attack-pattern')
])
def test_taxii21_objects(mocker, taxii2_server_v21, demisto_iocs_file, res_file, query_type):
    """
        Given
            TAXII Server v2.1, collection_id, limit, next, type parameter
        When
            Calling get objects api request for given collection
        Then
            Validate that right objects are returned.
    """
    iocs = util_load_json(f'test_data/{demisto_iocs_file}.json')
    objects = util_load_json(f'test_data/{res_file}.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    mocker.patch.object(uuid, 'uuid4', return_value='1ffe4bee-95e7-4e36-9a17-f56dbab3c777')
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/e46189b5-c5c8-5c7f-b947-183e0302b4d3/'
                                   f'objects/?match[type]={query_type}&limit=2&next=1', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json == objects


@pytest.mark.parametrize('api_request', [
    'objects', 'manifest'
])
def test_taxii21_bad_request(mocker, taxii2_server_v21, api_request):
    """
        Given
            TAXII Server v2.1, non-supported filter.
        When
            Calling get objects or manifest api request for given collection
        Then
            Validate that right error returned.
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    mocker.patch.object(demisto, 'error')
    mocker.patch.object(demisto, 'params', return_value={'res_size': '2500'})
    mocker.patch.object(demisto, 'updateModuleHealth')
    with APP.test_client() as test_client:
        response = test_client.get(f'/threatintel/collections/e46189b5-c5c8-5c7f-b947-183e0302b4d3/'
                                   f'{api_request}/?match[version]=3', headers=HEADERS)
        assert response.status_code == 404
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert 'Filtering by ID or version is not supported.' in response.json.get('description')


@pytest.mark.parametrize('api_request', [
    'objects', 'manifest'
])
def test_taxii20_bad_content_range(mocker, taxii2_server_v20, api_request):
    """
        Given
            TAXII Server v2.0, non-supported range.
        When
            Calling get objects or manifest api request for given collection
        Then
            Validate that right error returned.
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v20)
    mocker.patch.object(demisto, 'params', return_value={'res_size': '2500'})
    headers = copy.deepcopy(HEADERS)
    headers['Content-Range'] = 'items 8-2/10'
    with APP.test_client() as test_client:
        response = test_client.get(f'/threatintel/collections/e46189b5-c5c8-5c7f-b947-183e0302b4d3/'
                                   f'{api_request}/', headers=headers)
        assert response.status_code == 416


@pytest.mark.parametrize('res_file,fields,has_extension', [
    ('objects21_no_extention_file', {'name', 'type'}, False),
    ('objects21_spec_fields_file', {'sha1'}, True)])
def test_taxii21_objects_filtered_params(mocker, taxii2_server_v21, res_file, fields, has_extension):
    """
        Given
            TAXII Server v2.1, collection_id, type parameter, filtered_fields params
        When
            Calling get objects api request for given collection
        Then
            Validate that right objects are returned.
    """
    iocs = util_load_json('test_data/file_iocs.json')
    objects = util_load_json(f'test_data/{res_file}.json')
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    mocker.patch('TAXII2Server.SERVER.fields_to_present', fields)
    mocker.patch('TAXII2Server.SERVER.has_extension', has_extension)
    mocker.patch.object(uuid, 'uuid4', return_value='1ffe4bee-95e7-4e36-9a17-f56dbab3c777')
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    with APP.test_client() as test_client:
        response = test_client.get('/threatintel/collections/e46189b5-c5c8-5c7f-b947-183e0302b4d3/'
                                   'objects/?match[type]=file', headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json == objects


@pytest.mark.parametrize('header', (MEDIA_TYPE_TAXII_V20, MEDIA_TYPE_STIX_V20))
def test_taxii21_with_taxii20_header(mocker, taxii2_server_v21, header: str):
    """
    Given
        a TAXII 2.1 server
    When
        calling /taxii2/ with TAXII 2.0 header
    Then
        validate that an appropriate error is returned
    """
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    with APP.test_client() as test_client:
        response = test_client.get('/taxii2/', headers=HEADERS | {'Accept': header})
        assert response.status_code == 406


@pytest.mark.parametrize('query,types,expected_response', (
    ('my custom query', [], 'my custom query'),
    ('my custom query', ['file'], '(my custom query) and (type:"File")'),
    ('my custom query', ['file', 'domain'], '(my custom query) and (type:"File" or type:"domain")'),
))
def test_create_query(query: str, types: list[str], expected_response: str):
    """
        Given
            a query and types to match
        When
            calling create_query
        Then
            Validate that right query is returned.
    """
    assert create_query(query, types) == expected_response


@pytest.mark.parametrize('endpoint', [
    ('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/manifest/?limit=4&added_after=2022-06-03T00:00:00Z'),
    ('/threatintel/collections/4c649e16-2bb7-50f5-8826-2a2d0a0b9631/manifest/?limit=4&added_after=2022-06-03T13:54:27.234765Z')
])
def test_parse_manifest_and_object_args_with_valid_date(mocker, taxii2_server_v21, endpoint):
    """
        Given
            case 1: endpoint with utc date format.
            case 2: endpoint with stix date format.
        When
            testing parse_manifest_and_object_args.
        Then
            Ensure that Should parsing was done correctly and a valid results message was returned.
    """
    iocs = util_load_json('test_data/ip_iocs.json')
    manifest = util_load_json('test_data/manifest21.json')
    mocker.patch.object(demisto, 'params', return_value={'res_size': '100'})
    mocker.patch('TAXII2Server.SERVER', taxii2_server_v21)
    mocker.patch.object(demisto, 'searchIndicators', return_value=iocs)
    with APP.test_client() as test_client:
        response = test_client.get(endpoint, headers=HEADERS)
        assert response.status_code == 200
        assert response.content_type == 'application/taxii+json;version=2.1'
        assert response.json == manifest


def test_convert_sco_to_indicator_sdo_with_type_file(mocker):
    """
        Given
            sco indicator to sdo indicator with type file.
        When
            Running convert_sco_to_indicator_sdo.
        Then
            Validating the result
    """
    xsoar_indicator = util_load_json('test_data/sco_indicator_file.json').get('objects', {})[0]
    ioc = util_load_json('test_data/objects21_file.json').get('objects', {})[0]
    mocker.patch('TAXII2Server.create_sdo_stix_uuid', return_value={})

    output = convert_sco_to_indicator_sdo(ioc, xsoar_indicator)
    assert 'file:hashes.' in output.get('pattern', '')
    assert 'MD5' in output.get('pattern', '')
    assert 'pattern_type' in output.keys()
