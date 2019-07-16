import os
import subprocess
import sys
import urllib.parse

try:
    import git
except ImportError:
    import sys
    print("Error! `GitPython` is a dependency, please install.",
          file=sys.stderr)
    raise


from credentials import auto_askpass
from credentials import Backends
from .repository import AuthenticationRequirementChecker, Repository, Updater


class Git(Repository):
    class UsernamePasswordAuthenticationChecker(
            AuthenticationRequirementChecker):
        """
        Checking engine for Git repositories that might use username-password
        based HTTP(S) authentication.
        """

        def __init__(self, repository, remote, parts,
                     username=None, password=None):
            super().__init__(repository)
            self._remote = remote
            self._parts = parts

            if username is None and password is None:
                self._credentials = False
            elif username is not None and password is not None:
                self._credentials = True
            else:
                raise ValueError("Authentication check for Git HTTP "
                                 "repositories with either both username and "
                                 "password, or none of it.")

            self._username = username
            self._password = password

        def _fun(self):
            command = ['git', 'remote', 'show', self._remote]

            # Create an 'askpass' wrapper that will always return invalid, but
            # if asked to return something, will signal us through a control
            # file.
            if not self._credentials:
                env = auto_askpass.create(*self._parts)
            else:
                env = auto_askpass.create_with_credentials(self._username,
                                                           self._password,
                                                           *self._parts)

            try:
                subprocess.run(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               encoding='utf-8',
                               cwd=self._repository.path,
                               check=True,
                               env=env)
                # If the call above succeeds, the repository did not need
                # authentication.
                return False
            except subprocess.CalledProcessError as cpe:
                if "Authentication failed" in cpe.output:
                    return True
                raise

        def check(self):
            return self._fun()

        def check_credentials(self):
            return not self._fun()

    class UsernamePasswordWrappingUpdater(Updater):
        """
        Updates a Git repository clone with optionally providing
        username and password authentication to the updater executable.
        """

        def __init__(self, repository, remote, parts):
            super().__init__(repository)
            self._remote = remote
            self._parts = parts

        def update(self):
            update = 'update' if self._repository.custom_update_command \
                else 'fetch'
            command = ['git', update, self._remote]

            # Wrap the authentication details into a dummy script, as Git
            # updating with username and password asks from an inner process,
            # and we can't feed STDIN into it.
            env = auto_askpass.create(*self._parts)

            # Create the updater process.
            path = self._repository.path
            try:
                print("Updating '%s'..." % path)
                proc = subprocess.run(command,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      encoding='utf-8',
                                      cwd=path,
                                      check=True,
                                      env=env)
                print(proc.stdout)
                return True
            except subprocess.CalledProcessError as cpe:
                print("Update failed for '%s':" % path, file=sys.stderr)
                print(cpe.output, file=sys.stderr)
                print(str(cpe), file=sys.stderr)
                return False

    def __init__(self, path, datadir):
        super().__init__(path, datadir, 'git')

        # Check the repository's configuration on how it shall be updated.
        repo = git.Repo(datadir)
        self.urls = []
        self._auth_methods = {}  # Parse authentication methods for remotes.
        for remote in repo.remotes:
            for url in remote.urls:
                parsed = urllib.parse.urlparse(url)
                if parsed.scheme in ['http', 'https', 'ftp', 'ftps']:
                    # HTTP and FTP protocol may authenticate with
                    # username-password.
                    self._auth_methods[remote.name] = Backends.KEYRING
                elif parsed.scheme in ['git', 'file']:
                    # The old-style Git and local-clone file protocol does not
                    # authenticate.
                    self._auth_methods[remote.name] = None
                else:
                    if not parsed.netloc and parsed.scheme:
                        # If "netloc" wasn't parsed, the repository URL is
                        # using the 'example.org:foobar.git' shorthand syntax
                        # for 'ssh://example.org/foobar.git'.
                        url = 'ssh://' + parsed.scheme + '/' + parsed.path
                    self._auth_methods[remote.name] = Backends.SSH_AGENT

                self.urls.append((remote.name, url))

        self.urls = sorted(self.urls)

        # Try to see if the user has a custom 'update' command alias in their
        # Git config.
        # (To ensure this works as it would in a Shell, we need to load every
        # configuration script, not just the repository's own.)
        config_command = ['git', 'config', '--get', 'alias.update']
        try:
            subprocess.check_output(config_command, cwd=self.path)
            self.custom_update_command = True
        except subprocess.CalledProcessError:
            self.custom_update_command = False

    def get_authentication_method(self, remote):
        return self._auth_methods[remote]

    def get_remote_objname(self, remote):
        # Return the path on the Git server to the repository.
        url = next(filter(lambda r: r[0] == remote, self.urls))[1]
        parsed = urllib.parse.urlparse(url)
        return parsed.path if parsed.path else ""

    def get_auth_requirement_detector_for(self, remote):
        method = self._auth_methods[remote]

        if method is None:
            class _cls():
                """
                An authentication validator that always validates everything
                for the case when no authentication is to be done.
                """

                def check(self):
                    return False

                def check_credentials(self):
                    return True

            def _factory():
                return _cls()
        elif method == Backends.KEYRING:
            def _factory(username=None, password=None):
                return Git.UsernamePasswordAuthenticationChecker(
                    self, remote, self.get_remote_parts(remote)[1],
                    username, password)
        else:
            class _cls():
                """
                An authentication validator that always validates everything
                for the case when no authentication is to be done.
                """

                def check(self):
                    return False

                def check_credentials(self):
                    return True

            def _factory():
                return _cls()
            # raise NotImplementedError("Not implemented for %s" % remote)

        return _factory

    def get_updater_for(self, remote):
        method = self._auth_methods[remote]
        if method is None or method == Backends.KEYRING:
            def _factory(username, password):
                # This function conveniently ignores the username and password
                # argument, as Git username updating uses a wrapper script.
                return Git.UsernamePasswordWrappingUpdater(
                    self, remote, self.get_remote_parts(remote)[1])
        else:
            raise NotImplementedError("Not implemented for %s" % remote)

        return _factory
