from copy import deepcopy
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

from credentials import Backends
from .repository import AuthenticationRequirementChecker, Repository, Updater


class Subversion(Repository):
    class UsernamePasswordAuthenticationChecker(
            AuthenticationRequirementChecker):
        """
        Checks whether the given SVN repository needs authentication.
        """
        def __init__(self, repository, username=None, password=None):
            super().__init__(repository)

            if username is None and password is None:
                self._credentials = False
            elif username is not None and password is not None:
                self._credentials = True
            else:
                raise ValueError("Authentication check for SVN repositories "
                                 "with either both username and password, or "
                                 "none of it.")

            self._username = username
            self._password = password

        def _fun(self):
            # The "non-interactive" stops the called SVN binary from asking
            # authentication details and turns it into a hard fail.
            command = ['svn', 'log', '--limit', str(1),
                       '--no-auth-cache', '--non-interactive']
            original_command = command
            if self._credentials:
                command.append('--username')
                command.append(self._username)

                # Make sure we don't leak the password.
                original_command = deepcopy(command)

                command.append('--password')
                command.append(self._password)

            try:
                subprocess.run(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               encoding='utf-8',
                               cwd=self._repository.path,
                               check=True)
                return False
            except subprocess.CalledProcessError as cpe:
                if "Authentication failed" in cpe.output:
                    return True
                raise subprocess.CalledProcessError(cpe.returncode,
                                                    original_command,
                                                    cpe.output,
                                                    cpe.stderr)

        def check(self):
            return self._fun()

        def check_credentials(self):
            if not self._credentials:
                raise NotImplementedError()

            # Need to invert the result here, because _fun() returns whether
            # authentication is needed. If credentials are supplied, then the
            # method will return False (as in "no authentication needed").
            # (Same result happens if the credentials are invalid on a server
            # that doesn't need them.)
            return not self._fun()

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
            command = ['svn', 'update',
                       '--no-auth-cache', '--non-interactive']
            original_command = command
            if self._credentials:
                command.append('--username')
                command.append(self._username)

                # Make sure we don't leak the password.
                original_command = deepcopy(command)

                command.append('--password')
                command.append(self._password)

            # Create the updater process.
            path = self._repository.path
            try:
                print("Updating '%s'..." % path)
                proc = subprocess.run(command,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      encoding='utf-8',
                                      cwd=path,
                                      check=True)
                print(proc.stdout)
                return True
            except subprocess.CalledProcessError as cpe:
                try:
                    # Raise an exception in which the password isn't shown.
                    raise subprocess.CalledProcessError(cpe.returncode,
                                                        original_command,
                                                        cpe.output,
                                                        cpe.stderr)
                except subprocess.CalledProcessError as cpe2:
                    print("Update failed for '%s':" % path, file=sys.stderr)
                    print(cpe2.output, file=sys.stderr)
                    print(str(cpe2), file=sys.stderr)
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
        return Backends.KEYRING

    def get_remote_objname(self, remote):
        # Use the repository's path under the server as the "object name".
        return urllib.parse.urlparse(self.urls[0][1]).path

    def get_auth_requirement_detector_for(self, remote):
        def _factory(username=None, password=None):
            return Subversion.UsernamePasswordAuthenticationChecker(self,
                                                                    username,
                                                                    password)
        return _factory

    def get_updater_for(self, remote):
        def _factory(username, password):
            return Subversion.UsernamePasswordUpdater(self, username, password)
        return _factory
