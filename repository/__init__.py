import os

from .repository import Repository


def get_repositories(root):
    """
    Walk the directory tree at `root`, and produce `Repository` instances for
    found and known repositories.
    """

    for cwd, dirs, _ in os.walk(root):
        for subdir in map(lambda dir: os.path.join(cwd, dir), dirs):
            if subdir.endswith('.svn'):
                from .subversion import Subversion
                yield Subversion(cwd, subdir)
