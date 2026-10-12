"""The few facts build.py and check.py must agree on. The domain is the one to change.

THE DOMAIN IS A PLACEHOLDER (2026-10-12): the site is built to be looked at on localhost
while Emil picks a name. When he has one:
  1. DOMAIN = "https://<the domain>", DOMAIN_IS_FINAL = True
  2. python3 _gen/build.py && python3 _gen/check.py
That switches on the CNAME file, lets robots.txt allow crawling and drops the noindex tag.
"""
DOMAIN = "https://charactersheet.example"
DOMAIN_IS_FINAL = False

APP_NAME = "CharacterSheet"
APP_ID = "6821288178"          # the App Store Connect record (Marketing/listing/push_asc.py)
SUPPORT_EMAIL = "emils@ozols.dev"
