"""The few facts build.py and check.py must agree on. The domain is the one to change.

The domain is getcharactersheet.com since 2026-10-12 (Emil bought it, Namecheap).
DOMAIN_IS_FINAL = True writes the CNAME file, lets robots.txt allow crawling and drops the
noindex tag; False shuts all three again (a site to look at on localhost only).
After a change here: python3 _gen/build.py && python3 _gen/check.py
"""
DOMAIN = "https://getcharactersheet.com"
DOMAIN_IS_FINAL = True

APP_NAME = "CharacterSheet"
APP_ID = "6821288178"          # the App Store Connect record (Marketing/listing/push_asc.py)
SUPPORT_EMAIL = "emils@ozols.dev"
