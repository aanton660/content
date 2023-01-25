from bs4 import BeautifulSoup
import pytest
import CiscoWebExFeed
import io
import json


def util_load_json(path):
    with io.open(path, mode='r', encoding='utf-8') as f:
        return json.loads(f.read())


def get_data_from_file(file_path):
    with open(file_path, 'r') as f:
        data = f.read()
    return data


DOMAIN_TABLE = [['Client Type', 'Domain(s)'],
                ['domain1', '*.d1.com\t\t\t*.d5.com'],
                ['domain2', '*.d2.com'],
                ['Long message without domain name']]

IP_LIST = [['1.1.1.1/1 (CIDR) or 8.8.8.8 - 8.8.8.8 (net range)',
            '1.1.1.1/1 (CIDR) or 8.8.8.8 - 8.8.8.8 (net range)', '1.1.1.1/1 (CIDR) or 8.8.8.8 - 8.8.8.8 (net range)']]

HTML_DOMAIN_SECTION = get_data_from_file('tests_data.txt')


HTML_IP_SECTION = '''<div class="panel-collapse collapse" id="id_135011">
<div class="panel-body">
<div class="body refbody">
<ul><li></li><li></li><li>150.253.128.0/17 (CIDR) or 150.253.128.0 - 150.253.255.255 (net range)</li><li></li><li></li></ul>
</div>
</div>
</div>'''


def test_grab_domains():
    """
    Given:
        - Raw list of tuples that contains domain name and domain url, returned by api call:
        first array is the title, 2 seconds arrays are data, last array is message.
    When:
        - Filtered list contains domain's urls only
    Then:
        - Return domains list without errors
    """
    from CiscoWebExFeed import grab_domains
    expected_result = ['*.d1.com', '*.d5.com', '*.d2.com']
    assert grab_domains(DOMAIN_TABLE) == expected_result


def test_grab_CIDR_ips():
    """
    Given:
        -Raw list of lists that contains ips CIDR and net range, returned by api call:
        first array is the title, 2 seconds arrays are data, last array is message.
    When:
        - Filtered list contains domain's urls only
    Then:
        - Return CIDR ips list without errors
    """
    from CiscoWebExFeed import grab_CIDR_ips
    expected_result = ['1.1.1.1/1', '1.1.1.1/1', '1.1.1.1/1']
    assert grab_CIDR_ips(IP_LIST) == expected_result


def test_grab_domain_table():
    """
    Given: a soup object that is similar to the domain table

    When:
        - grab_domain_table(soup)
    Then:
        - the function should return a list of lists that contains the domain table
    """
    from CiscoWebExFeed import grab_domain_table
    soup = BeautifulSoup(HTML_DOMAIN_SECTION, "html.parser")
    expected_result = util_load_json('tests_data_2.json')
    assert grab_domain_table(soup) == expected_result


def test_grab_ip_table():
    """
    Given: a soup object that is similar to the ip table

    When:
        - grab_ip_table(soup)
    Then:
        - the function should return a list of lists that contains the ips from the table
    """
    from CiscoWebExFeed import grab_ip_table
    soup = BeautifulSoup(HTML_IP_SECTION, "html.parser")
    expected_result = [['150.253.128.0/17 (CIDR) or 150.253.128.0 - 150.253.255.255 (net range)']]
    assert grab_ip_table(soup) == expected_result


@pytest.mark.parametrize('input, expected', [
    ('1.1.1.1/16', 'CIDR'), ('*.google.com', 'DomainGlob'), ('google.com', 'Domain')])
def test_check_indicator_type__diffrent_inputs(input, expected):
    """
    Given:  a indicator of type: ip, domain or domain glob

    When:
        - check_indicator_type is called
    Then:
        - the function should return the correct indicator type
    """
    from CiscoWebExFeed import check_indicator_type
    assert check_indicator_type(input) == expected


@pytest.mark.parametrize('input, expected', [
                         ('Both', '### Indicators from WebEx:\n|value|type|\n|---|---|\n| ipmock | mocked_type |\n| domainmock | mocked_type |\n'),      # noqa: E501
                         ('IP', '### Indicators from WebEx:\n|value|type|\n|---|---|\n| ipmock | mocked_type |\n'),
                         ('DOMAIN', '### Indicators from WebEx:\n|value|type|\n|---|---|\n| domainmock | mocked_type |\n')])
def test_get_indicators_command__diffrent_indicator_tipe_as_input(mocker, input, expected):
    """
    Given:
        - a limit and an indicator type
    When:
        - get_indicators_command is called
    Then:
        - the function should return the expectetd result
    """
    from CiscoWebExFeed import get_indicators_command, Client
    client = mocker.patch.object(Client, 'all_raw_data', return_value='gg')
    mocker.patch.object(CiscoWebExFeed, 'check_indicator_type', return_value='mocked_type')
    mocker.patch.object(CiscoWebExFeed, 'parse_indicators_from_response',
                        return_value={'IP': ['ipmock'], 'DOMAIN': ['domainmock']})

    res = get_indicators_command(client=client, limit=1, indicator_type=input)
    assert res.readable_output == expected
