from __future__ import annotations

from typing import Final

from tests.airgap.fork_diff import _added_lines

PATCH: Final = """diff --git a/litellm/a.py b/litellm/a.py
index 1..2 100644
--- a/litellm/a.py
+++ b/litellm/a.py
@@ -3,0 +4,2 @@ def f():
+x = 1
+y = 2
@@ -10 +12 @@ def g():
-old
+new
@@ -20,3 +23,0 @@ def h():
-gone
diff --git a/litellm/new.py b/litellm/new.py
new file mode 100644
--- /dev/null
+++ b/litellm/new.py
@@ -0,0 +1,3 @@
+a
+b
+c
diff --git a/litellm/deleted.py b/litellm/deleted.py
deleted file mode 100644
--- a/litellm/deleted.py
+++ /dev/null
@@ -1,2 +0,0 @@
-a
-b
"""


def test_added_lines_follow_each_hunk_of_each_file() -> None:
    assert _added_lines(PATCH) == {
        "litellm/a.py": frozenset({4, 5, 12}),
        "litellm/new.py": frozenset({1, 2, 3}),
    }


def test_no_patch_means_no_added_lines() -> None:
    assert _added_lines("") == {}
