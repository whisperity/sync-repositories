import sys

try:
    import sshconf
except ImportError:
    print("Error! `sshconf` is a dependency, please install.",
          file=sys.stderr)
    sys.exit(-1)
