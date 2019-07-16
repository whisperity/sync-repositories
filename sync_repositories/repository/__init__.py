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
            elif subdir.endswith('.git'):
                from .git import Git

                if os.path.isdir(subdir) and os.path.islink(subdir):
                    # If the `.git` "folder" is a symbolic link, the current
                    # folder is for a Git clone that has its data storage
                    # offset, such as a submodule.
                    print("%s symbolic link - skipping \"submodules\" for now"
                          % subdir)
                elif os.path.isdir(subdir):
                    yield Git(cwd, subdir)
