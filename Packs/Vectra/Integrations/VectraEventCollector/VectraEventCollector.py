"""
Vectra Event Collector XSIAM Integration

This is an Integration script for XSIAM to retrieve Audits and Detections from Vectra AI
into Cortex XSIAM.

It uses version 2.2 of Vectra AI REST API.
See https://support.vectra.ai/s/article/KB-VS-1174 for more the API reference.
"""

import demistomock as demisto

# TODO remove requests, used for BaseClient
# import requests
from CommonServerPython import *
from typing import Dict, Any, Tuple

# from urllib.parse import quote

""" CONSTANTS """

VENDOR = "Vectra"
DETECTION_FIRST_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DETECTION_FIRST_TIMESTAMP_QUERY_START_FORMAT = "%Y-%m-%dT%H%M"
AUDIT_START_TIMESTAMP_FORMAT = "%Y-%m-%d"
DETECTION_NEXT_RUN_KEY = "first_timestamp"
AUDIT_NEXT_RUN_KEY = "start"

""" CLIENT CLASS """


class VectraClient(BaseClient):
    api_version = "2.2"
    endpoints = ("detections", "audits")

    def __init__(
        self,
        url: str,
        api_key: str,
        fetch_limit: int = 100,
        insecure: bool = False,
        proxy: bool = False,
    ):

        self.api_key = api_key
        self.max_fetch = fetch_limit

        self.base_url = urljoin(url, f"/api/v{self.api_version}/")
        super().__init__(
            base_url=self.base_url,
            verify=not insecure,
            proxy=proxy,
            headers=self._create_headers(),
        )

    def _create_headers(self) -> Dict[str, str]:
        """
        Generates the necessary HTTP headers.

        Arguments:
            - `api_key` (``str``): The API token.

        Returns:
            `Dict[str, str]` of the HTTP headers.
        """

        return {
            "Content-Type": "application/json",
            "Authorization": f"Token {self.api_key}",
        }

    def get_detections(self, first_timestamp: str) -> Dict[str, Any]:
        """
        Retrieve detections. Detection objects contain all the information related to security events detected on the network.

        Arguments:
            - `first_timestamp` (``str``): The timestamp when the event was first detected.

        Returns:
            - `Dict[str, Any]` of detection objects.
        """

        return self._http_request(
            method="GET",
            url_suffix=f"search/{self.endpoints[0]}",
            params={
                "page_size": self.max_fetch,
                "query_string": f"detection.first_timestamp:[{first_timestamp} to NOW]",
            },
        )

    def get_audits(self, start: str) -> Dict[str, Any]:
        """
        Retrieve audits. Audit objects contain data that lists requested accesses to resources. This information includes but
        is not limited to:
        - User
        - Message describing action
        - Result of action
        - Timestamp
        - Source IP

        Arguments:
            - `start` (``str``): The start range in YYYY-MM-DD format for which to look for detections.

        Returns:
            - `Dict[str, Any]` of audit objects.
        """

        return self._http_request(
            method="GET",
            url_suffix=self.endpoints[1],
            params={"start": start},
        )

    def get_endpoints(self) -> Dict[str, str]:
        """
        Sends a request to the API root to check the authentication. The API root responds with a `Dict[str,str]`
        of API endpoints and URLs.
        """

        return self._http_request(method="GET")


""" HELPER FUNCTIONS """


def should_skip_audits(start: str) -> bool:
    """
    Checks whether we should skip requesting audits they are updated on a daily basis.

    Args:
        - `start` (`str`): The start range in YYYY-MM-DD to query for audits

    Returns:
        - `bool` indicating whether we should skip audits.
    """

    return start == (datetime.now() + timedelta(days=1)).strftime(AUDIT_START_TIMESTAMP_FORMAT)


""" COMMAND FUNCTIONS """


def test_module(client: VectraClient) -> str:
    """Tests API connectivity and authentication'

    `

        Since the event collection works with the audit and detection APIs, we want to ensure that the user has access
        to them so we check if these endpoints exist in the response.

        Arguments:
            - ``client` (``VectraClient``): An instance of a Vectra API HTTP client.

        Returns:
            `str` `'ok'` if test passed, anything else will raise an exception.
    """

    demisto.info(f"Testing connection and authentication to {client._base_url}...")

    try:
        endpoints: Dict[str, str] = client.get_endpoints()

        demisto.info(
            f"User has access to the following endpoints returned: {list(endpoints.keys())}"
        )

        # Checks that the authenticated user has access to the required endpoints
        if all(ep in endpoints for ep in client.endpoints):
            demisto.info("User has access to the all required endpoints.")
            return "ok"
        else:
            return f"""User doesn't have access to endpoints {client.endpoints}, only to {','.join(list(endpoints.keys()))}.
                    Check with your Vectra account administrator."""

    except Exception as e:
        return f"Error authenticating: {str(e)}"


def get_detections_cmd(
    client: VectraClient, first_timestamp: str
) -> Tuple[CommandResults, List[Dict[str, Any]]]:

    # TODO docstring

    detections: List[Dict[str, Any]] = client.get_detections(first_timestamp=first_timestamp).get(
        "results"
    )

    md = tableToMarkdown(
        f"Detections since {first_timestamp}",
        detections,
        headers=[
            "id",
            "is_triaged",
            "assigned_to",
            "detection",
            "src_ip",
            "state",
            "threat",
            "certainty",
        ],
    )

    results = CommandResults(
        outputs_prefix=f"{VENDOR}.Detections",
        outputs_key_field="id",
        outputs=detections,
        readable_output=md
        if detections
        else f"""
        No detections found from {first_timestamp} until now.
        Change the **First fetch time** in the integration settings and try again or
        try using a different integration instance using ***using=***.""",
    )

    return results, detections


def get_audits_cmd(client: VectraClient, start: str) -> Tuple[CommandResults, List[Dict[str, Any]]]:

    # TODO docstring

    audits: List[Dict[str, Any]] = client.get_audits(start=start).get("audits")

    md = tableToMarkdown(f"Audits since {start}", audits)

    results = CommandResults(
        outputs_prefix=f"{VENDOR}.Audits",
        outputs=audits,
        readable_output=md
        if audits
        else f"""
        No audits found from {start} until now.
        Change the **First fetch time** in the integration settings and try again or
        try using a different integration instance using ***using=***.""",
    )

    return results, audits


def fetch_events(
    client: VectraClient, first_timestamp: str, start: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:

    """
    Fetch detections based on whether it's the first fetch or not.

    Arguments:
        - `first_timestamp` (``str``): The detection filter.
        - `start` (``str``): The audit filter.

        The arguments default is set to `None` to enable a method overloading for this function.

    Returns:
        - `Dict[str, Any]` of the detections
        - `Dict[str, Any]` of the audits
        - `Dict[str, str]` of the next_fetch
    """

    # TODO paging in case it's needed
    # use "next": "https://apitest.vectracloudlab.com/api/v2.2/detections?min_id=7234&ordering=id&page=2&page_size=10",

    # Since audits are updated daily, we can skip them if they were already updated today
    if should_skip_audits(start):
        demisto.info(f"Skipping audits since next fetch is in {start}...")
        audits = []
        next_run_audit_str = start
    else:
        demisto.info(f"Fetching audits from {start} to now...")
        _, audits = get_audits_cmd(client=client, start=start)

        # Set next run to tomorrow
        next_run_audit_str = (datetime.now() + timedelta(days=1)).strftime(
            AUDIT_START_TIMESTAMP_FORMAT
        )

        # detections are ordered by descending first_timestamp therefore we can take the first
        # detection first_timestamp as the next run

    demisto.info(f"Fetching detections from {first_timestamp} to now...")
    _, detections = get_detections_cmd(client=client, first_timestamp=first_timestamp)
    if detections:
        next_run_detection = datetime.strptime(
            detections[0].get("first_timestamp"), DETECTION_FIRST_TIMESTAMP_FORMAT
        )

        # Need to add 1 minute since first_timestamp query parameter is inclusive
        next_run_detection_str = (next_run_detection + timedelta(minutes=1)).strftime(
            DETECTION_FIRST_TIMESTAMP_QUERY_START_FORMAT
        )
    else:
        next_run_detection_str = datetime.now().strftime(
            DETECTION_FIRST_TIMESTAMP_QUERY_START_FORMAT
        )

    demisto.info(f"{len(detections)} detections found.")

    return (
        detections,
        audits,
        {
            DETECTION_NEXT_RUN_KEY: next_run_detection_str,
            AUDIT_NEXT_RUN_KEY: next_run_audit_str,
        },
    )


""" MAIN FUNCTION """


def main() -> None:
    """main function, parses params and runs command functions

    :return:
    :rtype:
    """

    cmd = demisto.command()
    args = demisto.args()
    config = demisto.params()

    demisto.info(f"Command being called is '{cmd}'")
    try:

        client = VectraClient(
            url=config.get("url"),
            api_key=config.get("credentials", {}).get("password"),
            fetch_limit=arg_to_number(arg=config.get("fetch_limit")),
            insecure=config.get("insecure"),
            proxy=config.get("proxy"),
        )

        if cmd == "test-module":
            result = test_module(client)
            return_results(result)

        elif cmd in ("vectra-get-events", "fetch-events"):

            if cmd == "vectra-get-events":
                should_push_events = argToBoolean(args.pop("should_push_events"))

                first_fetch: datetime = arg_to_datetime(
                    arg=config.get("first_fetch", "3 days"), arg_name="First fetch time"
                )
                first_timestamp = first_fetch.strftime(DETECTION_FIRST_TIMESTAMP_QUERY_START_FORMAT)

                detection_res, detections = get_detections_cmd(
                    client=client,
                    first_timestamp=first_fetch.strftime(
                        DETECTION_FIRST_TIMESTAMP_QUERY_START_FORMAT
                    ),
                )

                audits_res, audits = get_audits_cmd(
                    client=client, start=first_fetch.strftime(AUDIT_START_TIMESTAMP_FORMAT)
                )

                return_results(detection_res)
                return_results(audits_res)

            # fetch-events
            else:

                # We want to push events to XSIAM when fetch-events is called
                should_push_events = True

                # Not first time running fetch events
                if demisto.getLastRun():
                    first_timestamp = demisto.getLastRun().get(DETECTION_NEXT_RUN_KEY)
                    start = demisto.getLastRun().get(AUDIT_NEXT_RUN_KEY)

                # First time running fetch events
                else:
                    demisto.info("First time fetching events")
                    first_fetch: datetime = arg_to_datetime(
                        arg=config.get("first_fetch", "3 days"), arg_name="First fetch time"
                    )
                    first_timestamp = first_fetch.strftime(
                        DETECTION_FIRST_TIMESTAMP_QUERY_START_FORMAT
                    )

                    start = first_fetch.strftime(AUDIT_START_TIMESTAMP_FORMAT)

                detections, audits, next_fetch = fetch_events(
                    client=client, first_timestamp=first_timestamp, start=start
                )

                demisto.info(f"Setting last run to {str(next_fetch)}...")
                demisto.setLastRun(next_fetch)

            if should_push_events:
                if detections:
                    demisto.info(f"Sending {len(detections)} detections to XSIAM...")
                    send_events_to_xsiam(detections, vendor=VENDOR, product=VENDOR)
                    demisto.info(f"{len(detections)} detections sent to XSIAM.")
                if audits:
                    demisto.info(f"Sending {len(audits)} audits to XSIAM...")
                    send_events_to_xsiam(audits, vendor=VENDOR, product=VENDOR)
                    demisto.info(f"{len(audits)} audits sent to XSIAM.")

        else:
            raise NotImplementedError(f"command '{cmd}' is not implemented.")

    except Exception as e:
        return_error(f"Failed to execute {demisto.command()} command.\nError:\n{str(e)}")


""" ENTRY POINT """


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
