import difflib


def abci_diff(s1, s2):
    """
    A tool for visualizing difference of two ABCi, namely s1 and s2.

    Use the compare() method to calculate differences between the two strings
    compare() returns a generator of strings indicating differences per line
    Each line is prefixed to indicate the type of difference:
      '  ' (two spaces): unchanged line
      '+ ' (plus): line present only in the second string
      '- ' (minus): line present only in the first string
      '? ' (question mark): characters changed within a line (optional)

    Args:
        s1 (str): First ABCi text
        s2 (str): Second ABCi text

    """
    # Create a difflib.Differ object
    d = difflib.Differ()

    diff = list(d.compare(s1.splitlines(), s2.splitlines()))

    print("--- Differences between the two strings ---")
    for line in diff:
        print(line)
