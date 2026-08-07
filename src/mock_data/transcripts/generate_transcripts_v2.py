"""
Mock data generator v2 — 15 SEPARATE transcript CSV files (per captain's
explicit ask), each matching the exact format main.py already produces:
    timestamp, caller_number, speaker, text

Style is calibrated against a real test call transcript: callers speak in
fragments, spell out emails/addresses awkwardly, go off-topic and get
redirected, ask for services outside roofing scope (plumbing) and get
politely declined-but-redirected, give doubled/conflicting availability,
ask to speak to a manager, etc. The agent stays roofing/restoration-scoped
(incl. fire damage, storm damage, insurance claims per the latest scope
doc) and always steers back to collecting the 6 fields.

Two scenarios flagged as missing from the first pass are covered here:
  - A genuine second call from the same caller (Denise Coleman, files 02/03)
  - A second person calling on behalf of the original caller, same
    household (Priya Ortiz calling on behalf of husband Steven, file 05)
"""
import csv
import os
from datetime import datetime, timedelta

OUTDIR = "transcripts"
os.makedirs(OUTDIR, exist_ok=True)

BASE = datetime(2026, 8, 7, 8, 0, 0)

def ts(days=0, hours=0, minutes=0):
    return BASE + timedelta(days=days, hours=hours, minutes=minutes)

def write_call(filename, caller_number, start_ts, lines):
    """lines: list of (speaker, text, minute_offset)"""
    path = os.path.join(OUTDIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "caller_number", "speaker", "text"])
        for speaker, text, offset in lines:
            t = start_ts + timedelta(minutes=offset)
            w.writerow([t.isoformat(), caller_number, speaker, text])
    print(f"Wrote {filename} ({len(lines)} turns)")


# ---------------------------------------------------------------------
# 01 — Mark Reynolds: routine leak, one off-topic tangent, clean close
# ---------------------------------------------------------------------
write_call("call_01_mark_reynolds.csv", "+14175551001", ts(hours=9), [
    ("assistant", "Thanks for calling, this is the front desk for the roofing company — how can I help?", 0.0),
    ("caller", "Hey, quick question first, do you know if it's supposed to rain again this weekend?", 0.3),
    ("assistant", "I'm just the front desk for the roofing company, so I can't help with the forecast — but let's get your roof taken care of. What's going on?", 0.5),
    ("caller", "Oh right, sorry. Yeah so I've got a leak in my attic, started after the storm last week.", 0.9),
    ("assistant", "Got it, sorry to hear that. Can I get your full name?", 1.2),
    ("caller", "Mark Reynolds.", 1.4),
    ("assistant", "Thanks, Mark. And we'll confirm the number you're calling from — is that the best number to reach you?", 1.6),
    ("caller", "Yep, that one's fine.", 1.8),
    ("assistant", "Great. Can I get your email address?", 2.0),
    ("caller", "Sure, it's mreynolds, at gmail dot com.", 2.3),
    ("assistant", "Got it — mreynolds@gmail.com. And what's the property address?", 2.6),
    ("caller", "412 Cascade Avenue, Springfield.", 2.9),
    ("assistant", "Thanks. Can you describe the leak in a bit more detail — where exactly, and how bad?", 3.2),
    ("caller", "It's a small drip near the chimney, only when it rains hard. Not flooding or anything.", 3.6),
    ("assistant", "Understood, sounds manageable but worth getting looked at before it gets worse. When's a good time for someone to come out?", 4.0),
    ("caller", "Weekday afternoons after 4 work best.", 4.3),
    ("assistant", "Perfect, I've got you down for weekday afternoons after 4pm. We'll follow up soon to confirm a time. Anything else?", 4.6),
    ("caller", "Nope, that's it, thanks.", 4.9),
    ("assistant", "You're welcome, Mark. Take care.", 5.0),
])

# ---------------------------------------------------------------------
# 02 — Denise Coleman, FIRST call: shingle damage
# ---------------------------------------------------------------------
write_call("call_02_denise_coleman_first_call.csv", "+14175551002", ts(days=1, hours=10), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, a bunch of my shingles blew off yesterday in the wind.", 0.3),
    ("assistant", "Sorry to hear that — let's get that taken care of. Can I get your name?", 0.6),
    ("caller", "Denise Coleman.", 0.8),
    ("assistant", "Thanks, Denise. Email address?", 1.0),
    ("caller", "Um, it's d dot coleman, at outlook dot com. Wait, no — d-period-coleman.", 1.4),
    ("assistant", "Got it, d.coleman@outlook.com. And the property address?", 1.8),
    ("caller", "77 Maplewood Drive.", 2.0),
    ("assistant", "Can you tell me more about the damage — how many shingles, and is there any leaking yet?", 2.3),
    ("caller", "Looks like maybe six or seven missing on the south side. No leaking that I can see yet.", 2.7),
    ("assistant", "Good that it's not leaking yet, but worth getting ahead of it. What's a good time for an estimate?", 3.1),
    ("caller", "Mornings before 11 work for me.", 3.4),
    ("assistant", "Got it, mornings before 11. We'll be in touch to confirm. Anything else?", 3.7),
    ("caller", "No, that's all.", 3.9),
    ("assistant", "Thanks Denise, talk soon.", 4.0),
])

# ---------------------------------------------------------------------
# 03 — Denise Coleman, SECOND call (true follow-up / repeat caller)
# ---------------------------------------------------------------------
write_call("call_03_denise_coleman_second_call.csv", "+14175551002", ts(days=4, hours=9, minutes=30), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, this is Denise Coleman again, I called earlier this week about my shingles.", 0.3),
    ("assistant", "Hi Denise, yes I see your call from earlier this week about the shingle damage at 77 Maplewood Drive. What can I help with?", 0.7),
    ("caller", "Just wanted to check if anyone's been assigned to come look at it yet.", 1.1),
    ("assistant", "Let me note that you're following up on that — I'll flag it so someone gets back to you with a status update today.", 1.4),
    ("caller", "Okay, appreciate it. Is the morning-before-11 window still what you have on file?", 1.8),
    ("assistant", "Yes, that's what we have. Let us know if that changes.", 2.1),
    ("caller", "Nope, still works. Thanks.", 2.3),
    ("assistant", "You're welcome, we'll be in touch soon.", 2.4),
])

# ---------------------------------------------------------------------
# 04 — Steven Ortiz: roof replacement inquiry, asks about insurance (in scope)
# ---------------------------------------------------------------------
write_call("call_04_steven_ortiz_first_call.csv", "+14175551003", ts(days=2, hours=13), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, I think it's time to replace my roof, it's getting pretty old.", 0.3),
    ("assistant", "Sure, happy to help with that. Can I get your name?", 0.6),
    ("caller", "Steven Ortiz.", 0.8),
    ("assistant", "Thanks Steven. Email address?", 1.0),
    ("caller", "steven dot ortiz at yahoo dot com.", 1.3),
    ("assistant", "Got it. And the property address?", 1.6),
    ("caller", "205 Fieldstone Court.", 1.8),
    ("assistant", "How old is the current roof, and are you seeing any specific issues, or is this more preventative?", 2.1),
    ("caller", "It's about 20 years old, no active leaks, just want to get ahead of it before it becomes a problem.", 2.6),
    ("caller", "Also, does insurance usually cover any of a replacement like this, or is that a separate conversation?", 3.0),
    ("assistant", "That's a great question and something we can absolutely help walk through — insurance and claims are part of what we handle, so we can go over that when we come out for the estimate. When works for a visit?", 3.5),
    ("caller", "Weekends are easiest for me.", 3.9),
    ("assistant", "Got it, weekends. We'll follow up to schedule. Anything else?", 4.2),
    ("caller", "No, that covers it.", 4.4),
    ("assistant", "Thanks Steven, talk soon.", 4.5),
])

# ---------------------------------------------------------------------
# 05 — Priya Ortiz calling ON BEHALF of Steven, same household/address
# ---------------------------------------------------------------------
write_call("call_05_priya_ortiz_on_behalf_of_steven.csv", "+14175551010", ts(days=5, hours=11), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, I'm calling on behalf of my husband, Steven Ortiz — he called earlier this week about getting the roof replaced.", 0.3),
    ("assistant", "Of course — yes, I have his call on file about the roof replacement at 205 Fieldstone Court. What can I help with?", 0.8),
    ("caller", "I'm actually home most weekday mornings too, so if it's easier to schedule around my availability instead of just his, let me know.", 1.3),
    ("assistant", "That's helpful, thank you. Can I get your name so I can add you as an additional contact for this property?", 1.7),
    ("caller", "Priya Ortiz. Same address, same household, I just wanted to confirm someone's still coming out this weekend.", 2.1),
    ("assistant", "Yes, we've got weekend availability noted from Steven's call, and I'll add your name and weekday-morning availability as a backup option. Is your number a good second contact too?", 2.6),
    ("caller", "Yes, this number works.", 2.9),
    ("assistant", "Perfect, you're both on file now for 205 Fieldstone Court. We'll follow up to confirm a time.", 3.1),
    ("caller", "Great, thank you.", 3.3),
    ("assistant", "You're welcome, Priya, take care.", 3.4),
])

# ---------------------------------------------------------------------
# 06 — Angela Kim, Apt 2B: storm damage, ceiling stain spreading
# ---------------------------------------------------------------------
write_call("call_06_angela_kim_apt2b.csv", "+14175551004", ts(days=3, hours=8), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, there's a water stain on my bedroom ceiling and it's getting bigger since last night's storm.", 0.3),
    ("assistant", "That sounds urgent — let's get your info quickly. Can I get your name?", 0.6),
    ("caller", "Angela Kim.", 0.8),
    ("assistant", "Thanks Angela. Is the water actively dripping right now, or just the stain spreading?", 1.0),
    ("caller", "Not dripping yet, just spreading, but it's noticeably bigger than this morning.", 1.4),
    ("assistant", "Okay, good that it's not actively dripping yet, but we'll flag this as a priority. Email address?", 1.8),
    ("caller", "angela dot kim at gmail dot com.", 2.1),
    ("assistant", "And the property address, including unit number?", 2.4),
    ("caller", "118 Birchwood Lane, Apartment 2B.", 2.7),
    ("assistant", "Got it. What time works best for someone to come look, ideally soon given it's spreading?", 3.0),
    ("caller", "Any weekday works, I work from home.", 3.3),
    ("assistant", "Perfect, we'll prioritize getting someone out this week. We'll follow up shortly.", 3.6),
    ("caller", "Thank you.", 3.8),
])

# ---------------------------------------------------------------------
# 07 — Marcus Webb, Apt 4C: same building as Angela, gutter damage, asks for manager
# ---------------------------------------------------------------------
write_call("call_07_marcus_webb_apt4c.csv", "+14175551005", ts(days=3, hours=8, minutes=45), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Yeah my gutter's hanging half off after the storm last night.", 0.3),
    ("assistant", "Got it, sorry about that. Can I get your name?", 0.6),
    ("caller", "Marcus Webb.", 0.8),
    ("assistant", "Thanks Marcus. Email address?", 1.0),
    ("caller", "mwebb22 at gmail dot com.", 1.3),
    ("assistant", "And the property address with unit number?", 1.6),
    ("caller", "118 Birchwood Lane, Apartment 4C. I think my neighbor might've called about a ceiling leak too, same building.", 2.0),
    ("assistant", "Thanks for the heads up, we'll make sure both are on file. When's a good time for someone to take a look at your gutter?", 2.5),
    ("caller", "Evenings after 6.", 2.8),
    ("assistant", "Got it, evenings after 6. Anything else going on with the roof, or just the gutter?", 3.1),
    ("caller", "Just the gutter. Actually, can I talk to an actual manager about getting this prioritized? I've had gutter issues before with a different company and got ignored.", 3.6),
    ("assistant", "Totally understand that concern, Marcus. I'll make sure this gets flagged for a manager to review, and everything you've told me goes straight to the team so nothing gets lost. Let's make sure we've got everything locked in first — evenings after 6 works for you?", 4.2),
    ("caller", "Yeah that's fine.", 4.5),
    ("assistant", "Great, you're all set, and I'll note the request for manager follow-up. We'll be in touch.", 4.7),
    ("caller", "Okay, thanks.", 4.9),
])

# ---------------------------------------------------------------------
# 08 — Latoya Brooks: active emergency leak
# ---------------------------------------------------------------------
write_call("call_08_latoya_brooks_emergency.csv", "+14175551006", ts(days=6, hours=22, minutes=15), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Water is pouring through my ceiling right now, I need someone tonight!", 0.15),
    ("assistant", "Understood, this is urgent, I'm getting your info right now. Can I get your name?", 0.3),
    ("caller", "Latoya Brooks.", 0.4),
    ("assistant", "And the address?", 0.5),
    ("caller", "930 Crestline Drive.", 0.6),
    ("assistant", "Got it. Is the water coming from one spot or spreading across the ceiling?", 0.75),
    ("caller", "One spot in the living room but it's getting worse fast, I've got buckets out.", 0.95),
    ("assistant", "Okay, I'm flagging this as an emergency right now and getting someone to call you back within the hour. Best number to reach you is the one you're calling from?", 1.2),
    ("caller", "Yes, this number.", 1.35),
    ("assistant", "Got it, someone will call you very shortly. Hang in there.", 1.5),
    ("caller", "Please hurry.", 1.6),
])

# ---------------------------------------------------------------------
# 09 — Carlos Mendez, call 1: inspection before selling, slightly off-topic tangent
# ---------------------------------------------------------------------
write_call("call_09_carlos_mendez_first_call.csv", "+14175551007", ts(hours=14), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, I'm selling my house and want the roof inspected before it goes on the market.", 0.3),
    ("assistant", "Sure thing, we can help with that. Can I get your name?", 0.6),
    ("caller", "Carlos Mendez. Actually, do you know any good realtors in the area too? Trying to line everything up at once.", 1.0),
    ("assistant", "I'm just the front desk for the roofing side, so I can't help with realtors — but let's get your inspection squared away. Email address?", 1.5),
    ("caller", "carlos dot mendez at gmail dot com.", 1.9),
    ("assistant", "And the property address?", 2.2),
    ("caller", "56 Ridgeline Way.", 2.4),
    ("assistant", "Any known issues with the roof currently, or is this a general pre-sale inspection?", 2.7),
    ("caller", "No known issues, just want it documented before we list.", 3.0),
    ("assistant", "Makes sense. What's your availability like?", 3.3),
    ("caller", "Pretty flexible, whenever works.", 3.5),
    ("assistant", "Great, we'll follow up to get something scheduled.", 3.7),
    ("caller", "Sounds good.", 3.9),
])

# ---------------------------------------------------------------------
# 10 — Carlos Mendez, call 2: follow-up to schedule
# ---------------------------------------------------------------------
write_call("call_10_carlos_mendez_second_call.csv", "+14175551007", ts(days=3, hours=15), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, Carlos Mendez again, following up on the inspection I asked about earlier this week.", 0.3),
    ("assistant", "Hi Carlos, yes I've got that on file for 56 Ridgeline Way. Let's get a date locked in — any preference?", 0.7),
    ("caller", "Anytime next week works, I'm flexible.", 1.1),
    ("assistant", "Great, we'll aim for sometime next week and confirm the exact day shortly.", 1.4),
    ("caller", "Perfect, thanks.", 1.6),
])

# ---------------------------------------------------------------------
# 11 — Carlos Mendez, call 3: confirmation, doubled availability
# ---------------------------------------------------------------------
write_call("call_11_carlos_mendez_third_call.csv", "+14175551007", ts(days=8, hours=16), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Just calling to confirm the inspection is still on for this week.", 0.3),
    ("assistant", "Yes, confirmed for Thursday morning. Does that still work?", 0.6),
    ("caller", "Thursday morning works, or actually Friday afternoon could work too if morning falls through.", 1.0),
    ("assistant", "Got it, I'll note Thursday morning as the primary and Friday afternoon as a backup in case anything shifts.", 1.4),
    ("caller", "Perfect, thank you.", 1.6),
    ("assistant", "You're welcome, Carlos, see you then.", 1.7),
])

# ---------------------------------------------------------------------
# 12 — Whitney Foster, call 1: routine gutter cleaning
# ---------------------------------------------------------------------
write_call("call_12_whitney_foster_first_call.csv", "+14175551008", ts(days=1, hours=16), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "I'd like to get my gutters cleaned out.", 0.3),
    ("assistant", "Sure, we can help. Can I get your name?", 0.6),
    ("caller", "Whitney Foster.", 0.8),
    ("assistant", "Thanks Whitney. Email address?", 1.0),
    ("caller", "whitney dot f at gmail dot com.", 1.3),
    ("assistant", "And the property address?", 1.6),
    ("caller", "14 Oakhaven Circle.", 1.8),
    ("assistant", "Any specific concerns, or just routine cleaning?", 2.1),
    ("caller", "Just routine, nothing urgent.", 2.3),
    ("assistant", "Got it. What's a good time?", 2.5),
    ("caller", "Weekday mornings.", 2.7),
    ("assistant", "Perfect, we'll follow up to schedule.", 2.9),
])

# ---------------------------------------------------------------------
# 13 — Whitney Foster, call 2: NEW unrelated issue (not a true follow-up),
#      also asks about a plumbing problem (out of scope)
# ---------------------------------------------------------------------
write_call("call_13_whitney_foster_second_call_new_issue.csv", "+14175551008", ts(days=20, hours=9), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Hi, this is Whitney Foster again — different issue this time, my skylight's leaking.", 0.3),
    ("assistant", "Hi Whitney, good to hear from you, sorry about the skylight. Different from the gutter cleaning last time — let's get details. Is it actively leaking right now?", 0.8),
    ("caller", "Just after it rains, a little water pools around the frame. Also while I have you, my garbage disposal's been broken for weeks, any chance you all handle that too?", 1.4),
    ("assistant", "We're roofing and restoration only, so the disposal would need a plumber, sorry about that — but let's get the skylight taken care of. Same address, 14 Oakhaven Circle?", 2.0),
    ("caller", "Yep, same place.", 2.2),
    ("assistant", "Got it. What time works for someone to take a look?", 2.4),
    ("caller", "Weekday mornings still work best for me.", 2.7),
    ("assistant", "Perfect, noted. We'll follow up soon.", 2.9),
    ("caller", "Thanks.", 3.1),
])

# ---------------------------------------------------------------------
# 14 — Robin Chen: fragmented speech, off-topic tangent, doubled availability
# ---------------------------------------------------------------------
write_call("call_14_robin_chen_estimate.csv", "+14175551009", ts(days=7, hours=10), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "Yeah hi, um, so I was, like, wondering, um, about maybe getting like a, uh, cost thing for a new roof?", 0.3),
    ("assistant", "Sure, happy to help with a cost estimate for a new roof. Can I get your name?", 0.8),
    ("caller", "Robin Chen.", 1.0),
    ("caller", "Oh also, random question, is it supposed to be hot this whole week?", 1.2),
    ("assistant", "I'm just the front desk here for roofing, so I can't help with the forecast, but let's get your estimate going. Email address?", 1.6),
    ("caller", "Uh, it's, um, robin dot chen, at, um, gmail, dot com.", 2.0),
    ("assistant", "Got it. Property address?", 2.4),
    ("caller", "88 Sunset Terrace.", 2.6),
    ("assistant", "Any specific issues with the current roof, or just want a ballpark cost?", 2.9),
    ("caller", "Just a ballpark, no urgent issues really.", 3.2),
    ("assistant", "Got it. What's your availability like for someone to come out and take a look?", 3.5),
    ("caller", "Um, weekday evenings, or, actually, wait, maybe weekend mornings instead, either one honestly.", 3.9),
    ("assistant", "No problem, I'll note both weekday evenings and weekend mornings as options.", 4.2),
    ("caller", "Okay cool, thanks.", 4.4),
])

# ---------------------------------------------------------------------
# 15 — Jason Pham: closely mirrors the reference transcript style —
#      gibberish spelled-out email, asks for manager, confirms everything
# ---------------------------------------------------------------------
write_call("call_15_jason_pham_chimney.csv", "+14175551011", ts(days=9, hours=17), [
    ("assistant", "Front desk for the roofing company, how can I help?", 0.0),
    ("caller", "There's a gap around my chimney flashing, letting some moisture in.", 0.3),
    ("assistant", "Got it, sorry about that. Can I get your full name?", 0.6),
    ("caller", "Jason Pham.", 0.8),
    ("assistant", "Thanks, Jason. Could you share your email address?", 1.0),
    ("caller", "Yeah so it's like, uh, J, uh, P-H-A-M, um...", 1.3),
    ("assistant", "Take your time.", 1.5),
    ("caller", "88 at, um, gmail.com.", 1.7),
    ("assistant", "Got it, jpham88@gmail.com. And the property address?", 2.0),
    ("caller", "301 Hillcrest Avenue.", 2.2),
    ("assistant", "Thanks. Can you describe how bad the gap is — is any water actually coming through yet?", 2.5),
    ("caller", "A little draft and some minor moisture, not a full leak yet.", 2.9),
    ("assistant", "Good that it's caught early. When's a good time for someone to come out?", 3.2),
    ("caller", "Weekends only for me.", 3.4),
    ("assistant", "Got it, weekends only. We'll follow up to confirm a time.", 3.6),
    ("caller", "Is there any way I could just talk to a manager directly instead of waiting on a callback?", 3.9),
    ("assistant", "I totally understand wanting to move quickly — I'll flag this for a manager to follow up directly, and everything you've shared is already on file so nothing needs repeating. We'll be in touch soon.", 4.4),
    ("caller", "Okay, appreciate it. Thanks.", 4.8),
    ("assistant", "You're welcome, Jason, take care.", 4.9),
])

print(f"\nDone — 15 files written to ./{OUTDIR}/")
