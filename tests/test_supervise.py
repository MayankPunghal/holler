"""The supervisor restarts a crashing child and stops after a normal exit: python tests/test_supervise.py"""
import os
import sys
import tempfile

os.environ["HOLLER_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from holler import process  # noqa: E402

counter = os.path.join(os.environ["HOLLER_HOME"], "n")
child = [sys.executable, "-c",
         "import sys,os\np=sys.argv[1]\nn=int(open(p).read()) if os.path.exists(p) else 0\n"
         "open(p,'w').write(str(n+1))\nsys.exit(1 if n<2 else 0)", counter]
rc = process.supervise(cmd=child, delay=0.05)
launches = int(open(counter).read())
ok = rc == 0 and launches == 3
print("PASS" if ok else "FAIL", "| restarts after crashes, stops after a clean exit (launches=%d)" % launches)

os.remove(counter)
bad_child = [sys.executable, "-c", "import sys; sys.exit(3)"]
rc = process.supervise(cmd=bad_child, max_crashes=3, delay=0.01)
ok2 = rc == 1
print("PASS" if ok2 else "FAIL", "| gives up when the child keeps crashing")
print("ALL OK" if ok and ok2 else "FAILED")
sys.exit(0 if ok and ok2 else 1)
