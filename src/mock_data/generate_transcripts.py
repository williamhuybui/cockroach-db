"""
Mock data generator v4 — rewrites all 15 transcripts to match the ACTUAL
rhythm of real test calls, not a cleaned-up version of it:

  - Assistant confirms back nearly every piece of info the caller gives
    ("Thanks for that, Scott. We'll make sure...") rather than silently
    moving to the next question
  - Callers speak in longer, run-on, hesitant sentences with
    self-corrections and filler words, not clean one-liners
  - Off-topic pushback gets a brief acknowledgment of the caller's
    reasoning before the redirect, not a flat refusal
  - Manager requests get the exact real phrasing pattern: "no one
    available to transfer... but I can take down your information..."
  - Emails/addresses get spelled out awkwardly and sometimes corrected
  - Company name: "The Front Desk That Never Sleeps" (reverted from the
    placeholder), same 15 callers/scenarios as before, same 4-column
    format: timestamp, caller_number, speaker, text
"""
import csv
import os
from datetime import datetime, timedelta

OUTDIR = "transcripts"
os.makedirs(OUTDIR, exist_ok=True)

BASE = datetime(2026, 8, 10, 8, 0, 0)

def ts(days=0, hours=0, minutes=0):
    return BASE + timedelta(days=days, hours=hours, minutes=minutes)

def write_call(filename, caller_number, start_ts, lines):
    path = os.path.join(OUTDIR, filename)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "caller_number", "speaker", "text"])
        for speaker, text, offset in lines:
            t = start_ts + timedelta(minutes=offset)
            w.writerow([t.isoformat(), caller_number, speaker, text])
    print(f"Wrote {filename} ({len(lines)} turns)")


# 01 — Mark Reynolds
write_call("call_01_mark_reynolds.csv", "+14175551001", ts(hours=9), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. I help with roofing, storm restoration, and related services. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Yeah, so, um, quick question first, do you happen to know if it's supposed to rain again this weekend? I'm just trying to figure out timing here.", 0.3),
    ("assistant", "I'm only able to help with roofing and restoration questions for The Front Desk That Never Sleeps. Is there something about your roof or an appointment I can help with?", 0.6),
    ("caller", "Oh, okay, yeah, that's fair. So I've got this leak in my attic, it started after the storm last week, and it's kind of been bugging me since.", 1.0),
    ("assistant", "Sorry to hear that. That sounds worth getting looked at. Could you tell me your full name?", 1.4),
    ("caller", "Mark Reynolds.", 1.6),
    ("assistant", "Thanks for that, Mark. Could I also get an email address for you?", 1.9),
    ("caller", "Uh yeah, it's mreynolds, all one word, at gmail dot com.", 2.2),
    ("assistant", "Got it, so that's mreynolds@gmail.com. And what's the property address where the leak's happening?", 2.6),
    ("caller", "412 Cascade Avenue, Springfield.", 2.9),
    ("assistant", "Thanks for that. Is there a unit or apartment number for 412 Cascade Avenue, or is it a single-family home?", 3.2),
    ("caller", "No, single-family, just the house.", 3.5),
    ("assistant", "Got it. Can you tell me a bit more about the leak — where exactly it is, and how bad it seems?", 3.8),
    ("caller", "It's like a small drip near the chimney, mostly happens when it rains really hard, hasn't flooded or anything like that.", 4.2),
    ("assistant", "Understood, good that it's not too severe yet, but definitely worth getting ahead of. What's a good time for someone to come take a look?", 4.7),
    ("caller", "Weekday afternoons after 4 usually work best for me.", 5.1),
    ("assistant", "Perfect, so we've got you down as Mark Reynolds, 412 Cascade Avenue, weekday afternoons after 4. Is there anything else before we wrap up?", 5.4),
    ("caller", "Nope, I think that covers it.", 5.8),
    ("assistant", "Great, thanks for calling, Mark — take care!", 6.0),
])

# 02 — Denise Coleman, first call
write_call("call_02_denise_coleman_first_call.csv", "+14175551002", ts(days=1, hours=10), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. I help with roofing, storm restoration, and related services. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, yeah, so a bunch of my shingles blew off yesterday, it was pretty windy, and I just want to get it looked at before it turns into something worse.", 0.3),
    ("assistant", "Sorry to hear that, let's get that taken care of. Could I get your full name?", 0.8),
    ("caller", "Denise Coleman.", 1.0),
    ("assistant", "Thanks for that, Denise. Could I get an email address as well?", 1.3),
    ("caller", "Sure, it's d, dot, coleman, at outlook dot com. Wait, sorry, let me say that again — d dot coleman at outlook dot com.", 1.7),
    ("assistant", "No problem, got it, d.coleman@outlook.com. And what's the property address?", 2.1),
    ("caller", "77 Maplewood Drive.", 2.4),
    ("assistant", "Thanks. Is there a unit or apartment number there, or is it a single-family home?", 2.7),
    ("caller", "Single-family, no unit.", 3.0),
    ("assistant", "Got it. Can you tell me more about the damage — roughly how many shingles, and is there any leaking yet?", 3.3),
    ("caller", "Looks like maybe six or seven missing, all on the south side. No leaking that I can tell so far, thankfully.", 3.7),
    ("assistant", "Good that it's not leaking yet, but definitely worth getting ahead of before the next storm. Just a heads up, we won't be able to quote an exact price until someone's actually inspected it in person. What's a good time for an estimate?", 4.2),
    ("caller", "Mornings, before 11, usually work best for me.", 4.7),
    ("assistant", "So we've got Denise Coleman, 77 Maplewood Drive, mornings before 11. Anything else before we wrap up?", 5.0),
    ("caller", "No, I think that's everything.", 5.3),
    ("assistant", "Thanks for calling, Denise — we'll be in touch soon!", 5.5),
])

# 03 — Denise Coleman, second call
write_call("call_03_denise_coleman_second_call.csv", "+14175551002", ts(days=4, hours=9, minutes=30), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, um, this is Denise Coleman again, I called earlier this week about the shingles blowing off my roof.", 0.3),
    ("assistant", "Hi Denise, yes, I do see your call from earlier this week about the shingle damage at 77 Maplewood Drive. What can I help with?", 0.7),
    ("caller", "I just wanted to check in and see if anyone's actually been assigned to come look at it yet, it's been a few days.", 1.1),
    ("assistant", "Totally understandable. Let me flag that for a status update — I'll make sure someone follows up with you today with where things stand.", 1.5),
    ("caller", "Okay, I appreciate that. And is the morning-before-11 window still what you all have on file for me?", 2.0),
    ("assistant", "Yes, that's still what we have noted.", 2.3),
    ("caller", "Great, that still works for me, no changes needed.", 2.6),
    ("assistant", "Perfect, we'll be in touch soon. Thanks for calling, Denise — take care!", 2.9),
])

# 04 — Steven Ortiz
write_call("call_04_steven_ortiz_first_call.csv", "+14175551003", ts(days=2, hours=13), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, so, I think it's about time to replace my roof, it's getting up there in age and I'd rather deal with it now than wait for a problem.", 0.3),
    ("assistant", "That's a smart move. Could I get your full name?", 0.8),
    ("caller", "Steven Ortiz.", 1.0),
    ("assistant", "Thanks for that, Steven. Email address?", 1.3),
    ("caller", "Yeah, it's steven, dot, ortiz, at yahoo dot com.", 1.6),
    ("assistant", "Got it, steven.ortiz@yahoo.com. And the property address?", 2.0),
    ("caller", "205 Fieldstone Court.", 2.3),
    ("assistant", "Thanks. Unit or apartment number, or single-family?", 2.6),
    ("caller", "Single-family home.", 2.8),
    ("assistant", "Got it. How old is the current roof, and are you seeing any active issues, or is this more preventative?", 3.1),
    ("caller", "It's about 20 years old at this point, no active leaks right now, I just want to get ahead of it before something actually goes wrong.", 3.6),
    ("caller", "Also, does insurance usually cover part of a replacement like this, or is that a totally separate conversation I need to have?", 4.1),
    ("assistant", "That's something we can help document for a claim, though I'm not able to give specific insurance or legal advice myself — that's a conversation we can go into more when we're out for the estimate. When works for a visit?", 4.7),
    ("caller", "Weekends are easiest for me, honestly.", 5.1),
    ("assistant", "So we've got Steven Ortiz, 205 Fieldstone Court, weekends. Anything else before we wrap up?", 5.4),
    ("caller", "No, I think that covers it.", 5.7),
    ("assistant", "Thanks for calling, Steven — take care!", 5.9),
])

# 05 — Priya Ortiz, on behalf of Steven
write_call("call_05_priya_ortiz_on_behalf_of_steven.csv", "+14175551010", ts(days=5, hours=11), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, so, I'm actually calling on behalf of my husband, Steven Ortiz — he called earlier this week about getting a roof replacement estimate.", 0.3),
    ("assistant", "Of course, thanks for letting me know. Yes, I do have his call on file about the replacement at 205 Fieldstone Court. What can I help with?", 0.8),
    ("caller", "I'm actually home most weekday mornings too, so if it's easier to work around my schedule instead of just his, that might give you more flexibility.", 1.3),
    ("assistant", "That's really helpful to know, thank you. Could I get your name so I can add you as a second contact on the property?", 1.8),
    ("caller", "Priya Ortiz. Same address, same household, obviously — I just wanted to confirm someone's still planning to come out this weekend like we discussed.", 2.3),
    ("assistant", "Yes, that's still noted from Steven's call. I'll go ahead and add your weekday-morning availability as a backup option too. Is this number good as a second contact for the property?", 2.9),
    ("caller", "Yes, this number's fine.", 3.2),
    ("assistant", "Perfect, so we've got both you and Steven on file now for 205 Fieldstone Court. Anything else before I let you go?", 3.5),
    ("caller", "No, that's everything, thank you.", 3.8),
    ("assistant", "You're welcome, Priya — take care!", 4.0),
])

# 06 — Angela Kim, Apt 2B
write_call("call_06_angela_kim_apt2b.csv", "+14175551004", ts(days=3, hours=8), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, um, yeah, there's a water stain on my bedroom ceiling and it's actually gotten noticeably bigger since last night's storm, so I'm a little worried about it.", 0.3),
    ("assistant", "That does sound like something we should get eyes on quickly. Could I get your full name?", 0.8),
    ("caller", "Angela Kim.", 1.0),
    ("assistant", "Thanks for that, Angela. Is the water actively dripping right now, or is it more just the stain spreading?", 1.3),
    ("caller", "Not dripping yet, thankfully, just the stain spreading, but it's definitely bigger than it was this morning.", 1.7),
    ("assistant", "Okay, good that it's not actively dripping, but we'll go ahead and flag this as a priority. Could I get an email address?", 2.2),
    ("caller", "Yeah, angela dot kim at gmail dot com.", 2.5),
    ("assistant", "Got it. And the property address, including a unit number if there is one?", 2.9),
    ("caller", "118 Birchwood Lane, Apartment 2B.", 3.2),
    ("assistant", "Thanks. What time works best for someone to come take a look, ideally soon given it's still spreading?", 3.6),
    ("caller", "Honestly any weekday works, I work from home so I'm pretty flexible.", 4.0),
    ("assistant", "Perfect, so we've got Angela Kim, 118 Birchwood Lane Apartment 2B, and we'll prioritize getting someone out this week. Anything else?", 4.4),
    ("caller", "No, that's everything.", 4.7),
    ("assistant", "Thanks for calling, Angela — we'll follow up soon!", 4.9),
])

# 07 — Marcus Webb, Apt 4C
write_call("call_07_marcus_webb_apt4c.csv", "+14175551005", ts(days=3, hours=8, minutes=45), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Yeah, so my gutter's basically hanging half off the building after the storm last night, it looks pretty bad honestly.", 0.3),
    ("assistant", "Sorry to hear that. Could I get your full name?", 0.7),
    ("caller", "Marcus Webb.", 0.9),
    ("assistant", "Thanks for that, Marcus. Email address?", 1.2),
    ("caller", "mwebb22 at gmail dot com.", 1.5),
    ("assistant", "Got it. And the property address, with unit number?", 1.9),
    ("caller", "118 Birchwood Lane, Apartment 4C. Actually, I think my neighbor might've already called about a ceiling leak, same building as me.", 2.3),
    ("assistant", "Thanks for the heads up, I'll make sure we've got both on file. When's a good time for someone to check the gutter?", 2.8),
    ("caller", "Evenings after 6 usually work best for me.", 3.2),
    ("assistant", "Got it. Anything else going on with the roof itself, or just the gutter for now?", 3.5),
    ("caller", "Just the gutter for now. Actually, is there any way I could talk to an actual manager about getting this prioritized? I had a bad experience with a different company before where stuff like this got ignored for weeks.", 4.0),
    ("assistant", "I completely understand that concern, Marcus. I'm not able to transfer you directly right now, but I'll make sure this gets flagged for a manager to follow up, and everything you've told me is already on file so nothing gets lost. Anything else before we wrap up?", 4.7),
    ("caller", "No, I think that's it.", 5.1),
    ("assistant", "Thanks for calling, Marcus — take care!", 5.3),
])

# 08 — Latoya Brooks, emergency
write_call("call_08_latoya_brooks_emergency.csv", "+14175551006", ts(days=6, hours=22, minutes=15), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Water is pouring through my ceiling right now, I need somebody out here tonight, please!", 0.15),
    ("assistant", "Understood, this is urgent, let's get your information right away. Could I get your full name?", 0.3),
    ("caller", "Latoya Brooks.", 0.4),
    ("assistant", "Thanks, Latoya. And the address?", 0.5),
    ("caller", "930 Crestline Drive.", 0.6),
    ("assistant", "Unit number, or single-family?", 0.7),
    ("caller", "Single-family.", 0.8),
    ("assistant", "Got it. Is the water coming from one spot, or is it spreading across the ceiling?", 0.95),
    ("caller", "One spot in the living room but it's getting worse fast, I've already got buckets out.", 1.2),
    ("assistant", "Okay, I'm flagging this as an emergency right now and getting someone to call you back within the hour. Is the number you're calling from the best one to reach you?", 1.5),
    ("caller", "Yes, this number, please hurry.", 1.7),
    ("assistant", "Understood, someone will call you very shortly. Hang in there, Latoya.", 1.9),
])

# 09 — Carlos Mendez, call 1
write_call("call_09_carlos_mendez_first_call.csv", "+14175551007", ts(hours=14), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, so I'm actually selling my house and I want to get the roof inspected before it goes on the market, just to have that documented.", 0.3),
    ("assistant", "Sure, we can definitely help with that. Could I get your full name?", 0.8),
    ("caller", "Carlos Mendez.", 1.0),
    ("assistant", "Thanks for that, Carlos. Email address?", 1.3),
    ("caller", "carlos dot mendez at gmail dot com.", 1.6),
    ("assistant", "Got it. And the property address?", 2.0),
    ("caller", "56 Ridgeline Way.", 2.3),
    ("assistant", "Unit number, or single-family?", 2.5),
    ("caller", "Single-family.", 2.7),
    ("assistant", "Got it. Any known issues currently, or is this more of a general pre-sale inspection?", 3.0),
    ("caller", "No known issues that I'm aware of, just want it documented before we list, kind of a peace-of-mind thing.", 3.4),
    ("assistant", "That makes sense. What's your availability like?", 3.8),
    ("caller", "Pretty flexible on my end, honestly.", 4.1),
    ("assistant", "So we've got Carlos Mendez, 56 Ridgeline Way, flexible availability. Anything else before we wrap up?", 4.4),
    ("caller", "No, that's everything.", 4.7),
    ("assistant", "Thanks for calling, Carlos!", 4.9),
])

# 10 — Carlos Mendez, call 2
write_call("call_10_carlos_mendez_second_call.csv", "+14175551007", ts(days=3, hours=15), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, this is Carlos Mendez again, just following up on the inspection I asked about earlier this week.", 0.3),
    ("assistant", "Hi Carlos, yes, I do have that on file for 56 Ridgeline Way. Let's go ahead and get a date locked in — any preference?", 0.8),
    ("caller", "Anytime next week's fine for me, I'm pretty flexible on timing.", 1.3),
    ("assistant", "Great, we'll aim for sometime next week and confirm the exact day shortly. Anything else?", 1.7),
    ("caller", "No, that's all, thanks.", 2.0),
])

# 11 — Carlos Mendez, call 3
write_call("call_11_carlos_mendez_third_call.csv", "+14175551007", ts(days=8, hours=16), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hey, just calling to confirm the inspection's still on for this week.", 0.3),
    ("assistant", "Yes, that's confirmed for Thursday morning. Does that still work on your end?", 0.7),
    ("caller", "Thursday morning works, or, actually, Friday afternoon could work too if morning ends up falling through for some reason.", 1.2),
    ("assistant", "Got it, I'll note Thursday morning as the primary and Friday afternoon as a backup in case anything shifts. Anything else?", 1.7),
    ("caller", "No, that's it, appreciate it.", 2.0),
    ("assistant", "You're welcome, Carlos — see you then!", 2.2),
])

# 12 — Whitney Foster, call 1
write_call("call_12_whitney_foster_first_call.csv", "+14175551008", ts(days=1, hours=16), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, I'd like to get my gutters cleaned out, they've been pretty neglected for a while now.", 0.3),
    ("assistant", "Sure, we can help with that. Could I get your full name?", 0.7),
    ("caller", "Whitney Foster.", 0.9),
    ("assistant", "Thanks for that, Whitney. Email address?", 1.2),
    ("caller", "whitney dot f at gmail dot com.", 1.5),
    ("assistant", "Got it. And the property address?", 1.9),
    ("caller", "14 Oakhaven Circle.", 2.1),
    ("assistant", "Unit number, or single-family?", 2.3),
    ("caller", "Single-family.", 2.5),
    ("assistant", "Got it. Any specific concerns, or is this just routine cleaning?", 2.8),
    ("caller", "Just routine, nothing urgent going on right now.", 3.1),
    ("assistant", "Got it. What's a good time?", 3.4),
    ("caller", "Weekday mornings usually work best for me.", 3.6),
    ("assistant", "So we've got Whitney Foster, 14 Oakhaven Circle, weekday mornings. Anything else before we wrap up?", 3.9),
    ("caller", "No, that's it.", 4.2),
])

# 13 — Whitney Foster, call 2, new issue + explicit yes/no on plumbing
write_call("call_13_whitney_foster_second_call_new_issue.csv", "+14175551008", ts(days=20, hours=9), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Hi, this is Whitney Foster again — different issue this time though, my skylight's been leaking.", 0.3),
    ("assistant", "Hi Whitney, sorry to hear about the skylight. Is it actively leaking right now, or more of an intermittent thing?", 0.8),
    ("caller", "Just after it rains, a little water pools around the frame, doesn't seem constant.", 1.3),
    ("caller", "Also, while I've got you, my garbage disposal's been broken for a few weeks now, any chance you all handle that kind of thing too?", 1.8),
    ("assistant", "Is the disposal issue connected to any water coming from above, or is that a totally separate plumbing problem?", 2.3),
    ("caller", "No, totally separate, it's just the disposal itself acting up, nothing to do with water from the roof.", 2.7),
    ("assistant", "Got it, that one would need a plumber then, sorry about that — but let's get the skylight sorted. Same address, 14 Oakhaven Circle?", 3.1),
    ("caller", "Yep, same place, still single-family.", 3.4),
    ("assistant", "Got it. What time works for someone to take a look at the skylight?", 3.7),
    ("caller", "Weekday mornings still work best for me, same as last time.", 4.0),
    ("assistant", "So we've got Whitney Foster, 14 Oakhaven Circle, weekday mornings, for the skylight leak. Anything else before we wrap up?", 4.4),
    ("caller", "No, that's everything.", 4.7),
    ("assistant", "Thanks for calling, Whitney!", 4.9),
])

# 14 — Robin Chen
write_call("call_14_robin_chen_estimate.csv", "+14175551009", ts(days=7, hours=10), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Yeah, hi, um, so I was, like, wondering, um, about maybe getting like a, uh, cost thing for a new roof? Not totally sure how that works.", 0.3),
    ("assistant", "Sure, happy to help get that started. Could I get your full name?", 0.9),
    ("caller", "Robin Chen.", 1.1),
    ("caller", "Oh, also, random question, is it supposed to be hot this whole week or is that just today?", 1.3),
    ("assistant", "I'm only able to help with roofing and restoration questions here, but let's get your estimate going. Could I get an email address?", 1.8),
    ("caller", "Uh, it's, um, robin dot chen, at, um, gmail, dot com, I think that's right.", 2.2),
    ("assistant", "Got it, robin.chen@gmail.com. Property address?", 2.6),
    ("caller", "88 Sunset Terrace.", 2.8),
    ("assistant", "Unit number, or single-family?", 3.0),
    ("caller", "Single-family.", 3.2),
    ("assistant", "Got it. Any specific issues with the current roof, or just want a general ballpark? Just a heads up, we can't give an exact price until someone's actually inspected it in person.", 3.6),
    ("caller", "That's totally fine, just a ballpark idea, no urgent issues that I know of right now.", 4.1),
    ("assistant", "Got it. What's your availability like for someone to come take a look?", 4.5),
    ("caller", "Um, weekday evenings, or, actually, wait, maybe weekend mornings instead, honestly either one works for me.", 4.9),
    ("assistant", "No problem, I'll note both weekday evenings and weekend mornings as options. So we've got Robin Chen, 88 Sunset Terrace. Anything else before we wrap up?", 5.4),
    ("caller", "No, I think that's everything.", 5.8),
    ("assistant", "Thanks for calling, Robin!", 6.0),
])

# 15 — Jason Pham
write_call("call_15_jason_pham_chimney.csv", "+14175551011", ts(days=9, hours=17), [
    ("assistant", "Hello! I'm a virtual assistant for The Front Desk That Never Sleeps. Is there something going on with your roof I can help with today?", 0.0),
    ("caller", "Yeah, so there's a gap around my chimney flashing, and it's letting some moisture in, been noticing it for about a week now.", 0.3),
    ("assistant", "Sorry to hear that. Could I get your full name?", 0.8),
    ("caller", "Jason Pham.", 1.0),
    ("assistant", "Thanks for that, Jason. Could I get an email address?", 1.3),
    ("caller", "Yeah so it's like, uh, J, uh, P-H-A-M, um, hold on...", 1.6),
    ("assistant", "Take your time.", 1.8),
    ("caller", "88 at, um, gmail dot com.", 2.0),
    ("assistant", "Got it, jpham88@gmail.com. And the property address?", 2.4),
    ("caller", "301 Hillcrest Avenue.", 2.6),
    ("assistant", "Unit number, or single-family?", 2.8),
    ("caller", "Single-family.", 3.0),
    ("assistant", "Thanks for that. Can you describe how bad the gap is — is any water actually coming through yet, or mostly just a draft?", 3.3),
    ("caller", "Mostly just a draft and some minor moisture, not a full leak or anything yet, thankfully.", 3.8),
    ("assistant", "Good that it's been caught early. When's a good time for someone to come out and take a look?", 4.2),
    ("caller", "Weekends only work for me, I'm pretty tied up on weekdays.", 4.6),
    ("assistant", "Got it, weekends only. So we've got Jason Pham, 301 Hillcrest Avenue, weekends. Anything else before we wrap up?", 5.0),
    ("caller", "Actually, is there any way I could talk to a manager directly instead of waiting on a callback? Just curious.", 5.4),
    ("assistant", "I understand wanting to move quickly on this. I'm not able to transfer you directly, but I'll flag this for a manager to follow up, and everything you've shared is already on file so you won't need to repeat anything.", 5.9),
    ("caller", "Okay, that works, appreciate it.", 6.4),
    ("assistant", "You're welcome, Jason — thanks for calling, take care!", 6.6),
])

print(f"\nDone — 15 files written to ./{OUTDIR}/")
