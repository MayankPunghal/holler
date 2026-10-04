from holler.cleanup import clean

CASES = [
    ("Today is Monday, no, no, wait, today is Tuesday.", "Today is Tuesday."),
    ("Today is Monday no wait Tuesday", "Today is Tuesday"),
    ("Um, I want to uh book a flight to Delhi, sorry, I mean Mumbai.", "I want to book a flight to Mumbai."),
    ("Meet me at 3, no wait, 4 pm", "Meet me at 4 pm"),
    ("Meet at 3 no wait 4 no wait 5", "Meet at 5"),
    ("Send the report to John scratch that send it to Priya", "Send it to Priya"),
    ("I went to the store, no no no wait, the market.", "I went to the market."),
    ("So um yeah uh that's it", "So yeah that's it"),
    ("I I think the the plan works", "I think the plan works"),
    ("No, I don't want that.", "No, I don't want that."),
    ("I mean, it works fine.", "I mean, it works fine."),
    ("It is fine. Send it now. Actually no, send it tomorrow.", "It is fine. Send it tomorrow."),
    ("I'm going home. No wait, to work.", "I'm going home. To work."),  # too ambiguous: keeps both
    ("Book it for Monday, make that Tuesday", "Book it for Tuesday"),
    ("Call Rahul oops Rohit", "Call Rohit"),
    ("The meeting is at 5, hang on, 6 pm", "The meeting is at 6 pm"),
    ("Today is Wednesday. No, no, quick. Today is Monday. And it is 9.7 a.m. right now.", "Today is Monday. And it is 9.7 a.m. right now."),
    ("No, no, I don't think that works", "No, no, I don't think that works"),
    ("No no that is fine", "No no that is fine"),
    ("Today is Wednesday. No, no, wait. Today is Monday. And it is 9:01 AM. No, my bad. It is 9:27 AM right now. And I'm working on my video generation.", "Today is Monday. And it is 9:27 AM right now. And I'm working on my video generation."),
    ("Today is Sunday. It's 9.35am. Okay, wait, it's 9.52am right now. And I'm working on my video generation.", "Today is Sunday. It's 9.52am right now. And I'm working on my video generation."),
    ("Wait for the build to finish, then wait for the tests.", "Wait for the build to finish, then wait for the tests."),
    ("Wait, what is the status of the deployment?", "Wait, what is the status of the deployment?"),
    ("Hold on to the reference until the request completes.", "Hold on to the reference until the request completes."),
    ("Set the Lambda Timeout to 30 seconds, sorry, 300 seconds, and bump the memory to 512 MB.", "Set the Lambda Timeout to 300 seconds, and bump the memory to 512 MB."),
    ("It is 9.35am, sorry, 9.52am right now.", "It is 9.52am right now."),
    ("I need 3 items, I mean 5 items.", "I need 5 items."),
    ("Set the timeout to 30 seconds, sorry, the memory to 512 MB.", "Set the timeout to 30 seconds, sorry, the memory to 512 MB."),
    ("We have 3 servers, sorry about that, 5 users reported errors.", "We have 3 servers, sorry about that, 5 users reported errors."),
    ("", ""),
]

bad = 0
for src, want in CASES:
    got = clean(src)
    ok = got == want
    bad += not ok
    print(("PASS" if ok else "FAIL"), "|", src, "->", got, "" if ok else f"   (wanted: {want})")
raise SystemExit(bad)
