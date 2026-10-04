"""Spoken commands, smart formatting and vocabulary suggestions: python tests/test_spoken.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from holler.spoken import apply_commands, smart_format  # noqa: E402
from holler.suggest import suggest  # noqa: E402

bad = 0


def check(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print("PASS" if ok else "FAIL", "|", name, "" if ok else f"\n   got:  {got!r}\n   want: {want!r}")


def full(t):
    return smart_format(apply_commands(t))


check("new paragraph", full("Dear team, new paragraph, thanks all."), "Dear team\n\nThanks all.")
check("question mark", full("Are you coming, question mark"), "Are you coming?")
check("brackets", full("open bracket, see note, close bracket."), "(see note).")
check("in-sentence phrase untouched", full("Add a new line to the file."), "Add a new line to the file.")
check("the word period inside a sentence", full("The period of the loop is short."), "The period of the loop is short.")
check("colon", full("Total, colon, five hundred rupees"), "Total: ₹500")
check("percent words", full("It grew by twenty five percent"), "It grew by 25%")
check("percent hyphen", full("twenty-five percent."), "25%.")
check("decimal percent", full("three point five percent"), "3.5%")
check("hundred and", full("one hundred and twenty percent!"), "120%!")
check("rupees digits", full("pay 500 rupees"), "pay ₹500")
check("dollars comma", full("two thousand and five dollars"), "$2,005")
check("lakh kept", full("five lakh rupees"), "₹5 lakh")
check("plain numbers untouched", full("I have two apples and 3 pears"), "I have two apples and 3 pears")
check("email", full("send to john at example dot com please"), "send to john@example.com please")
check("filename", full("edit main dot py now"), "edit main.py now")
check("url path", full("visit github dot com slash holler slash docs now"), "visit github.com/holler/docs now")
check("'at' alone untouched", full("meet me at the office"), "meet me at the office")
check("command ending a clause", full("It grew by 25% new paragraph, send it to john"), "It grew by 25%\n\nSend it to john")
check("domain dots survive", full("Edit Program.cs, new line, then run it"), "Edit Program.cs\nThen run it")
check("'the question mark' is talked about", full("I forgot the question mark."), "I forgot the question mark.")
check("email with .com already written", full("The email reads John at example.com"), "The email reads john@example.com")
check("at the rate", full("john at the rate example dot com"), "john@example.com")
check("'look at google.com' untouched", full("Look at google.com"), "Look at google.com")
check("at the rate with commas", full("Send it to john, at the rate, example dot com"), "Send it to john@example.com")
check("at the rate of", full("john at the rate of gmail.com"), "john@gmail.com")
check("fused address in email context", full("Send it to johnatexample.com."), "Send it to john@example.com.")
check("dropped 'at' after email words", full("My email id is john.example.com"), "My email id is john@example.com")
check("dotted domain elsewhere untouched", full("Open mail.google.com now"), "Open mail.google.com now")
check("email id glued to the address", full("Send the email to emailidjohnatexample.com"), "Send the email to john@example.com")
check("stand-alone exclamation", full("This is really fun. Exclamation."), "This is really fun!")
check("'I said new paragraph' is talked about", full("I said new paragraph, not that."), "I said new paragraph, not that.")
check("fused address outside email context", full("Visit whatever.com today"), "Visit whatever.com today")

d = tempfile.mkdtemp()
log = os.path.join(d, "log.tsv")
with open(log, "w", encoding="utf-8") as f:
    for i in range(5):
        f.write(f"t\traw\tWe deploy with ZorbApi and use order_id here {i}.\n")
    f.write("t\traw\tOnce we saw Quuxer here.\n")
got = dict(suggest(log, ["kubernetes"]))
check("suggests repeated unusual terms", sorted(got), ["ZorbApi", "order_id"])
check("skips known terms", dict(suggest(log, ["~ZorbApi"])).get("ZorbApi"), None)

from holler.vocab import Vocab  # noqa: E402
from holler.suggest import auto_add  # noqa: E402
vd = tempfile.mkdtemp()
v = Vocab(vd)
check("auto_add adds glossary-only terms", sorted(auto_add(log, v)), ["ZorbApi", "order_id"])
check("auto_add is idempotent", auto_add(log, v), [])
check("auto terms are glossary-only", "~ZorbApi" in v.keyword_list(), True)

print("ALL OK" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
