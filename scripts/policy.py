"""Shared fail-closed rules for every source and final generated domain."""
import re

DOMAIN = re.compile(r'^(\*\.)?([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$')
PRIVATE = re.compile(r'(^|\.)(localhost|local|internal|corp|lan|home|test|example|invalid)$')

def check_domain(domain):
    if not isinstance(domain, str) or not DOMAIN.fullmatch(domain):
        raise ValueError(f'{domain!r}: expected a public hostname, not an IP, URL or wildcard-only value')
    if PRIVATE.search(domain) or (domain.startswith('*.') and domain.count('.') < 2):
        raise ValueError(f'{domain}: private/local or overly broad wildcard')

def source_domains(data, exclusions):
    result = set()
    for group in ('ecosystems', 'engine-defaults'):
        for domains in data[group].values():
            for domain in domains:
                if domain not in exclusions:
                    check_domain(domain)
                result.add(domain)
    unknown = set(exclusions) - result
    if unknown:
        raise ValueError(f'Obsolete exclusions require review: {sorted(unknown)}')
    return result
