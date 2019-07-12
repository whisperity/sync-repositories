import subprocess
import sys
import urllib.parse

try:
    import svn.local
except ImportError:
    import sys
    print("Error! `svn` Python package is a dependency, please install.",
          file=sys.stderr)
    raise

from .repository import Repository, Updater


class Subversion(Repository):
    class UsernamePasswordUpdater(Updater):
        """
        Updates a Subversion repository working copy with optionally providing
        username and password authentication to the server.
        """

        def __init__(self, repository, username=None, password=None):
            super().__init__(repository)

            if username is None and password is None:
                self._credentials = False
            elif username is not None and password is not None:
                self._credentials = True
            else:
                raise ValueError(
                    "Call update() for SVN repositories with either "
                    "both username and password, or none of it.")

            self._username = username
            self._password = password

        def update(self):
            command = ['svn', 'update', '--non-interactive', '--no-auth-cache']
            pwd = ''

            if self._credentials:
                command.append('--username')
                command.append(self._username)
                pwd = self._password + '\n'

            # Create the updater process.
            path = self._repository.path
            try:
                print("Updating '%s'..." % path)
                proc = subprocess.run(command,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      input=pwd if pwd else None,
                                      encoding='utf-8',
                                      cwd=path,
                                      check=True)
                print(proc.stdout)
                return True
            except subprocess.CalledProcessError as cpe:
                print("Update failed for '%s':" % path, file=sys.stderr)
                print(cpe.output, file=sys.stderr)
                print(str(cpe), file=sys.stderr)
                return False

    def __init__(self, path, datadir):
        super().__init__(path, datadir, 'svn')

        # Fetch the remote URL for the repository.
        try:
            repo = svn.local.LocalClient(path)
            # from pprint import pprint
            # pprint(repo.info())
            self.urls = [('root', repo.info()['repository/root'])]
        except (OSError, AttributeError):
            print("Error! The repository could not be understood by 'svn' "
                  "Python wrapper...", file=sys.stderr)
            raise

    def get_authentication_method(self, remote):
        # If SVN repositories authenticate, they only authenticate with
        # username-password combination.
        return 'keyring'

    def get_remote_objname(self, remote):
        # Use the repository's path under the server as the "object name".
        return urllib.parse.urlparse(self.urls[0][1]).path

    def get_updater_for(self, remote):
        def _factory(username, password):
            return Subversion.UsernamePasswordUpdater(self, username, password)
        return _factory
