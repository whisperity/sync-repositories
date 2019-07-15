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

from credentials import Backends
from credentials.auto_askpass import create as auto_askpass_create
from .repository import Repository, Updater


class Git(Repository):
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
            env = auto_askpass_create(*self._parts)

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
        def _factory():
            class _X():
                def check(self):
                    return False
            return _X()
        return _factory

    def get_updater_for(self, remote):
        if self._auth_methods[remote] == 'keyring':
            def _factory(username, password):
                # This function conveniently ignores the username and password
                # argument, as Git username updating uses a wrapper script.
                return Git.UsernamePasswordWrappingUpdater(
                    self, remote, self.get_remote_parts(remote)[1])
            return _factory
        elif self._auth_methods[remote] == 'none':
            def _factory():
                return False
            return _factory
        elif self._auth_methods[remote] == 'ssh-agent':
            def _factory():
                return False
            return _factory
