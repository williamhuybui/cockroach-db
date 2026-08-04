"""
Mock data generator for The Front Desk That Never Sleeps.

Produces two linked CSVs:
  - calls.csv       one row per call (structured summary, what CockroachDB
                     endpoints read/write/update)
  - transcript.csv  one row per conversation turn (raw log, matches the
                     format main.py already writes to call_logs/, plus a
                     call_id to join back to calls.csv)

Scenarios covered (all i could think of for now):
  1. Caller called once, no follow-up               -> Mark Reynolds
  2. Caller called twice (follow-up)                  -> Denise Coleman
  3. Caller called once, then a DIFFERENT person
     calls back on that caller's behalf               -> Steven Ortiz / Priya Ortiz
  4. Multiple people, same address, different unit     -> Angela Kim / Marcus Webb
  5. Single urgent/emergency call                       -> Latoya Brooks
  6. Caller called three times (initial + 2 follow-ups) -> Carlos Mendez
  7. Plain single non-emergency call                    -> Robin Chen, Jason Pham (single-call baseline)
  8. Repeat caller, different problem each time         -> Whitney Foster
"""
import csv
from datetime import datetime, timedelta

BASE = datetime(2026, 7, 28, 8, 0, 0)

def ts(days=0, hours=0, minutes=0):
    return (BASE + timedelta(days=days, hours=hours, minutes=minutes)).isoformat()

calls = []
transcript = []

def add_call(call_id, caller_number, timestamp, name, email, address, problem,
             problem_detail, availability, urgency, previous_call_id="", calling_on_behalf_of=""):
    calls.append({
        "call_id": call_id, "caller_number": caller_number, "timestamp": timestamp,
        "name": name, "email": email, "address": address, "problem": problem,
        "problem_detail": problem_detail, "availability": availability,
        "urgency": urgency, "previous_call_id": previous_call_id,
        "calling_on_behalf_of": calling_on_behalf_of,
    })

def add_turns(call_id, caller_number, start_ts, lines):
    """lines: list of (speaker, text, minute_offset)"""
    for speaker, text, offset in lines:
        t = (datetime.fromisoformat(start_ts) + timedelta(minutes=offset)).isoformat()
        transcript.append({
            "call_id": call_id, "timestamp": t, "caller_number": caller_number,
            "speaker": speaker, "text": text,
        })

# 1. Mark Reynolds — single call, no follow-up, routine
t1 = ts(days=0, hours=9, minutes=0)
add_call("C001", "+14175551001", t1, "Mark Reynolds", "mreynolds@gmail.com",
          "412 Cascade Ave, Springfield, MO", "Roof leak",
          "Small drip in the attic near the chimney, started after last week's storm",
          "Weekday afternoons after 4pm", "Medium")
add_turns("C001", "+14175551001", t1, [
    ("assistant", "Thanks for calling, this is the front desk — what can I help with?", 0.0),
    ("caller", "Hi, I've got a leak in my attic, started last week during the storm.", 0.3),
    ("assistant", "Sorry to hear that. Can I get your name and the address?", 0.6),
    ("caller", "Mark Reynolds, 412 Cascade Ave.", 0.9),
    ("assistant", "Got it. What's the best time for someone to come look?", 1.2),
    ("caller", "Weekday afternoons after 4pm work best.", 1.5),
])

# 2. Denise Coleman — calls twice (initial + follow-up)
t2a = ts(days=1, hours=10, minutes=0)
add_call("C002", "+14175551002", t2a, "Denise Coleman", "d.coleman@outlook.com",
          "77 Maplewood Dr, Springfield, MO", "Shingle damage",
          "Several shingles missing on the south-facing slope after high winds",
          "Mornings before 11am", "Medium")
add_turns("C002", "+14175551002", t2a, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "A bunch of shingles blew off my roof yesterday.", 0.3),
    ("assistant", "I can help with that. Name and address?", 0.6),
    ("caller", "Denise Coleman, 77 Maplewood Dr.", 0.9),
    ("assistant", "When's a good time for an estimate?", 1.2),
    ("caller", "Mornings before 11 work for me.", 1.5),
])
t2b = ts(days=4, hours=9, minutes=30)
add_call("C003", "+14175551002", t2b, "Denise Coleman", "d.coleman@outlook.com",
          "77 Maplewood Dr, Springfield, MO", "Shingle damage (follow-up)",
          "Calling to check status on the estimate from earlier in the week",
          "Mornings before 11am", "Low", previous_call_id="C002")
add_turns("C003", "+14175551002", t2b, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "Hi, it's Denise Coleman again, calling about my roof from earlier this week.", 0.3),
    ("assistant", "Yes, I see your call from Tuesday about the shingle damage. Let me check on the estimate status for you.", 0.6),
    ("caller", "Great, just wanted to make sure it wasn't forgotten.", 1.0),
])

# 3. Steven Ortiz — initial call, then Priya Ortiz calls back ON HIS BEHALF
t3a = ts(days=2, hours=13, minutes=0)
add_call("C004", "+14175551003", t3a, "Steven Ortiz", "steven.ortiz@yahoo.com",
          "205 Fieldstone Ct, Springfield, MO", "Roof replacement inquiry",
          "20-year-old roof, wants a full replacement quote",
          "Weekends", "Low")
add_turns("C004", "+14175551003", t3a, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "Hi, I'm looking into getting my roof replaced, it's pretty old.", 0.3),
    ("assistant", "Sure, can I get your name and address?", 0.6),
    ("caller", "Steven Ortiz, 205 Fieldstone Ct.", 0.9),
    ("assistant", "And when works for a visit?", 1.2),
    ("caller", "Weekends are easiest for me.", 1.5),
])
t3b = ts(days=5, hours=11, minutes=0)
add_call("C005", "+14175551010", t3b, "Priya Ortiz", "priya.ortiz@yahoo.com",
          "205 Fieldstone Ct, Springfield, MO", "Roof replacement inquiry (on behalf of Steven Ortiz)",
          "Calling on behalf of her husband Steven Ortiz to confirm the quote appointment",
          "Weekends", "Low", previous_call_id="C004", calling_on_behalf_of="Steven Ortiz")
add_turns("C005", "+14175551010", t3b, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "Hi, I'm calling on behalf of my husband Steven Ortiz, he called earlier this week about a roof replacement quote.", 0.3),
    ("assistant", "Yes, I have his call on file from Thursday. I can note you as an additional contact — what's your name?", 0.6),
    ("caller", "Priya Ortiz. Just wanted to confirm the weekend appointment still works.", 1.0),
])

# 4. Angela Kim (2B) and Marcus Webb (4C) — same building, different units
t4a = ts(days=3, hours=8, minutes=0)
add_call("C006", "+14175551004", t4a, "Angela Kim", "angela.kim@gmail.com",
          "118 Birchwood Ln, Apt 2B, Springfield, MO", "Storm damage",
          "Water stain spreading across the bedroom ceiling after last night's storm",
          "Any weekday", "High")
add_turns("C006", "+14175551004", t4a, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "There's a big water stain on my ceiling, it's getting bigger.", 0.3),
    ("assistant", "That sounds urgent — can I get your name and unit number?", 0.6),
    ("caller", "Angela Kim, 118 Birchwood Lane, Apartment 2B.", 0.9),
    ("assistant", "Is the water actively dripping right now?", 1.2),
    ("caller", "Not dripping yet, just the stain spreading.", 1.5),
])
t4b = ts(days=3, hours=8, minutes=45)
add_call("C007", "+14175551005", t4b, "Marcus Webb", "mwebb22@gmail.com",
          "118 Birchwood Ln, Apt 4C, Springfield, MO", "Gutter damage",
          "Gutter partially torn off the building during last night's storm, hanging loose",
          "Evenings after 6pm", "Medium")
add_turns("C007", "+14175551005", t4b, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "My gutter's hanging off after the storm last night.", 0.3),
    ("assistant", "Got it — name and unit?", 0.6),
    ("caller", "Marcus Webb, same building as a neighbor I think, Apartment 4C, 118 Birchwood Lane.", 0.9),
    ("assistant", "Thanks. When's a good time to take a look?", 1.2),
    ("caller", "Evenings after 6 work best.", 1.5),
])

# 5. Latoya Brooks — single urgent/emergency call
t5 = ts(days=6, hours=22, minutes=15)
add_call("C008", "+14175551006", t5, "Latoya Brooks", "l.brooks@hotmail.com",
          "930 Crestline Dr, Springfield, MO", "Active roof leak",
          "Water actively coming through the living room ceiling during tonight's storm, buckets out",
          "ASAP / tonight", "Emergency")
add_turns("C008", "+14175551006", t5, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "Water is pouring through my ceiling right now, I need someone tonight!", 0.2),
    ("assistant", "Understood, this is urgent. Name and address?", 0.4),
    ("caller", "Latoya Brooks, 930 Crestline Drive.", 0.6),
    ("assistant", "I'm flagging this as an emergency and getting someone to call you back within the hour.", 0.8),
    ("caller", "Please hurry, I've got buckets out but it's getting worse.", 1.0),
])

# 6. Carlos Mendez — three calls (initial + two follow-ups)
t6a = ts(days=0, hours=14, minutes=0)
add_call("C009", "+14175551007", t6a, "Carlos Mendez", "carlos.mendez@gmail.com",
          "56 Ridgeline Way, Springfield, MO", "Roof inspection request",
          "Wants a general inspection before selling the house, no known active damage",
          "Flexible", "Low")
add_turns("C009", "+14175551007", t6a, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "I'm selling my house and want the roof inspected first.", 0.3),
    ("assistant", "Sure thing, name and address?", 0.6),
    ("caller", "Carlos Mendez, 56 Ridgeline Way.", 0.9),
])
t6b = ts(days=3, hours=15, minutes=0)
add_call("C010", "+14175551007", t6b, "Carlos Mendez", "carlos.mendez@gmail.com",
          "56 Ridgeline Way, Springfield, MO", "Roof inspection (follow-up)",
          "Following up to schedule the actual inspection date", "Flexible", "Low",
          previous_call_id="C009")
add_turns("C010", "+14175551007", t6b, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "Hi, Carlos Mendez again, following up on the inspection I asked about.", 0.3),
    ("assistant", "Yes, I have that on file — let's get a date on the calendar.", 0.6),
    ("caller", "Anytime next week works.", 1.0),
])
t6c = ts(days=8, hours=16, minutes=0)
add_call("C011", "+14175551007", t6c, "Carlos Mendez", "carlos.mendez@gmail.com",
          "56 Ridgeline Way, Springfield, MO", "Roof inspection (confirmation)",
          "Confirming the inspection appointment that was scheduled", "Flexible", "Low",
          previous_call_id="C010")
add_turns("C011", "+14175551007", t6c, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "Just calling to confirm my inspection is still on for this week.", 0.3),
    ("assistant", "Yes, confirmed for Thursday morning.", 0.6),
    ("caller", "Perfect, thank you.", 0.9),
])

# 7. Whitney Foster — repeat caller, DIFFERENT problem each time (not a true follow-up)
t7a = ts(days=1, hours=16, minutes=0)
add_call("C012", "+14175551008", t7a, "Whitney Foster", "whitney.f@gmail.com",
          "14 Oakhaven Cir, Springfield, MO", "Gutter cleaning",
          "Routine gutter cleaning request, no damage", "Weekday mornings", "Low")
add_turns("C012", "+14175551008", t7a, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "I'd like to get my gutters cleaned out.", 0.3),
    ("assistant", "Sure — name and address?", 0.6),
    ("caller", "Whitney Foster, 14 Oakhaven Circle.", 0.9),
])
t7b = ts(days=20, hours=9, minutes=0)
add_call("C013", "+14175551008", t7b, "Whitney Foster", "whitney.f@gmail.com",
          "14 Oakhaven Cir, Springfield, MO", "Skylight leak",
          "New, unrelated issue — skylight seal leaking after recent rain", "Weekday mornings", "Medium")
add_turns("C013", "+14175551008", t7b, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "This is Whitney Foster again — different issue this time, my skylight's leaking.", 0.3),
    ("assistant", "Got it, noted as a new issue. When works for a look?", 0.6),
    ("caller", "Weekday mornings still work best.", 1.0),
])

# 8. Robin Chen & Jason Pham — plain single-call baselines
t8 = ts(days=7, hours=10, minutes=0)
add_call("C014", "+14175551009", t8, "Robin Chen", "robin.chen@gmail.com",
          "88 Sunset Terrace, Springfield, MO", "New roof cost estimate",
          "Wants a ballpark cost estimate for a full re-roof, no urgency", "Weekday evenings", "Low")
add_turns("C014", "+14175551009", t8, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "I just want a ballpark on what a new roof would cost.", 0.3),
    ("assistant", "Happy to help — name and address for the estimate?", 0.6),
    ("caller", "Robin Chen, 88 Sunset Terrace.", 0.9),
])

t9 = ts(days=9, hours=17, minutes=0)
add_call("C015", "+14175551011", t9, "Jason Pham", "jpham88@gmail.com",
          "301 Hillcrest Ave, Springfield, MO", "Chimney flashing repair",
          "Small gap around chimney flashing letting in draft and minor moisture", "Weekends only", "Medium")
add_turns("C015", "+14175551011", t9, [
    ("assistant", "Front desk, how can I help?", 0.0),
    ("caller", "There's a gap around my chimney flashing, letting some moisture in.", 0.3),
    ("assistant", "Name and address, please?", 0.6),
    ("caller", "Jason Pham, 301 Hillcrest Avenue.", 0.9),
    ("assistant", "And when's a good time to come out?", 1.2),
    ("caller", "Weekends only for me.", 1.5),
])

# --- Write CSVs ---
calls_fields = ["call_id", "caller_number", "timestamp", "name", "email", "address",
                 "problem", "problem_detail", "availability", "urgency",
                 "previous_call_id", "calling_on_behalf_of"]
with open("calls.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=calls_fields)
    w.writeheader()
    w.writerows(calls)

transcript_fields = ["call_id", "timestamp", "caller_number", "speaker", "text"]
with open("transcript.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=transcript_fields)
    w.writeheader()
    w.writerows(transcript)

print(f"Wrote {len(calls)} calls and {len(transcript)} transcript turns.")
