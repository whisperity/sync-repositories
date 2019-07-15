#!/usr/bin/env python3
"""
SYNOPSIS: Automatically updates every found source code repository in the
          current tree, or the specified path.
"""

import argparse
import os
import subprocess
import sys

from credentials import Backends
from credentials import keyring as kr
import repository

# Go into askpass-wrapper mode if the environment specifies it.
if 'SR_ASKPASS' in os.environ:
    from credentials import auto_askpass
    auto_askpass.execute()

    # Make sure execution doesn't flow through.
    raise RuntimeError("askpass_wrapper didn't terminate properly.")


if __name__ == '__main__':
    ARGS = argparse.ArgumentParser(
        description="""Synchronise source control repositories found in the
        current tree.""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    ARGS.add_argument('root_folder',
                      help="""The root of the directory tree where update
                           should be run.""",
                      nargs='?',
                      default=os.getcwd())
    ARGS.add_argument('--do-not-ask', '--daemon', '-d',
                      dest='daemon',
                      action='store_true',
                      help="""Perform an automatic update of repositories,
                           skipping a repository if user interaction would be
                           necessary.""")
    argv = ARGS.parse_args()

    keyring = kr.SecretStorage.get_storage()

    print("Checking '%s' for repositories..." % argv.root_folder,
          file=sys.stderr)
    repository_to_update_data = {}

    # Perform a check that every repository's authentication status is known.
    for repo in repository.get_repositories(argv.root_folder):
        repo_data = list()

        for remote, url, parts in repo.get_remotes():
            check_authentication = keyring.is_requiring_authentication(*parts)
            needs_credentials, can_update = None, False
            if check_authentication is None:
                # We don't know yet whether the server requires
                # authentication or not.
                auth_checker = repo.get_auth_requirement_detector_for(
                    remote)()
                try:
                    if auth_checker.check():
                        keyring.set_authenticating(*parts)
                        needs_credentials = True
                    else:
                        keyring.set_unauthenticated(*parts)
                        needs_credentials = False
                        can_update = True
                except subprocess.CalledProcessError as cpe:
                    print("Failed to execute authentication check for "
                          "repository '%s' remote '%s':"
                          % (repo.path, remote))
                    print(cpe)
                    continue
            elif check_authentication is False:
                # We know that the server does not require authentication.
                needs_credentials, can_update = False, True
            else:
                # We know that the server requires authentication.
                needs_credentials = True

            auth_backend = repo.get_authentication_method(remote)
            if auth_backend == Backends.KEYRING:
                if needs_credentials:
                    # If we realised that credentials are needed, check if
                    # credentials are properly known.

                    credentials_stored = keyring.get_credentials(*parts)
                    if not credentials_stored:
                        print("The repository '%s' has a remote server '%s' "
                              "is connected to, but the authentication "
                              "details for this server are not known!"
                              % (repo.path, remote))

                        if not argv.daemon:
                            # ... unless running in daemon mode, in which
                            # case the user won't be asked.
                            kr.discuss_keyring_security()
                            u, p = kr.ask_user_for_password(
                                keyring, url, parts, can_be_empty=False)

                            # Check if the given credentials are valid.
                            auth_checker = repo \
                                .get_auth_requirement_detector_for(remote)(
                                    u, p)
                            if auth_checker.check_credentials():
                                can_update = True
                            else:
                                print("Invalid credentials given!",
                                      file=sys.stderr)
                                protocol, server, port, objname = parts
                                keyring.delete_credential(protocol,
                                                          server,
                                                          port,
                                                          u,
                                                          objname)
                    else:
                        can_update = True

                if can_update:
                    repo_data.append((remote, url, parts))
                else:
                    print("... Skipping this repository from update.")
                    continue

        repository_to_update_data[repo] = repo_data

    # Update repositories that had been selected for actual update.
    print("Performing repository updates...")
    for repo, data in repository_to_update_data.items():
        for remote, url, parts in data:
            print("Updating '%s' from remote '%s'..." % (repo.path, remote))
            auth_backend = repo.get_authentication_method(remote)
            update_success = False

            if auth_backend == Backends.KEYRING:
                kr_creds = keyring.get_credentials(*parts)
                if not kr_creds:
                    # If the server doesn't require authentication, don't
                    # provide credentials.
                    kr_creds = [(None, None)]

                for kr_cred in kr_creds:
                    updater = repo.get_updater_for(remote)(*kr_cred)
                    update_success = update_success or updater.update()

                if not update_success:
                    print("Failed to update '%s' from remote '%s'!"
                          % (repo.path, remote),
                          file=sys.stderr)
