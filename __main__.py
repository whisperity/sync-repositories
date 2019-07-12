#!/usr/bin/env python3
"""
SYNOPSIS: Automatically updates every found source code repository in the
          current tree, or the specified path.
"""

import argparse
import os
import sys

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
    ARGS.add_argument('--allow-new-repositories', '-a',
                      help="""Allow every found repository, even new ones, to
                           be updated. By default, only repositories that has
                           been configured at least once are updated again.
                           """,
                      action='store_true')

    argv = ARGS.parse_args()
    print(argv)

    keyring = kr.SecretStorage.get_storage()

    print("Checking '%s' for repositories..." % argv.root_folder,
          file=sys.stderr)
    repository_to_update_data = {}

    # Perform a check that every repository's authentication status is known.
    for repo in repository.get_repositories(argv.root_folder):
        repo_data = list()

        for remote, url, parts in repo.get_remotes():
            if repo.get_authentication_method(remote) == 'keyring':
                kr_creds = keyring.get_credentials(*parts)
                if kr_creds is None:
                    print("The repository '%s' has a remote server it is "
                          "connected to, but the authentication details "
                          "for this server are not known!"
                          % repo.path)
                    if argv.allow_new_repositories:
                        kr.discuss_keyring_security()
                        kr.ask_user_for_password(keyring, url, parts)

                        repo_data.append((remote, url, parts))
                    else:
                        print("... Skipping this repository and remote from "
                              "upgrade.")
                elif kr_creds is False or kr_creds:
                    # Allow updating the repository if some credentials are
                    # known - or the fact that no credentials are needed is
                    # known.
                    repo_data.append((remote, url, parts))

        repository_to_update_data[repo] = repo_data

    # Update repositories that had been selected for actual update.
    print("Performing repository updates...")
    for repo, data in repository_to_update_data.items():
        for remote, url, parts in data:
            if repo.get_authentication_method(remote) == 'keyring':
                kr_creds = keyring.get_credentials(*parts)
                if kr_creds is False:
                    # If the server is not authenticating, indicate this in the
                    # credentials to pass.
                    kr_creds = [(None, None)]

                for kr_cred in kr_creds:
                    updater = repo.get_updater_for(remote)(*kr_cred)
                    updater.update()
