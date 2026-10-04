import os, shutil, tempfile
from holler.vocab import Vocab, diff_pairs, align
from holler.paths import PACKAGE_DATA

here = os.path.dirname(os.path.abspath(__file__))
bad = 0
def check(name, got, want):
    global bad
    ok = got == want
    bad += not ok
    print(("PASS" if ok else "FAIL"), "|", name, "" if ok else f"\n   got:  {got!r}\n   want: {want!r}")

# ---- seeded vocabulary on the real files (the sentences from the real-world test)
seed = tempfile.mkdtemp()
v = Vocab(seed, PACKAGE_DATA)      # first run copies the shipped examples
A = v.apply
check("refactor/asp.net/scoped",
      A("Pre-factor this asb.net core minimal API endpoint to use dependency injection and register the service as scopedinprogram.cs"),
      "Refactor this ASP.NET Core minimal API endpoint to use dependency injection and register the service as scoped in Program.cs")
check("moq/xunit/null reference",
      A("Add unit tests with XUnit and Mach for the order service class, covering the null difference case and the timeout exception."),
      "Add unit tests with xUnit and Moq for the order service class, covering the null reference case and the timeout exception.")
check("system.web/httpcontext", A("This legacy code uses system.web and http-context.current. So, what will break"),
      "This legacy code uses System.Web and HttpContext.Current. So, what will break")
check("dtos", A("keep the existing data contracts as details."), "keep the existing data contracts as DTOs.")
check("dockerfile", A("Try to Docker for a .NET 8 application that targets Linux"), "Write a Dockerfile for a .NET 8 application that targets Linux")
check("dotnet casing", A("move it to .net 8 on aws"), "move it to .NET 8 on AWS")
check("REST untouched", A("take a rest, then test the rest api"), "take a rest, then test the rest api")
check("ordinary words untouched", A("the lambda function is in the program"), "the lambda function is in the program")
check("prompt keeps newest last", v.prompt_terms(80)[-1], "Anthropic")

check("align finds the sentence inside a line",
      align("Please add a Mach for the repository and run it.",
            "Earlier text. Please add a Moq for the repository and run it. More words after that"),
      "Please add a Moq for the repository and run it.")
check("align leaves a short selection alone", align("Use Mach for mocking.", "Use Moq for mocking."), "Use Moq for mocking.")

# ---- learning, on a throwaway folder
d = tempfile.mkdtemp()
try:
    for f in ("keywords.txt", "replacements.txt"):
        open(os.path.join(d, f), "w").write("")
    L = Vocab(d)
    r1 = L.learn_from_edit("Add tests with XUnit and Mach for the order service.", "Add tests with xUnit and Moq for the order service.")
    check("first single-word correction is only noted", [m.split(":")[0] for m in r1], ["noted once", "learned spelling"])
    check("not applied yet", L.apply("with Mach here"), "with Mach here")
    r2 = L.learn_from_edit("Use Mach for mocking.", "Use Moq for mocking.")
    check("second confirmation learns it", r2, ["learned: Mach -> Moq"])
    check("applied now", L.apply("with Mach here"), "with Moq here")
    r3 = L.learn_from_edit("covering the null difference case", "covering the null reference case")
    check("phrase with neighbour learned at once", r3[0].startswith("learned: null difference -> null reference; noted once"), True)
    check("phrase rule applies at once", L.apply("the null difference case"), "the null reference case")
    check("bare word not touched yet", L.apply("the difference between them"), "the difference between them")
    check("kw added", "Moq" in L.keywords and "xUnit" in L.keywords, True)
    r4 = L.learn_from_edit("keep contracts as details and more", "keep contracts as DTOs and more")
    check("single word, once only", r4[0].startswith("noted once"), True)
    check("not applied on first sight", L.apply("see the details"), "see the details")
    check("unrelated edit rejected", L.learn_from_edit("hello there my friend", "completely different sentence about trains"), None)
    # hand edits are picked up
    open(os.path.join(d, "replacements.txt"), "a").write("foo bar => Baz\n"); L.refresh_if_changed()
    check("hand edits reload", L.apply("a foo bar b"), "a Baz b")
    # file stays well-formed and appends on its own line
    open(os.path.join(d, "keywords.txt"), "w", newline="").write("No newline at end")
    L.add_keyword("NuGet")
    check("append after missing newline", [l.strip() for l in open(os.path.join(d, "keywords.txt"))], ["No newline at end", "NuGet"])
finally:
    shutil.rmtree(d)

check("diff: identifier-style casing only", diff_pairs("use xunit here", "use xUnit here"), ([], ["xUnit"]))
check("diff: sentence case ignored", diff_pairs("use it here", "Use it here"), ([], []))
raise SystemExit(bad)
