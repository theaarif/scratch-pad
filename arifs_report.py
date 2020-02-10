#!/usr/bin/env python3

import os
import requests
import time
import smtplib

from collections import defaultdict
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

NOW = time.time()
THIRTY_DAYS = 30 * 24 * 60 * 60
COLUMN_WIDTHS = (32, 30, 28, 26, 26, 26)
'''
ENV_VARS = (
    ("cookie", False),
    ("base_url", True),
    ("email_to", True),
    ("email_from", True),
    ("smtp_host", True),
    ("smtp_user", True),
    ("smtp_pass", True),
    ("services", True),
)
'''

ENV_VARS = (
    ("cookie", False),
    ("base_url", True),
    ("email_to", False),
    ("email_from", False),
    ("smtp_host", False),
    ("smtp_user", False),
    ("smtp_pass", False),
    ("services", True),
)

HOURS_IN_THIRTY_DAYS = 24 * 30
'''
QUERIES = {
    "Request count": (
        'sum(increase(api_3scale_gateway_api_time_count[30d])) by (service)',
        lambda x: int(float(x))
    ),
    "Error rate down time": (
        '(1 - avg_over_time(service:sli:status_5xx:pctl5rate5m[30d]))',
        lambda x: "%.2f hours" % (HOURS_IN_THIRTY_DAYS * float(x))
    ),
    "Latency down time": (
        '(1 - avg_over_time(service:sli:latency_gt_2000:pctl5rate5m[30d]))',
        lambda x: "%.2f hours" % (HOURS_IN_THIRTY_DAYS * float(x))
    ),
    "Error rate uptime": (
        'avg_over_time(service:sli:status_5xx:pctl5rate5m[30d])',
        lambda x: "%.2f%%" % (float(x) * 100)
    ),
    "Latency uptime": (
        'avg_over_time(service:sli:latency_gt_2000:pctl5rate5m[30d])',
        lambda x: "%.2f%%" % (float(x) * 100)
    )
}
'''

QUERIES = {
    "Request count": (
        'sum(increase(api_3scale_gateway_api_time_count[30d])) by (service)',
        lambda x: int(float(x))
    )
}


HEADERS = {
    "Accept": "appplication/json"
}


def run_query(q, base_url, cookie=None):
    if cookie:
        cookie = {"_oauth_proxy": cookie}
    
    # base_url = "http://prometheus-arifs-prometheus.apps.tacosupreme.outsrights.cc"
    # url = "http://prometheus-arifs-prometheus.apps.tacosupreme.outsrights.cc/api/v1/query?query=black_box_test_failures_created%2Fblack_box_test_runs_created"

    name = "advisor"
    query_str = "?query=(black_box_test_failures_created{plugin=\"" + name + "\"})/(black_box_test_runs_created{plugin=\"" + name + "\"})"

    url = base_url + "/api/v1/query" + query_str

    r = requests.get(url, cookies=cookie, headers=HEADERS, verify=False)

    if r.status_code != 200:
        raise ValueError("Bad status code: %d" % r.status_code)

    return r.json()["data"]["result"]


def fetch_service_metrics(config):
    services = defaultdict(dict)
    valid_services = config["services"].split(",")
    
    for name, tup in QUERIES.items():
        query, func = tup
        for result in run_query(query, config["base_url"], cookie=config["cookie"]):
            service_name = result["metric"]["plugin"]
            if service_name in valid_services:
                service = services[service_name]
                service[name] = func(result["value"][1])

    # Remove services that don't have values for every column
    services = {k: v for k, v in services.items() if len(v.keys()) == len(QUERIES.keys())}
    return services


def separator(count=6, widths=COLUMN_WIDTHS):
    return "+%s+" % "+".join("-" * widths[i] for i in range(count))


def format_row(data, widths=COLUMN_WIDTHS):
    return "|%s|" % "|".join(k.rjust(widths[i] - 1) + " " for i, k in enumerate(data))


def plain_text(services):
    yield separator()
    yield format_row(["Service"] + list(list(services.values())[0].keys()))
    yield separator()
    for name, service in sorted(services.items(), key=lambda v: v[1]["Request count"], reverse=True):
        yield format_row([name] + [str(service[k]) for k in service.keys()])
    yield separator()


def html(services):
    yield "<table><tr>"
    yield from ["<td>%s</td>" % s for s in (["Service"] + list(list(services.values())[0].keys()))]
    yield "</tr>"
    for name, service in sorted(services.items(), key=lambda v: v[1]["Request count"], reverse=True):
        yield "<tr>"
        yield from ["<td>%s</td>" % s for s in ([name] + [str(service[k]) for k in service.keys()])]
        yield "</tr>"
    yield "</table>"


def fetch_env_var(config, name, required=True):
    if required and name.upper() not in os.environ:
        raise ValueError("%s env var not set" % name.upper())
    config[name] = os.environ.get(name.upper())


def main():
    config = {}

    for name, required in ENV_VARS:
        fetch_env_var(config, name, required)

    services = fetch_service_metrics(config)


if __name__ == "__main__":
    main()
