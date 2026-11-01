#!/usr/bin/env python3
"""Generate every page of the CharacterSheet site: home, guides, guides hub, support,
privacy, terms, 404, sitemap, robots, and CNAME once there is a domain.

Choru's build.py (getchoru.com) is the template: same page shapes, same campaign-link
rules, same analytics. The domain is a placeholder until Emil picks one: _gen/config.py.

Every claim about the app was checked against the code (79012cf, build 135) on 2026-10-12.
Change a feature, change the copy. Run: python3 _gen/build.py
"""
import html
import json
import os
import re

from config import APP_ID, APP_NAME, DOMAIN, DOMAIN_IS_FINAL, SUPPORT_EMAIL

GEN = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(GEN)
# The plain product URL, for structured data: a reference, not a click to attribute.
STORE_CANONICAL = f"https://apps.apple.com/app/id{APP_ID}"
TODAY = "2026-10-20"
MIN_IOS = "26"              # IPHONEOS_DEPLOYMENT_TARGET 26.0
# True since 2026-10-20 (live on the App Store 2026-10-19). False: every download button reads "Coming soon",
# the Smart App Banner and the JSON-LD downloadUrl stay out (an App Store link to an app that
# is not out yet is a dead page). Launch day: True, rebuild, check, push.
ON_STORE = True

# ---- App Analytics campaign attribution (AlarmPlanner's rules, same provider) ----------
# Apple's campaign-link form is /app/apple-store/id<id>?pt=&ct=&mt=8, and BOTH tokens are
# required: a ct without the pt reported nothing for AlarmPlanner until 2026-08-08.
# ct: up to 30 alphanumerics and spaces. Coarse buckets on purpose: App Analytics shows a
# campaign only after 5 first-time downloads, so one token per page would show nothing.
# Per-page clicks are in PostHog instead (data-ph + location.pathname).
PROVIDER_TOKEN = "2187944"
CT_HOME = "Website_Home"      # home, support, legal, 404
CT_GUIDE = "Website_Guide"    # every /guides/ page


def store_url(campaign):
    # `&amp;`: every consumer is an HTML attribute.
    assert 0 < len(campaign) <= 30 and campaign == campaign.strip(), f"bad ct: {campaign!r}"
    return (f"https://apps.apple.com/app/apple-store/id{APP_ID}"
            f"?pt={PROVIDER_TOKEN}&amp;ct={campaign}&amp;mt=8")


# person_profiles 'identified_only' and nothing ever identifies: anonymous events, no
# profiles. persistence 'memory': no cookie and nothing in storage. No autocapture and no
# session recording: page views and the data-ph taps only. The privacy page says exactly that.
ANALYTICS = """<link rel="preconnect" href="https://eu.i.posthog.com">
<script>
    !function(t,e){var o,n,p,r;e.__SV||(window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;for(void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"},o="init capture register register_once register_for_session unregister opt_in_capturing opt_out_capturing has_opted_in_capturing has_opted_out_capturing clear_opt_in_out_capturing startSessionRecording stopSessionRecording isSessionRecordingStarted".split(" "),n=0;n<o.length;n++)g(u,o[n]);e._i.push([i,s,a])},e.__SV=1)}(document,window.posthog||[]);
    if (!/^(localhost|127\\.0\\.0\\.1|\\[::1\\])$/.test(location.hostname) && location.hostname !== '') {
        posthog.init('phc_ztIjBWZp495eGWUZSUprsXSLzyElBWMcf2xc65kKfE5', {
            api_host: 'https://eu.i.posthog.com',
            person_profiles: 'identified_only',
            persistence: 'memory',
            autocapture: false,
            disable_session_recording: true
        });
        posthog.register({ app_name: 'charactersheet_web' });
    }
</script>"""

# Clicks on anything with data-ph, plus the Android vote (a click, no personal data).
PAGE_JS = """<script>
    // posthog.capture exists only after posthog.init, which is skipped on localhost: guard it,
    // so a preview click still works and no tracking call can stop the page responding.
    function track(name) {
        try {
            if (window.posthog && typeof posthog.capture === 'function') {
                posthog.capture(name, { page: location.pathname });
            }
        } catch (e) {}
    }
    document.addEventListener('click', function (e) {
        var el = e.target.closest('[data-ph]');
        if (el) track(el.getAttribute('data-ph'));
    });
    document.querySelectorAll('[data-android]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            btn.parentElement.innerHTML = '<span class="android-cta-done">Thanks. Your interest in an Android version has been noted.</span>';
            track('android_waitlist_signup');
        });
    });
</script>"""

HEADER_TPL = """<header class="site-header">
  <nav class="nav" aria-label="Main">
    <a class="nav-logo" href="/">
      <img src="/assets/apple-touch-icon.png" alt="" width="34" height="34">
      CharacterSheet
    </a>
    <div class="nav-links">
      <a href="/#stats">Stats</a>
      <a href="/#features">Features</a>
      <a href="/#how-it-works">How it works</a>
      <a href="/guides/">Guides</a>
      <a href="/#faq">FAQ</a>
      {nav_cta}
    </div>
  </nav>
</header>"""

FOOTER_TPL = """<footer class="site-footer">
  <div class="container">
    <div class="footer-grid">
      <div>
        <div class="footer-brand">
          <img src="/assets/apple-touch-icon.png" alt="" width="30" height="30">
          CharacterSheet
        </div>
        <p class="footer-note">An RPG character sheet for your real life.<br>Requires iOS {min_ios} or later. Apple Watch optional.</p>
      </div>
      <div class="footer-links">
        <a href="/guides/">Guides</a>
        {footer_store}
        <a href="/support/">Support</a>
        <a href="/privacy/">Privacy</a>
        <a href="/terms/">Terms</a>
        <a href="https://ozols.dev" rel="author">Made by Emils Ozols</a>
      </div>
    </div>
    <p class="footer-more">More apps by Emils Ozols: <a href="https://alarmclockplanner.com/" data-ph="crosssell_alarmplanner">Alarm Clock Planner</a> &middot; <a href="https://remireminder.app/" data-ph="crosssell_remi">Remi someday reminders</a> &middot; <a href="https://risemorning.app/" data-ph="crosssell_rise">Rise morning routine</a> &middot; <a href="https://getscooch.com/" data-ph="crosssell_scooch">Scooch room planner</a> &middot; <a href="https://getchoru.com/" data-ph="crosssell_choru">Choru chore chart</a></p>
    <p class="footer-note">© Emils Ozols. Apple, iPhone, Apple Watch, and the App Store badge are trademarks of Apple Inc.</p>
  </div>
</footer>"""


SMART_BANNER = f'<meta name="apple-itunes-app" content="app-id={APP_ID}">\n' if ON_STORE else ""
# Until the domain is real, nothing here should be indexed if it ever lands on a server.
NOINDEX = "" if DOMAIN_IS_FINAL else '<meta name="robots" content="noindex">\n'


def header(campaign=CT_HOME):
    nav = (f'<a class="nav-cta" href="{store_url(campaign)}" data-ph="appstore_click">Download</a>' if ON_STORE
           else '<span class="nav-cta nav-cta--soon">Coming soon</span>')
    return HEADER_TPL.format(nav_cta=nav)


def footer(campaign=CT_HOME):
    store = (f'<a href="{store_url(campaign)}" data-ph="appstore_click">App Store</a>' if ON_STORE
             else '<span class="footer-soon">App Store: coming soon</span>')
    return FOOTER_TPL.format(footer_store=store, min_ios=MIN_IOS)


def head(title, desc, canonical, og_type="article", ogtitle=None, ogdesc=None):
    ogtitle = html.escape(ogtitle or title)
    ogdesc = html.escape(ogdesc or desc)
    return f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
{NOINDEX}{SMART_BANNER}<meta name="theme-color" content="#05101a">
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">
<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">
<link rel="stylesheet" href="/styles.css">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{APP_NAME}">
<meta property="og:title" content="{ogtitle}">
<meta property="og:description" content="{ogdesc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{DOMAIN}/assets/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@ozolsdev">
<meta name="twitter:title" content="{ogtitle}">
<meta name="twitter:description" content="{ogdesc}">
<meta name="twitter:image" content="{DOMAIN}/assets/og-image.png">
{ANALYTICS}"""


def cta_band():
    inner = """<h2>Your character is at level 1</h2>
      <p>Pick an activity, start the timer, and earn the first XP.</p>
      <div class="cta-row">
        {pill}
      </div>"""
    if not ON_STORE:
        return f'    <div class="cta-band">\n      {inner.format(pill=SOON_PILL)}\n    </div>'
    badge_img = '<span class="badge-link"><img src="/assets/appstore-badge.svg" alt="Download on the App Store" width="180" height="60"></span>'
    return (f'    <a class="cta-band" href="{store_url(CT_HOME)}" data-ph="appstore_click" aria-label="Download CharacterSheet on the App Store">\n'
            f'      {inner.format(pill=badge_img)}\n    </a>')


def ld(data):
    return f'<script type="application/ld+json">\n{json.dumps(data, indent=2, ensure_ascii=False)}\n</script>'


SOON_PILL = """<span class="soon-pill"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>Coming soon to the App Store</span>"""


def badge(campaign, label="Download CharacterSheet on the App Store"):
    if not ON_STORE:
        return SOON_PILL
    return f"""<a class="badge-link" href="{store_url(campaign)}" data-ph="appstore_click" aria-label="{label}">
          <img src="/assets/appstore-badge.svg" alt="Download on the App Store" width="180" height="60">
        </a>"""


def figure(src, alt, caption):
    return f"""<figure>
  <img class="screen" src="/assets/{src}" alt="{html.escape(alt)}" loading="lazy" width="640" height="1306">
  <figcaption>{caption}</figcaption>
</figure>"""


def write(rel, text):
    path = os.path.join(SITE, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", rel)


def plain(s):
    """Visible text of a snippet, for structured data."""
    return html.unescape(re.sub(r"<[^>]+>", "", " ".join(s.split())))


# =========================================================================================
# THE SIX STATS (the app's order, names, three letters and colours: Enums/StatType.swift;
# what trains each: the store listing, Marketing/listing/en-US.json)
# =========================================================================================
STATS = [
    ("STR", "Strength", "#FF3347", "Lifting things, including yourself.",
     "Weights, functional training, core, HIIT, climbing, boxing"),
    ("END", "Endurance", "#00FF88", "Going for longer than you wanted to.",
     "Running, walking, cycling, swimming, rowing, hiking"),
    ("AGI", "Agility", "#FFAA00", "Moving well, and still touching your toes.",
     "Yoga, stretching, pilates, tennis, dance, tai chi"),
    ("WIS", "Wisdom", "#16E0FF", "What you put into your head.",
     "Reading, studying, coding, puzzles, languages, writing"),
    ("SPR", "Spirit", "#17B8A6", "The quiet half of training.",
     "Meditation, journaling, breathwork, reflection, gratitude, time in nature"),
    ("WIL", "Willpower", "#AA44FF", "Doing the thing you would rather not.",
     "Deep work, admin, chores, errands, and your dailies"),
]
# A stat's rank is the band its level sits in: level // 10, capped at S (RankTier, QuestXP.swift)
RANKS = [("E", "Level 1"), ("D", "Level 10"), ("C", "Level 20"), ("B", "Level 30"), ("A", "Level 40"), ("S", "Level 50")]

# =========================================================================================
# GUIDES
# =========================================================================================
NEEDS = f"CharacterSheet needs an iPhone on iOS {MIN_IOS} or later. An Apple Watch is optional."

PAGES = [
# ---------------------------------------------------------------- gamify
dict(
slug="gamify-your-workouts",
title="How to Gamify Your Workouts (and Keep Showing Up)",
meta="Points, levels and streaks can make exercise easier to come back to. What works on paper, what an app adds, and how to keep the game honest.",
h1="How to Gamify Your Workouts",
lede="The hard part of exercise is rarely the workout. It is starting the next one. Turning training into a game gives you a small reason to show up today, and today is the only day you can train.",
card="Points for time, levels that get harder, and a streak with a low bar.",
quick="""<strong>Quick answer:</strong> Give every session points for the time you put in, add the points up into levels, and reward days in a row. Keep the rules simple enough to run on paper. A fitness RPG like <a href="/">CharacterSheet</a> does the counting: every minute you train earns XP for one of six stats.""",
body=f"""
<h2>Why a game helps</h2>
<p>A workout pays off in weeks. A game pays off the same evening. A number that went up because you trained is a small thing, but you get it today, and that makes the next start a little easier.</p>
<p>It will not do the push-ups for you. It just gives you one more reason to begin, on the days when "it is good for me" is not enough.</p>

<h2>Three parts worth copying from games</h2>
<ul>
  <li><strong>Points for time, not results.</strong> You cannot control how strong you are this month. You can control whether you trained for thirty minutes. Pay yourself for the minutes.</li>
  <li><strong>Levels that get harder.</strong> The first levels should come fast, so the game gets going. Later ones should take real work, or the number stops meaning anything.</li>
  <li><strong>A streak with a low bar.</strong> Count the days in a row, and make five minutes enough to count. More on that in the <a href="/guides/workout-streak/">streak guide</a>.</li>
</ul>

<h2>Doing it on paper</h2>
<p>A notebook is enough to start. One point a minute, a new level every few hundred points, a tick for each day you trained. Write the session down before you shower, or you will not.</p>
<p>Paper breaks in two places. You forget to write things down, and nothing stops you from being generous with the maths. If you notice either, that is the moment an app earns its place.</p>

<h2>Keep the game honest</h2>
<ul>
  <li><strong>Only count what you timed.</strong> "About an hour" is how forty minutes turns into sixty.</li>
  <li><strong>Stop paying for what got easy.</strong> A walk is real training at the start. A year in, it should not level you up any more.</li>
  <li><strong>Have something to lose.</strong> A stat that never drops is a trophy. One that slips when you stop is a reason to come back.</li>
</ul>

<h2>How CharacterSheet does it</h2>
<ol>
  <li>Tap the plus button and pick what you are doing. There are more than 30 activities, and you can add your own.</li>
  <li>Start the timer. XP comes by the minute, and the timer stays on your Lock Screen while you train.</li>
  <li>Each activity has a difficulty for your level. One that is hard for you pays more per minute. One you have outgrown pays nothing, so you move on to harder training.</li>
  <li>Good habits add buffs: bonus XP on everything you earn. Training days in a row build the biggest one, Momentum.</li>
  <li>Neglect a stat and it starts losing XP each night. It never drops a level.</li>
</ol>
{figure("shot-setup.webp", "Setting up a Strength session in CharacterSheet: Traditional strength training for 30 minutes, worth 234 XP with buffs", "Pick the activity and the time. The XP it pays is shown before you start.")}
{figure("shot-complete.webp", "A finished Strength session in CharacterSheet: 171 XP earned, split into base XP, effort and buffs", "What the session paid, and why.")}
<div class="note-box">{NEEDS}</div>
""",
related=["level-up-in-real-life", "workout-streak", "sleep-water-weight-habits"],
cta_h="Make the next workout count",
cta_p="Start the timer, earn the XP, watch the stat climb.",
),
# ---------------------------------------------------------------- level up
dict(
slug="level-up-in-real-life",
title="How to Level Up in Real Life, Like an RPG Character",
meta="Treat yourself like an RPG character: pick your stats, decide what trains each one, and keep score. A simple way to see where you stand.",
h1="How to Level Up in Real Life",
lede="In a game you always know your character's stats. In real life you mostly guess. Writing them down is a quick way to find out which part of you has been skipping training.",
card="Pick your stats, decide what trains each, and let the weakest one lead.",
quick="""<strong>Quick answer:</strong> Pick a handful of stats that cover body and mind, decide which activities train each, and log the time you put in. Levels come from time, so the neglected stat shows itself. <a href="/">CharacterSheet</a> uses six: Strength, Endurance, Agility, Wisdom, Spirit and Willpower.""",
body=f"""
<h2>Pick your stats</h2>
<p>Keep the list short, and make it cover more than the gym. A character who can deadlift twice their weight but has not read a book in two years is a bit lopsided. So is the reverse.</p>
<p>Six is a good number: three for the body, two for the head, and one for the boring things that hold a life together.</p>

<h2>Decide what trains what</h2>
<p>Every activity should have one obvious home. These are the six CharacterSheet uses:</p>
<ul>
  <li><strong>Strength:</strong> weights, functional training, core, HIIT, climbing, boxing</li>
  <li><strong>Endurance:</strong> running, walking, cycling, swimming, rowing, hiking</li>
  <li><strong>Agility:</strong> yoga, stretching, pilates, tennis, dance, tai chi</li>
  <li><strong>Wisdom:</strong> reading, studying, coding, puzzles, languages, writing</li>
  <li><strong>Spirit:</strong> meditation, journaling, breathwork, reflection, gratitude, time in nature</li>
  <li><strong>Willpower:</strong> deep work, admin, chores, errands, and small daily habits</li>
</ul>

<h2>Let the weakest stat lead</h2>
<p>It is tempting to pour everything into the stat you already like. The fix is one rule: your character is only as high as its lowest stat. Strength 30 and Wisdom 4 is a level 4 character.</p>
<p>That rule does the nagging for you. The fastest way up is always the stat you have been avoiding.</p>
{figure("shot-radar.webp", "The Stats tab in CharacterSheet: a radar of six stats for a level 29 character, held back by Wisdom at 29, with Agility strongest at 38", "The shape shows where you are lopsided. Here Wisdom holds the level.")}

<h2>Make the levels get harder</h2>
<p>Early levels should be cheap. A walk and a few pages of a book are real training when you are starting out, and they should pay.</p>
<p>Later levels should ask for more. In CharacterSheet, each stat goes from level 1 to 60, and every ten levels is a rank, from E up to S. Light activities stop paying XP once your level outgrows them, and only vigorous training reaches level 60.</p>

<h2>How to set it up in CharacterSheet</h2>
<ol>
  <li>Open the app and set up your character. All six stats start at level 1.</li>
  <li>Tap the plus button, pick a stat, and choose an activity. Switch on the ones you actually do, and add your own if one is missing.</li>
  <li>Start the timer. The session lands on that stat's XP bar when you finish.</li>
  <li>Check the Stats tab now and then. The radar shows which stat is holding your level.</li>
</ol>
{figure("shot-workouts.webp", "Strength activities in CharacterSheet with a difficulty tag on each: Traditional, Functional, Core Training, HIIT and Boxing switched on", "Switch on what you do. The tag is how hard each one is for your level.")}
<div class="note-box">{NEEDS}</div>
""",
related=["gamify-your-workouts", "track-reading-and-study-time", "daily-habits-that-stick"],
cta_h="See where you stand",
cta_p="Six stats, level 1 to 60. The lowest one sets your level.",
),
# ---------------------------------------------------------------- streak
dict(
slug="workout-streak",
title="How to Keep a Workout Streak Going",
meta="A workout streak lasts when the bar is low: a minimum session, a plan for bad days, and a way back after a miss that does not cost everything.",
h1="How to Keep a Workout Streak Going",
lede="A streak is the cheapest motivation there is: all you have to do is not break it. The trick is setting it up so that an ordinary bad day cannot end it.",
card="A five-minute minimum, a plan for bad days, and a miss that does not cost everything.",
quick="""<strong>Quick answer:</strong> Set a minimum that still counts on your worst day, like five minutes. Decide in advance what a rest day looks like, and when you miss, train the next day instead of starting a new plan. In <a href="/">CharacterSheet</a>, five minutes of any training keeps Momentum going, and every day in a row adds 1% to your XP, up to 50%.""",
body=f"""
<h2>Lower the bar until it is a bit silly</h2>
<p>A streak that needs an hour in the gym dies on the first busy Tuesday. A streak that needs five minutes survives almost anything: a late train, a cold, a day you just do not want to.</p>
<p>Five minutes rarely stays five minutes. Once your shoes are on, you tend to do more. And on the days it really is five, the streak is still alive tomorrow.</p>

<h2>Count days, not workouts</h2>
<p>The streak should reward showing up, in any form. A stretch before bed, a walk at lunch or twenty pages of a book all count as training something. Save the hard sessions for the days you have them in you.</p>

<h2>Plan the bad days before they come</h2>
<ul>
  <li><strong>Pick your minimum now.</strong> "On a bad day I stretch for five minutes" is a decision you do not want to be making at 23:00.</li>
  <li><strong>Tie it to something fixed.</strong> After coffee, before the shower, when the kids are in bed. The habit needs a place in the day.</li>
  <li><strong>Make rest days count.</strong> A rest day with a walk in it is still a day you trained.</li>
</ul>

<h2>When you miss a day</h2>
<p>You will. The streak that matters is the one after the miss: train the next day, even if it is the five-minute version. Two misses in a row is where streaks actually end.</p>
<p>It helps if a miss costs something but not everything. A counter that drops to zero after 40 days makes the 41st day feel pointless.</p>

<h2>How Momentum works in CharacterSheet</h2>
<ul>
  <li>Train anything for five minutes and the day counts.</li>
  <li>Every day in a row adds 1% bonus XP to everything you earn, up to 50%.</li>
  <li>Miss a day and the count goes back by two days. It does not reset.</li>
  <li>Come back after a few days away and a comeback buff, Arise, is waiting. You spend it by training on the day you return.</li>
</ul>
{figure("shot-home.webp", "CharacterSheet Home: a level 29 character with a 21-day Momentum streak worth 21% bonus XP, and this week's days under it", "Momentum on Home: 21 days in a row, 21% bonus XP.")}
{figure("shot-buffs.webp", "The buffs panel in CharacterSheet: Momentum at 21%, Well Rested at 20%, On Track and Weighed In at 5% each, 51% in total", "Momentum is one buff. The others stack on top.")}
<div class="note-box">{NEEDS}</div>
""",
related=["gamify-your-workouts", "daily-habits-that-stick", "sleep-water-weight-habits"],
cta_h="Start day one",
cta_p="Five minutes counts. Every day in a row adds 1% to your XP.",
),
# ---------------------------------------------------------------- dailies
dict(
slug="daily-habits-that-stick",
title="Small Daily Habits That Stick: Keep the List Short",
meta="Three small daily habits beat ten ambitious ones. How to pick them, where to keep the list, and what to do on the days you miss.",
h1="Small Daily Habits That Stick",
lede="Making the bed will not change your life. Doing one small thing on purpose every day, including the days you do not feel like it, is practice for the bigger things.",
card="Three small things, finished every day, in one place you check each evening.",
quick="""<strong>Quick answer:</strong> Pick three small things you can finish in a few minutes each, keep the list where you will see it every evening, and tick them off the same day. In <a href="/">CharacterSheet</a> these are your dailies: every one you tick trains Willpower.""",
body=f"""
<h2>Keep the list to three</h2>
<p>A long list of habits feels productive for a week. Then one bad day leaves seven boxes empty, and the whole list starts to look like an accusation.</p>
<p>Three is enough to matter and short enough to finish on a bad day. Add a fourth after a few good weeks, not before.</p>

<h2>Make each one finishable</h2>
<p>"Read more" is a wish. "Read ten pages" is something you can tick. Good daily habits are small, specific and done in minutes:</p>
<ul>
  <li>Make my bed</li>
  <li>Read ten pages</li>
  <li>No snacking after dinner</li>
</ul>
<p>The last one is a habit of not doing something. Those count too, and they are often the hardest.</p>

<h2>Check the list at the same time every day</h2>
<p>Pick a moment in the evening and look at the list then. It is early enough to still do what is left, and late enough to know how the day went.</p>

<h2>Paper and Reminders both work</h2>
<p>A sticky note on the fridge does the job. So does a list of repeating reminders in the Reminders app on your iPhone. If either one is working for you, keep it.</p>
<p>What neither does is make the habits add up to anything. A ticked reminder disappears, and yesterday's sticky note goes in the bin.</p>

<h2>Dailies in CharacterSheet</h2>
<ol>
  <li>On Home, find the Daily willpower card and add your dailies. You can have up to five.</li>
  <li>Tick each one as you do it. Every tick trains Willpower, the sixth stat.</li>
  <li>Set an evening time in Settings, and the app reminds you then if any are left.</li>
  <li>A day with none done costs Willpower some XP, so the stat reflects how the week actually went.</li>
</ol>
{figure("shot-home.webp", "CharacterSheet Home with the Daily willpower card: two of three dailies done, and No snacking after dinner still open", "Two done, one to go.")}
<div class="note-box">A Home Screen widget shows the dailies you have left. {NEEDS}</div>
""",
related=["workout-streak", "level-up-in-real-life", "track-reading-and-study-time"],
cta_h="Three small things a day",
cta_p="Tick your dailies and Willpower levels up with the rest of you.",
),
# ---------------------------------------------------------------- reading
dict(
slug="track-reading-and-study-time",
title="How to Track Reading and Study Time on iPhone",
meta="Three ways to time your reading and studying on iPhone: the Clock app, a Focus to cut interruptions, and a tracker that turns minutes into XP.",
h1="How to Track Reading and Study Time on iPhone",
lede="Reading and studying have a problem workouts do not: nothing records them. No ring closes and no watch buzzes. If you want to know how much you actually did, you have to time it.",
card="The Clock app, a Focus, and a timer that turns the minutes into XP.",
quick="""<strong>Quick answer:</strong> Time each session with the Clock app's stopwatch or timer and note the minutes, and switch on a Focus so nothing interrupts. To keep a running total without the notes, use a tracker with a timer. In <a href="/">CharacterSheet</a>, reading, studying, coding, languages and writing train Wisdom, and every minute earns XP.""",
body=f"""
<h2>The plain way: Clock and a note</h2>
<p>Open the Clock app, start the stopwatch, read. When you stop, write the minutes in a note. It takes ten seconds and it works.</p>
<p>The weak point is the note. Totals by hand get skipped, and after a month you have a list of numbers that nobody has added up.</p>

<h2>Cut the interruptions with a Focus</h2>
<p>Twenty minutes of reading with three glances at messages is not twenty minutes. Set up a Focus in the Settings app, under Focus, and switch it on before you start. Your phone stays quiet until you are done.</p>

<h2>Read in sessions with an end</h2>
<p>"I will study tonight" is easy to put off. "Thirty minutes, starting now" is not. Pick a length before you begin, set a timer for it, and stop when it rings. A short session you finish beats a long one you keep meaning to start.</p>

<h2>How CharacterSheet tracks it</h2>
<ol>
  <li>Tap the plus button, choose Wisdom, and pick the activity: reading, studying, coding, a language, writing.</li>
  <li>Choose how to time it: an open timer, a set duration, or sets.</li>
  <li>Start. The timer stays on your Lock Screen, and XP comes by the minute.</li>
  <li>When you finish, the minutes land on Wisdom's XP bar and in the Log.</li>
</ol>
{figure("shot-log.webp", "The Log tab in CharacterSheet: 2 hours 44 minutes trained this week over eight weekly bars, coloured by stat, with a filter for each stat", "The Log adds up the weeks. Filter it to Wisdom to see only reading and study time.")}
{figure("shot-recap.webp", "The recap of yesterday in CharacterSheet: XP earned per stat, including 35 minutes of reading for Wisdom", "The next morning, a recap of what yesterday paid.")}
<p>The same goes for the quiet practices. Meditation, journaling and breathwork train Spirit, and CharacterSheet can save those sessions to Apple Health as Mindful Minutes.</p>
<div class="note-box">{NEEDS}</div>
""",
related=["level-up-in-real-life", "daily-habits-that-stick", "gamify-your-workouts"],
cta_h="Make reading count",
cta_p="Start the timer, read, and Wisdom levels up.",
),
# ---------------------------------------------------------------- body
dict(
slug="sleep-water-weight-habits",
title="How to Track Sleep, Water and Weight on iPhone",
meta="Sleep, water and a regular weigh-in are easy to track on iPhone with Apple Health. What each one takes, and how to make the habit pay.",
h1="How to Track Sleep, Water and Weight on iPhone",
lede="Training is the loud part of getting in shape. Sleep, water and a look at the scale are the quiet part, and they are easy to skip because nobody sees them.",
card="Apple Health holds all three. The hard part is doing them every day.",
quick="""<strong>Quick answer:</strong> Apple Health can hold all three: sleep from an Apple Watch or a sleep schedule, and water and weight typed in or saved by an app. The tracking is easy. Doing it daily is the hard part, so <a href="/">CharacterSheet</a> turns each into a buff: meet your sleep goal for 20% bonus XP, keep up with water for 5%, and weigh in for 5%.""",
body=f"""
<h2>Sleep</h2>
<p>If you wear an Apple Watch to bed, it records your sleep into Apple Health. Without one, a sleep schedule on your iPhone gives Health your time in bed, judged from when you put the phone down and pick it up.</p>
<p>Pick a number of hours you can actually reach on a work night. A goal you hit four nights a week teaches you more than one you never hit.</p>

<h2>Water</h2>
<p>Log it when you drink it, not from memory at night. A glass is small enough that you will forget it by dinner.</p>
<p>It also helps to spread it out. A litre at 22:00 to catch up is not the habit you were going for.</p>

<h2>Weight</h2>
<p>Weigh in at the same time of day, ideally in the morning, and look at the trend over weeks. One day's number moves with salt, water and dinner, and tells you very little.</p>
<p>Daily or weekly both work. What matters is that you keep looking.</p>

<h2>If Apple Health is enough, use it</h2>
<p>The Health app shows all three as charts, for free, and it is already on your iPhone. If you log there every day and it keeps you going, you do not need anything else.</p>
<p>Most people stop logging after a couple of weeks, because nothing happens when they do. That is the part a game can fix.</p>

<h2>How CharacterSheet makes them pay</h2>
<ul>
  <li><strong>Well Rested, 20%:</strong> sleep your goal's hours the night before.</li>
  <li><strong>On Track, 5%:</strong> stay ahead of your daily water goal. Log water with one tap.</li>
  <li><strong>Weighed In, 5%:</strong> log a weigh-in today.</li>
</ul>
<p>Buffs add bonus XP to everything you earn that day, and they add up. Sleep well, drink your water and step on the scale, and a workout pays 30% more before any other buff.</p>
{figure("shot-body.webp", "The Body tab in CharacterSheet: sleep and water charts for the last month with their buffs active, and quick buttons to log water", "Sleep, water and weight on the Body tab, each with its buff.")}
{figure("shot-buffs.webp", "The buffs panel in CharacterSheet: Well Rested at 20%, On Track and Weighed In at 5% each, with Momentum, 51% in total", "Every buff, what it adds, and how to earn it.")}
<div class="note-box">CharacterSheet reads sleep, weight and water from Apple Health on your iPhone, and saves the water and weigh-ins you log in the app back to it. None of it is sent to me. It is a habit tracker, not medical advice.</div>
""",
related=["workout-streak", "gamify-your-workouts", "daily-habits-that-stick"],
cta_h="Make the quiet habits pay",
cta_p="Sleep, water and a weigh-in each add bonus XP to your training.",
),
]

BY_SLUG = {p["slug"]: p for p in PAGES}


def related_html(slugs):
    items = "\n".join(f'      <li><a href="/guides/{s}/">{BY_SLUG[s]["h1"]}</a></li>' for s in slugs)
    return f"""<div class="related">
    <h2>Related guides</h2>
    <ul>
{items}
    </ul>
    <p><a href="/guides/">All guides</a></p>
  </div>"""


def cta_html(h, ptext, campaign):
    if not ON_STORE:
        return f"""<div class="article-cta">
    <h2>{h}</h2>
    <p>{ptext}</p>
    <div class="cta-row">
      {SOON_PILL}
    </div>
  </div>"""
    # The ENTIRE box is one anchor (no nested links: the badge is a decorative span)
    return f"""<a class="article-cta" href="{store_url(campaign)}" data-ph="appstore_click" aria-label="Download CharacterSheet on the App Store">
    <h2>{h}</h2>
    <p>{ptext}</p>
    <div class="cta-row">
      <span class="badge-link">
        <img src="/assets/appstore-badge.svg" alt="Download on the App Store" width="180" height="60">
      </span>
      <span class="cta-qr" aria-hidden="true"><img src="/assets/qr-appstore.svg" alt="" width="84" height="84"><span>On a computer? Scan with your iPhone camera to open the App Store.</span></span>
    </div>
  </a>"""


def article_ld(p, canonical):
    return ld({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": p["h1"],
        "description": p["meta"],
        "image": f"{DOMAIN}/assets/og-image.png",
        "datePublished": TODAY,
        "dateModified": TODAY,
        "author": {"@type": "Person", "name": "Emils Ozols", "url": "https://ozols.dev"},
        "publisher": {"@type": "Organization", "name": APP_NAME,
                      "logo": {"@type": "ImageObject", "url": f"{DOMAIN}/assets/icon-512.png"}},
        "mainEntityOfPage": canonical,
    }) + "\n" + ld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{DOMAIN}/"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": f"{DOMAIN}/guides/"},
            {"@type": "ListItem", "position": 3, "name": p["h1"], "item": canonical},
        ],
    })


def page(title, desc, canonical, body, campaign=CT_HOME, extra_head="", og_type="article",
         ogtitle=None, ogdesc=None):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{head(title, desc, canonical, og_type=og_type, ogtitle=ogtitle, ogdesc=ogdesc)}
{extra_head}
</head>
<body>

{header(campaign)}

<main>
{body}
</main>

{footer(campaign)}
{PAGE_JS}
</body>
</html>
"""


for p in PAGES:
    canonical = f"{DOMAIN}/guides/{p['slug']}/"
    body = f"""<article class="article">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a> › <a href="/guides/">Guides</a> › {p['h1']}</nav>
  <h1>{p['h1']}</h1>
  <p class="lede">{p['lede']}</p>
  <div class="quick-answer"><p>{p['quick']}</p></div>
{p['body']}
{cta_html(p['cta_h'], p['cta_p'], CT_GUIDE)}
{related_html(p['related'])}
</article>"""
    write(f"guides/{p['slug']}/index.html",
          page(p["title"], p["meta"], canonical, body, CT_GUIDE, article_ld(p, canonical)))

# =========================================================================================
# GUIDES HUB
# =========================================================================================
# Clusters with real intro copy and a FAQ of its own: AlarmPlanner's flat link-list hub sat
# "Crawled - currently not indexed" until it carried text worth indexing.
CLUSTERS = [
    ("Making training a game",
     """Points, levels and stats are a way of keeping score that you look forward to checking.
     These guides cover the rules worth copying from games, on paper or in an app.""",
     ["gamify-your-workouts", "level-up-in-real-life"]),
    ("Keeping it going",
     """Starting is easy. The second month is where plans go quiet. A low bar, a short list and
     a miss that does not cost everything are what carry a habit past it.""",
     ["workout-streak", "daily-habits-that-stick"]),
    ("The quiet half",
     """Reading, studying, sleep, water and the scale never make it into a workout summary. They
     count all the same, and they are easy to track once something records them.""",
     ["track-reading-and-study-time", "sleep-water-weight-habits"]),
]
_clustered = [s for _, _, slugs in CLUSTERS for s in slugs]
assert sorted(_clustered) == sorted(BY_SLUG), (
    f"hub out of sync: missing {sorted(set(BY_SLUG) - set(_clustered))}, "
    f"unknown {sorted(set(_clustered) - set(BY_SLUG))}")

HUB_FAQ = [
    ("How do you gamify exercise?",
     """Give every session points for the time you put in, add them up into levels, and reward
     days in a row. Keep the rules simple, and stop paying for training that has become easy.""",
     "gamify-your-workouts"),
    ("What stats would a real-life character have?",
     """A short list that covers body and mind. CharacterSheet uses six: Strength, Endurance,
     Agility, Wisdom, Spirit and Willpower, and your character is only as high as the lowest.""",
     "level-up-in-real-life"),
    ("How do I keep a workout streak?",
     """Set a minimum that counts on your worst day, like five minutes, and decide in advance what
     a rest day looks like. When you miss, train the next day.""",
     "workout-streak"),
    ("How many daily habits should I track?",
     """Three is a good start. Make each one small and specific, check the list at the same time
     every evening, and add another only after a few good weeks.""",
     "daily-habits-that-stick"),
    ("How can I track reading time on iPhone?",
     """Time each session with the Clock app and note the minutes, or use a tracker with a timer
     that keeps the total for you. A Focus keeps the session free of interruptions.""",
     "track-reading-and-study-time"),
    ("Can the iPhone track sleep, water and weight?",
     """Yes. Apple Health holds all three: sleep from an Apple Watch or a sleep schedule, and
     water and weight typed in or saved by an app.""",
     "sleep-water-weight-habits"),
]


def cards(slugs):
    return "\n".join(f"""      <a class="guide-card" href="/guides/{s}/">
        <h3>{BY_SLUG[s]['h1']}</h3>
        <p>{BY_SLUG[s]['card']}</p>
        <span class="more">Read the guide</span>
      </a>""" for s in slugs)


def faq_details(items, link_text="Read the guide"):
    out = []
    for q, a, href in items:
        link = f' <a href="{href}">{link_text if not href.startswith("#") else "Get the app"}</a>' if href else ""
        out.append(f"""      <details>
        <summary>{q}</summary>
        <p>{" ".join(a.split())}{link}</p>
      </details>""")
    return "\n".join(out)


def faq_ld(items):
    return ld({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": plain(q),
                        "acceptedAnswer": {"@type": "Answer", "text": plain(a)}}
                       for q, a, _ in items],
    })


clusters_html = "\n".join(f"""  <div class="container guide-cluster">
    <h2>{h}</h2>
    <p class="cluster-intro">{" ".join(intro.split())}</p>
    <div class="guide-grid">
{cards(slugs)}
    </div>
  </div>""" for h, intro, slugs in CLUSTERS)

HUB_DESC = ("Practical guides to training like an RPG character: gamifying workouts, keeping a "
            "streak, daily habits, and tracking reading, sleep, water and weight.")
hub_items = [(q, a, f"/guides/{s}/") for q, a, s in HUB_FAQ]
hub_body = f"""<article class="article">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a> › Guides</nav>
  <h1>Guides: Level Up in Real Life</h1>
  <p class="lede">Practical answers on making training a game, keeping it going, and tracking the quiet habits around it.</p>
  <p>Most plans to get in shape fail the same way. The first two weeks go well, then a busy week comes, and nothing in the plan notices you are gone. A game notices. It keeps score, it pays you today for what you did today, and it has something for you to come back to.</p>
  <p>Each guide starts with what works without any app, then the tools already on your iPhone, then how <a href="/">CharacterSheet</a> handles it. Where the honest answer is that a notebook or Apple Health is enough, the guide says so.</p>
</article>
<section style="padding-top: 0;">
{clusters_html}
</section>
<section>
  <div class="container">
    <h2>Common questions</h2>
    <div class="faq-list">
{faq_details(hub_items)}
    </div>
  </div>
</section>"""
hub_head_ld = ld({
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    "name": "Guides: Level Up in Real Life",
    "description": HUB_DESC,
    "url": f"{DOMAIN}/guides/",
}) + "\n" + faq_ld(hub_items)
write("guides/index.html",
      page("Guides: Gamify Workouts, Streaks and Daily Habits", HUB_DESC,
           f"{DOMAIN}/guides/", hub_body, CT_GUIDE, hub_head_ld))

# =========================================================================================
# HOME
# =========================================================================================
ICONS = {
    "timer": '<circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9.5 2.5h5M12 2.5V5"/>',
    "levels": '<path d="M4 20V14M10 20V9M16 20V12M22 20V4"/><path d="M2 20h22" transform="translate(-1 0)"/>',
    "scroll": '<path d="M7 4h11a2 2 0 012 2v11a3 3 0 01-3 3H8a3 3 0 01-3-3V6a2 2 0 012-2z"/><path d="M9 9h7M9 13h7M9 17h4"/>',
    "bolt": '<path d="M13 2L4.5 13.5H11L10 22l8.5-11.5H12L13 2z"/>',
    "flame": '<path d="M12 22c4 0 7-2.7 7-6.8 0-3.6-2.6-6-4.2-8.2-.5 2.1-1.5 3.3-2.8 3.9C12.4 7.5 11 4.6 8.8 2.5 8.6 6.2 5 9 5 15.2 5 19.3 8 22 12 22z"/>',
    "decay": '<path d="M3 7l6 6 4-4 8 8"/><path d="M21 12v5h-5"/>',
    "watch": '<rect x="6.5" y="6.5" width="11" height="11" rx="3.2"/><path d="M9 6.5l.6-3.5h4.8l.6 3.5M9 17.5l.6 3.5h4.8l.6-3.5M12 10v2.2l1.4 1"/>',
    "heart": '<path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0112 7.6a4.3 4.3 0 017.5 2.7c0 5.6-7.5 10.2-7.5 10.2z"/><path d="M7.5 12.5h2.2l1.3-2.4 1.8 4 1.2-1.6h2.5"/>',
}
FEATURES = [
    ("timer", "XP by the minute", "Pick an activity and start the timer. XP comes in while you train, and the timer stays on your Lock Screen."),
    ("levels", "Level 1 to 60", "Easy workouts are enough at low levels. The higher you go, the harder the training has to be."),
    ("scroll", "57 quests", "Some are on the board from day one. Others you have to discover."),
    ("bolt", "Buffs for good habits", "Sleeping enough, drinking water and weighing in each add bonus XP to everything you earn."),
    ("flame", "Momentum", "Every day in a row you train adds 1% to your XP, up to 50%. Five minutes is enough to count."),
    ("decay", "Stats that decay", "Neglect a stat and it starts losing XP, just like in real life. A level, once earned, stays."),
    ("watch", "An Apple Watch app", "Start a session from your wrist. It tracks your heart rate, so more effort earns more XP."),
    ("heart", "Works with Apple Health", "Reads your workouts, heart rate, sleep, weight and water, and saves your sessions back."),
]
SHOTS = [
    ("shot-home.webp", "CharacterSheet Home: a level 29 character with six stats, a 21-day Momentum streak, Daily willpower and quests", "Level up in real life"),
    ("shot-recap.webp", "The recap of yesterday: the XP each stat earned, session by session", "Every workout earns XP"),
    ("shot-stats.webp", "The Stats tab: an XP bar and a ten-day strip for each stat", "Six stats to train"),
    ("shot-radar.webp", "The Stats tab: a radar of the six stats with the level, the rank and the stat holding it", "See where you stand"),
    ("shot-quests.webp", "The Quests board: an urgent quest with a countdown, and today's quests", "Quests for the real world"),
    ("shot-buffs.webp", "The buffs panel: Momentum, Well Rested, On Track and Weighed In add up to 51% bonus XP", "Stack buffs for bonus XP"),
    ("shot-body.webp", "The Body tab: sleep, water and weight charts from Apple Health", "Sleep, water, weight"),
    ("shot-log.webp", "The Log tab: this week's minutes and XP over eight weekly bars", "Watch your weeks add up"),
    ("shot-workouts.webp", "Strength activities, each with its difficulty: Traditional, Functional, Core Training, HIIT, Boxing", "30+ workouts to choose from"),
    ("shot-setup.webp", "Setting up a Strength session: 30 minutes of Traditional, worth 234 XP", "Pick an activity"),
    ("shot-timer.webp", "A running Strength session: 21 minutes on the timer and 105 XP so far", "Start the timer"),
    ("shot-complete.webp", "A finished session: 171 XP earned, with base XP, effort and buffs listed", "See what it paid"),
]
HOME_FAQ = [
    ("What is CharacterSheet?",
     """An RPG character sheet for your real life. You train, you get XP, your stats level up. Six
     stats cover lifting, cardio, mobility, learning, calm and getting things done.""",
     "/guides/level-up-in-real-life/"),
    ("What counts as training?",
     """Weights, running, yoga and the other workouts you would expect, and also reading, studying,
     meditation, journaling, deep work and chores. There are more than 30 activities, each tied to
     one of the six stats, and you can add your own.""",
     "#stats"),
    ("How do I earn XP?",
     """Pick an activity and start the timer. XP comes by the minute, harder activities pay more,
     and buffs add a bonus on top. Dailies, small things you tick off, earn XP for Willpower.""",
     "/guides/gamify-your-workouts/"),
    ("Do I need an Apple Watch?",
     """No. The iPhone app works by itself. With an Apple Watch you can start sessions from your
     wrist, and it tracks your heart rate, so more effort earns more XP.""",
     None),
    ("What are buffs?",
     """Bonus XP on everything you earn, given for good habits. Momentum grows 1% for every day in
     a row you train, up to 50%. Sleeping enough, drinking water and weighing in each add a buff
     too, and they all add up.""",
     "/guides/sleep-water-weight-habits/"),
    ("What happens if I stop training?",
     """A stat you neglect starts losing XP each night, just like in real life. It never drops a
     level. Miss a day and Momentum goes back by two days instead of resetting.""",
     "/guides/workout-streak/"),
    ("Does it work with Apple Health?",
     """Yes. It reads your workouts, heart rate, sleep, weight and water, and saves your sessions,
     water and weigh-ins back. Reading and saving each have their own switch in Settings.""",
     "/privacy/"),
    ("Where is my character stored?",
     """On your iPhone, with a backup in your own iCloud. There is no account to make and no
     sign-up, and your Apple Health data is never sent to me.""",
     "/privacy/"),
    ("How much does it cost?",
     """CharacterSheet runs on a subscription, monthly or yearly. New subscribers can start the
     yearly plan with a free trial. Prices are shown in the app before you buy.""",
     "/terms/"),
    ("Which languages does it speak?",
     """English and German.""",
     None),
    ("Is there an Android version?",
     """Not at the moment: CharacterSheet is made for iPhone and Apple Watch. On Android? Tap
     Register your interest at the top of this page, so I know.""",
     None),
]


def home_faq_details():
    out = []
    for q, a, href in HOME_FAQ:
        if href is None:
            link = ""
        elif href == "#stats":
            link = f' <a href="{href}">See the six stats</a>'
        else:
            link = f' <a href="{href}">Learn more</a>'
        out.append(f"""      <details>
        <summary>{q}</summary>
        <p>{" ".join(a.split())}{link}</p>
      </details>""")
    return "\n".join(out)


def feature_cards():
    return "\n".join(f"""      <div class="feature-card">
        <div class="ico"><svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[i]}</svg></div>
        <h3>{h}</h3>
        <p>{p}</p>
      </div>""" for i, h, p in FEATURES)


def stat_cards():
    return "\n".join(f"""      <div class="stat-card" style="--stat: {color}">
        <div class="stat-head"><span class="stat-code">{code}</span><h3>{name}</h3></div>
        <p>{line}</p>
        <p class="trains"><span>Trained by:</span> {trains}</p>
      </div>""" for code, name, color, line, trains in STATS)


def rank_ladder():
    return "\n".join(f'      <div class="rank"><b>{letter}</b><span>{level}</span></div>'
                     for letter, level in RANKS)


def marquee_set(hidden):
    figs = "\n".join(f"""          <figure>
            <img class="screen" src="/assets/{src}" alt="{'' if hidden else html.escape(alt)}" loading="lazy" width="640" height="1306">
            <figcaption>{cap}</figcaption>
          </figure>""" for src, alt, cap in SHOTS)
    aria = ' aria-hidden="true"' if hidden else ""
    return f"""        <div class="shots-set"{aria}>
{figs}
        </div>"""


ANDROID = 'On Android? <button type="button" class="android-link" data-android>Register your interest</button>'
HOME_TITLE = "CharacterSheet: Fitness RPG for iPhone and Apple Watch"
HOME_DESC = ("Turn workouts, reading and meditation into XP. Six real-life stats from level 1 to 60, "
             "with quests and buffs. A fitness RPG for iPhone and Apple Watch.")
HOME_OG = ("An RPG character sheet for your real life. You train, you get XP, your stats level up.")
STORE = store_url(CT_HOME)

home_body = f"""
<!-- ============ HERO ============ -->
<section class="hero" id="download">
  <div class="container hero-grid">
    <div>
      <span class="eyebrow">Fitness RPG for iPhone and Apple Watch</span>
      <h1>Level up <span class="accent">in real life</span></h1>
      <p class="hero-sub">CharacterSheet is an RPG character sheet for your real life. You train, you get XP, your stats level up. Lifting, running, yoga, reading, meditation and the chores you keep putting off all count.</p>
      <div class="cta-row">
        {badge(CT_HOME)}
        <span class="cta-qr" aria-hidden="true"><img src="/assets/qr-appstore.svg" alt="" width="84" height="84"><span>On a computer? Scan with your iPhone camera to open the App Store.</span></span>
      </div>
      <div class="android-cta">{ANDROID}</div>
      <div class="trust-row">
        <span>Six stats, level 1 to 60</span>
        <span>Apple Watch app</span>
        <span>Works with Apple Health</span>
        <span>No account, no ads</span>
      </div>
    </div>
    <div class="hero-art">
      <img class="screen" src="/assets/shot-home.webp" alt="CharacterSheet on iPhone: a level 29 character with six stats, a 21-day Momentum streak, Daily willpower and quests" width="640" height="1306" fetchpriority="high">
    </div>
  </div>
</section>

<!-- ============ STATS ============ -->
<section id="stats">
  <div class="container">
    <div class="section-head">
      <h2>Six stats, one character</h2>
      <p>Everything you do trains one of them. Each stat goes from level 1 to 60, and every ten levels is a rank.</p>
    </div>
    <div class="stat-grid">
{stat_cards()}
    </div>
    <div class="ranks" aria-label="Ranks, from E at level 1 to S at level 50">
{rank_ladder()}
    </div>
  </div>
</section>

<!-- ============ FEATURES ============ -->
<section id="features">
  <div class="container">
    <div class="section-head">
      <h2>The game around your training</h2>
      <p>You do the work. CharacterSheet keeps the score and gives you a reason to come back tomorrow.</p>
    </div>
    <div class="feature-grid">
{feature_cards()}
    </div>
    <p class="extras"><strong>Also in the box:</strong> dailies that train Willpower, Home Screen widgets, a recap of yesterday when you open the app, a log of everything, and more than 30 workout types with room for your own.</p>
  </div>
</section>

<!-- ============ SCREENSHOTS ============ -->
<section id="screenshots">
  <div class="container">
    <div class="section-head">
      <h2>See it in action</h2>
      <p>Real screens, straight from the app.</p>
    </div>
  </div>
  <div class="shots-marquee">
      <div class="shots-track">
{marquee_set(False)}
{marquee_set(True)}
      </div>
    </div>
</section>

<!-- ============ HOW IT WORKS ============ -->
<section id="how-it-works">
  <div class="container">
    <div class="section-head">
      <h2>How it works</h2>
      <p>From "I should really work out" to XP on the board, in three steps.</p>
    </div>
    <div class="steps">
      <div class="step">
        <div class="num">1</div>
        <h3>Pick what you are doing</h3>
        <p>Tap the plus button and choose an activity: weights, a run, yoga, a book, meditation, deep work. Each one trains one of the six stats.</p>
      </div>
      <div class="step">
        <div class="num">2</div>
        <h3>Start the timer</h3>
        <p>XP comes by the minute while you train. Harder activities pay more, and with an Apple Watch your heart rate counts too.</p>
      </div>
      <div class="step">
        <div class="num">3</div>
        <h3>Watch the stat climb</h3>
        <p>The session lands on its stat's XP bar. Fill the bar and the stat levels up. Come back tomorrow and Momentum adds a bonus on top.</p>
      </div>
    </div>
  </div>
</section>

<!-- ============ GUIDES ============ -->
<section id="guides">
  <div class="container">
    <div class="section-head">
      <h2>Guides</h2>
      <p>Straight answers on making training a game and keeping it going.</p>
    </div>
    <div class="guide-grid">
{cards([p["slug"] for p in PAGES])}
    </div>
  </div>
</section>

<!-- ============ FAQ ============ -->
<section id="faq">
  <div class="container">
    <div class="section-head">
      <h2>Frequently asked questions</h2>
    </div>
    <div class="faq-list">
{home_faq_details()}
    </div>
  </div>
</section>

<!-- ============ CTA ============ -->
<section>
  <div class="container">
{cta_band()}
    <div class="android-cta android-cta--center">{ANDROID}</div>
  </div>
</section>
"""
home_ld = ld({
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": APP_NAME,
    "operatingSystem": f"iOS {MIN_IOS} or later",
    "applicationCategory": "HealthApplication",
    "description": "A fitness RPG for iPhone and Apple Watch. Workouts, reading, meditation and daily habits earn XP for six stats that level from 1 to 60, with quests and buffs.",
    "url": f"{DOMAIN}/",
    "author": {"@type": "Person", "name": "Emils Ozols", "url": "https://ozols.dev"},
    "image": f"{DOMAIN}/assets/icon-512.png",
    **({"downloadUrl": STORE_CANONICAL} if ON_STORE else {}),
}) + "\n" + faq_ld(HOME_FAQ)
write("index.html", page(HOME_TITLE, HOME_DESC, f"{DOMAIN}/", home_body, CT_HOME, home_ld,
                         og_type="website", ogdesc=HOME_OG))

# =========================================================================================
# SUPPORT / PRIVACY / TERMS
# The app's paywall and the store listing link /terms/ and /privacy/ here, and the listing's
# support URL is /support/ (getcharactersheet.com, 2026-10-12): keep these three paths.
# =========================================================================================
MAIL = f'<a href="mailto:{SUPPORT_EMAIL}">{SUPPORT_EMAIL}</a>'

LEGAL = [
dict(
slug="support",
title="Support | CharacterSheet",
meta="Support for CharacterSheet, the fitness RPG for iPhone and Apple Watch: contact, Apple Health, the Watch app, backups, subscriptions and your data.",
h1="Support",
sub="Questions, problems or ideas? Every email lands in a real inbox, and I read everything.",
body=f"""
<div class="quick-answer"><p><strong>Email:</strong> <a href="mailto:{SUPPORT_EMAIL}?subject=CharacterSheet%20support">{SUPPORT_EMAIL}</a>. I usually reply within a couple of days. CharacterSheet is made by one person, so a short description of what you expected and what happened instead helps a lot.</p></div>

<h2>Frequently asked</h2>

<h3>Where is my character stored?</h3>
<p>On your iPhone, with a backup in your own iCloud. CharacterSheet has no account of its own, and no server of mine holds your character. The one thing that does leave your phone is anonymous usage statistics, which you can turn off in Settings, Help out; the <a href="/privacy/">privacy policy</a> lists exactly what they contain.</p>

<h3>I got a new iPhone. How do I get my character back?</h3>
<p>Sign in to the same Apple Account and install CharacterSheet. If a backup is in your iCloud, the app offers to restore it. You can also restore later from Settings, Backup, Restore from Backup.</p>

<h3>My workouts or sleep are not showing up</h3>
<p>CharacterSheet reads them from Apple Health, so it needs permission. In CharacterSheet, check that Settings, Health, Read from Apple Health is on. Then open the Health app, tap your picture, and look for CharacterSheet under the apps that can read your data.</p>

<h3>The Apple Watch app is out of date with my phone</h3>
<p>Open CharacterSheet on your iPhone, go to Settings, Apple Watch, and tap Resync with Apple Watch. Keep both apps open for a moment.</p>

<h3>Why did a stat lose XP overnight?</h3>
<p>Each level asks for a certain amount of training, and a session buys days of cover. A night without cover takes some XP from that stat. It never takes a level. The Stats tab shows how many days each stat is covered for.</p>

<h3>Why does an activity pay no XP?</h3>
<p>Its difficulty reads Trivial: your level has outgrown it. Pick a harder activity for that stat. Light activities carry a stat through the early levels, and only vigorous ones reach level 60.</p>

<h3>How do I manage or cancel my subscription?</h3>
<p>In CharacterSheet, open Settings, Subscription, Manage subscription. Or in the iOS Settings app, tap your name, then Subscriptions. On a new phone, Restore purchases in the same card brings your plan back.</p>

<h3>How do I turn off usage statistics?</h3>
<p>Settings, Help out, "Share anonymous usage". It stops immediately.</p>

<h3>How do I delete my data?</h3>
<p>Settings, Data, Delete All Data removes your character from the app. To remove the backup too, open the iOS Settings app, tap your name, then iCloud, manage your storage, choose CharacterSheet and delete its data. Workouts, water and weigh-ins that were saved to Apple Health stay there until you delete them in the Health app.</p>

<h2>Guides</h2>
<p>For streaks, daily habits and making training a game, see the <a href="/guides/">guides</a>.</p>
""",
),
dict(
slug="privacy",
title="Privacy Policy | CharacterSheet",
meta="Privacy policy for CharacterSheet, the fitness RPG for iPhone. No account, no ads, Health data stays on your device, opt-out anonymous usage statistics.",
h1="Privacy Policy",
sub="Last updated: 12 October 2026",
body=f"""
<h2>The short version</h2>
<ul>
  <li>No account and no sign-up. Open the app and start.</li>
  <li>Your character lives on your iPhone and is backed up to your own iCloud.</li>
  <li>Your Apple Health data is read on your device and never sent to me.</li>
  <li>The app collects anonymous usage statistics, so I can see what gets used. You can turn that off in Settings.</li>
  <li>No ads, and nothing is sold to anyone.</li>
</ul>

<h2>Data storage</h2>
<p>CharacterSheet stores your character, your stats and XP, your sessions, quests, dailies and settings on your device and in <strong>your own private iCloud</strong>. There is no CharacterSheet account, and I run no server that holds your data. I cannot see it. The one thing that does leave your phone is the anonymous usage statistics described below, which you can turn off.</p>

<h2>Apple Health</h2>
<p>With your permission, CharacterSheet reads from Apple Health: workouts, active energy, heart rate and resting heart rate, walking, running and cycling distance, sleep, body weight, water, and your date of birth. It uses them to import workouts, to work out how much effort a session took, and to give the sleep, water and weigh-in buffs.</p>
<p>With your permission, it saves to Apple Health: the workouts you time in the app, Mindful Minutes for Spirit sessions, and the water and weigh-ins you log.</p>
<p>Health data is read and used <strong>on your device</strong>. It is never sent to me, never used for advertising, and is not part of the usage statistics. Reading and saving each have their own switch in Settings, Health, and you can change what CharacterSheet may access at any time in the Health app.</p>

<h2>Apple Watch</h2>
<p>The Apple Watch app talks to your iPhone and to Apple Health on the watch. It sends nothing to me, and collects no usage statistics.</p>

<h2>Notifications</h2>
<p>Reminders are created on your iPhone. They do not pass through any server of mine.</p>

<h2>Backups</h2>
<p>CharacterSheet can save automatic backup copies of your character to your own iCloud, and you can make one yourself in Settings, Backup. A backup holds your character and your sessions. It is held by Apple under your Apple Account and is not sent to me.</p>

<h2>Anonymous usage statistics</h2>
<p>CharacterSheet uses <strong>PostHog</strong> (hosted in the EU) to collect anonymous usage statistics, so I can see which features get used and where people get stuck. CharacterSheet carries no advertising and no advertising trackers.</p>
<p>What is collected:</p>
<ul>
  <li>Counts of what happens: sessions started, finished and discarded, with the stat, the activity type, the minutes and the XP; dailies ticked; quests accepted and completed; backups made; a plan bought, with its price</li>
  <li>That water or a weigh-in was logged, without the amount</li>
  <li>That a workout was imported from Apple Health, without what it was or how long it ran</li>
  <li>Which screens and onboarding steps were viewed, and which settings were switched on or off</li>
  <li>App-level context: your character's level and rank, each stat's level, your Momentum streak, how many dailies and sessions exist, which plan is active, whether backups are on and which widgets are in use</li>
  <li>Generic context: app version and language, debug or release build, whether notifications are allowed, and the day the app was first opened</li>
  <li>If you installed the app from an Apple ad on the App Store: which campaign that ad belonged to, as Apple reports it. It says nothing about who you are.</li>
  <li>If you answer the in-app question "What is CharacterSheet missing?" and tap Send: the answer you typed, up to 500 characters. It is the only text you type that is collected, so leave out anything personal.</li>
</ul>
<p>What is <strong>not</strong> collected:</p>
<ul>
  <li>Your name, your character's name, your email, or any personal identifiers</li>
  <li>Anything from Apple Health: no heart rate, sleep, weight, water amounts or workouts</li>
  <li>Anything else you type: your character's name, the names of your dailies and of activities you add stay on your device</li>
  <li>Your location, contacts, or advertising identifiers</li>
  <li>Anything linked back to you as an individual</li>
</ul>
<p>The statistics can be turned off at any time in Settings, Help out, "Share anonymous usage". The app respects it immediately.</p>

<h2>This website</h2>
<p>This site counts page views, and taps on its App Store links and a few buttons, with PostHog, hosted in the EU, so I can see which pages are useful. It sets no cookies, stores nothing on your device, and does not build a profile of you.</p>

<h2>Purchases</h2>
<p>Apple processes every payment. I never see your payment details.</p>

<h2>Third-party sharing</h2>
<p>I do not sell, share, or transfer your data. Apple provides iCloud, Apple Health, notifications and payments under Apple's own privacy policy. The only other third-party service is PostHog, for the anonymous usage statistics described above, stored on EU servers and never linked to you as an individual.</p>

<h2>Your rights</h2>
<ul>
  <li><strong>Access &amp; export</strong>: everything CharacterSheet stores is visible in the app, and the backup in your iCloud is a copy of it.</li>
  <li><strong>Deletion</strong>: Settings, Data, Delete All Data removes your character. To remove the backup, open the iOS Settings app, tap your name, then iCloud, manage your storage, choose CharacterSheet and delete its data. Entries saved to Apple Health are deleted in the Health app.</li>
  <li><strong>Opt out of usage statistics</strong>: the Settings switch above.</li>
</ul>
<p>If you are an EU/EEA resident, the GDPR grants you additional rights regarding any data processed. CharacterSheet sends me nothing that identifies you, so the only things I could hold are anonymous usage statistics and an email you send. Contact me using the email below to exercise your rights.</p>

<h2>Children's privacy</h2>
<p>CharacterSheet is not aimed at children, and it does not collect personal information from anyone.</p>

<h2>Support email</h2>
<p>If you email {MAIL}, I use your message and address only to reply. No mailing lists, no sharing. Sending an answer from the in-app feedback question also opens a mail draft to that address, which goes only if you send it.</p>

<h2>Changes</h2>
<p>If a future version of CharacterSheet changes any of the above, this page and the App Store privacy label will be updated before that version ships.</p>
""",
),
dict(
slug="terms",
title="Terms of Use | CharacterSheet",
meta="Terms of use for CharacterSheet, the fitness RPG for iPhone: the Monthly and Yearly plans, renewal and cancellation, refunds, and health.",
h1="Terms of Use",
sub="Last updated: 12 October 2026",
body=f"""
<p>These terms cover your use of CharacterSheet, the fitness RPG for iPhone and Apple Watch made by Emils Ozols ("I", "me"). By downloading or using CharacterSheet you agree to them. If you do not agree, please do not use the app.</p>

<h2>Using CharacterSheet</h2>
<p>You may use CharacterSheet on Apple devices you own or control. Apple's <a href="https://www.apple.com/legal/internet-services/itunes/dev/stdeula/">Standard End User License Agreement</a> also applies. You may not copy, resell, reverse-engineer or redistribute the app.</p>

<h2>Plans</h2>
<p>CharacterSheet is free to download. Using it takes one of two plans, both auto-renewable subscriptions:</p>
<ul>
  <li><strong>Monthly.</strong> Billed once a month.</li>
  <li><strong>Yearly.</strong> Billed once a year.</li>
</ul>
<p>New subscribers can start either plan with a free trial; its length is shown before you start.</p>
<p>Both plans unlock every part of CharacterSheet, on iPhone and Apple Watch. Prices are shown in the app before you buy and vary by country or region. Apple processes every payment through the App Store, tied to your Apple Account. On a new phone, "Restore purchases" brings your plan back.</p>

<h2>Renewal and cancellation</h2>
<ul>
  <li>Payment is charged to your Apple Account when you confirm the purchase, or when the free trial ends if you started one.</li>
  <li>A plan renews automatically unless auto-renew is turned off at least 24 hours before the end of the current period. Your Apple Account is charged for the renewal within the 24 hours before the period ends.</li>
  <li>You can manage or cancel the subscription in your Apple Account settings: on iPhone, open Settings, tap your name, then Subscriptions. Cancelling stops the next renewal; the plan keeps working until the end of the period you paid for.</li>
  <li>Cancel during the free trial and you are not charged. Any unused part of a free trial ends when you buy a plan.</li>
</ul>

<h2>When a plan ends</h2>
<p>If your trial or subscription ends, everything you built is kept. Your character stays on your phone and in your iCloud backup. Carrying on with it takes a plan.</p>

<h2>Refunds</h2>
<p>Apple handles every payment, so I cannot issue refunds myself. You can ask Apple for one at <a href="https://reportaproblem.apple.com/">reportaproblem.apple.com</a>, under Apple's refund policy.</p>

<h2>Health and exercise</h2>
<p>CharacterSheet is a game around your training. It is not a medical device and gives no medical advice. The levels, ranks and effort it shows are scores in a game, not a measure of your health. Talk to a doctor before starting a new exercise routine if you have a health condition or any doubt, and stop if something hurts. You train at your own risk.</p>

<h2>XP, levels and quests</h2>
<p>XP, levels, ranks, buffs and quest rewards exist only inside the app. They are not money: they cannot be bought, sold or exchanged, and they have no cash value. I may rebalance how XP is earned, which can change a level.</p>

<h2>Your data</h2>
<p>What you put into CharacterSheet is yours. It lives on your devices and in your own iCloud, as the <a href="/privacy/">privacy policy</a> describes.</p>

<h2>Acceptable use</h2>
<p>Use CharacterSheet lawfully. Do not try to disrupt it, or to reach the systems it relies on without permission.</p>

<h2>No warranty</h2>
<p>CharacterSheet is provided "as is" and "as available", without warranties of any kind, express or implied. Reminders, sync, Apple Health and backups depend on your devices, iOS and iCloud, which are outside my control.</p>

<h2>Limitation of liability</h2>
<p>To the extent the law allows, I am not liable for indirect, incidental or consequential damages from using CharacterSheet or being unable to use it. Where liability cannot be excluded, it is limited to what you paid for CharacterSheet in the twelve months before the claim.</p>

<h2>Changes</h2>
<p>I may change or remove features, and update these terms. If the terms change in a meaningful way, the date at the top changes too. Using CharacterSheet after a change means you accept the updated terms.</p>

<h2>Governing law</h2>
<p>These terms are governed by the laws of Latvia and the European Union. Nothing here limits the consumer rights you have under the law of the country you live in.</p>

<h2>Contact</h2>
<p>Questions about these terms: <a href="mailto:{SUPPORT_EMAIL}?subject=CharacterSheet%20terms">{SUPPORT_EMAIL}</a>. For help with the app, see <a href="/support/">support</a>.</p>
""",
),
]

for lp in LEGAL:
    body = f"""<article class="article">
  <nav class="breadcrumb" aria-label="Breadcrumb"><a href="/">Home</a> › {lp['h1']}</nav>
  <h1>{lp['h1']}</h1>
  <p class="lede">{lp['sub']}</p>
{lp['body']}
</article>"""
    write(f"{lp['slug']}/index.html", page(lp["title"], lp["meta"], f"{DOMAIN}/{lp['slug']}/", body))

# =========================================================================================
# 404, SITEMAP, ROBOTS, CNAME
# =========================================================================================
e404_body = """<article class="article" style="text-align:center; padding-top: 70px; padding-bottom: 90px;">
  <img class="icon-404" src="/assets/apple-touch-icon.png" alt="" width="96" height="96">
  <h1>404: this quest is not on the board</h1>
  <p class="lede">This page does not exist, or it moved.</p>
  <div class="cta-row" style="justify-content: center;"><a class="btn-secondary" href="/">Back to the homepage</a><a class="btn-secondary" href="/guides/">Browse the guides</a></div>
</article>"""
write("404.html", page("Page Not Found | CharacterSheet",
                       "That page does not exist. Head back to the CharacterSheet homepage or browse the guides.",
                       f"{DOMAIN}/404.html", e404_body))

urls = ([f"{DOMAIN}/", f"{DOMAIN}/guides/"]
        + [f"{DOMAIN}/guides/{p['slug']}/" for p in PAGES]
        + [f"{DOMAIN}/{lp['slug']}/" for lp in LEGAL])
sitemap = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
sitemap += [f"  <url><loc>{u}</loc><lastmod>{TODAY}</lastmod></url>" for u in urls]
sitemap.append("</urlset>")
write("sitemap.xml", "\n".join(sitemap) + "\n")
if DOMAIN_IS_FINAL:
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
    write("CNAME", DOMAIN.split("://", 1)[1] + "\n")
else:
    write("robots.txt", "User-agent: *\nDisallow: /\n")
    cname = os.path.join(SITE, "CNAME")
    if os.path.exists(cname):
        os.remove(cname)
print(f"{len(urls)} urls in the sitemap" + ("" if DOMAIN_IS_FINAL else "  (PLACEHOLDER DOMAIN: noindex, robots Disallow)"))

# ---------- WebP fallback (2026-10-30) ----------
# Some company networks refuse image/webp: every WebP gets a PNG twin and every <img> an onerror
# that swaps it in. Runs last, over generated and hand-written pages alike (_gen/webp_fallback.py).
import webp_fallback  # noqa: E402
webp_fallback.run()
