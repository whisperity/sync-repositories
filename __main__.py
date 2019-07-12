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


if __name__ == '__main__':
    ARGS = argparse.ArgumentParser(
        description="""Synchronise source control repositories found in the
        current tree.""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    ARGS.add_argument('root_folder',
                      help="The root of the directory tree where update "
                           "should be run.",
                      nargs='?',
                      default=os.getcwd())

    argv = ARGS.parse_args()
    print(argv)

    keyring = kr.SecretStorage.get_storage()

    print("Checking '%s' for repositories..." % argv.root_folder,
          file=sys.stderr)
    repositories = list(repository.get_repositories(argv.root_folder))

    # Perform a check that every repository's authentication status is known.
    for repo in repositories:
        for remote, url, parts in repo.get_remotes():
            if repo.get_authentication_method(remote) == 'keyring':
                kr_creds = keyring.get_credentials(*parts)
                if kr_creds is None:
                    print("The repository '%s' has a remote server it is "
                          "connected to, but the authentication details "
                          "for this server are not known!"
                          % os.path.basename(repo.path))

                    kr.discuss_keyring_security()

                    kr.ask_user_for_password(keyring, url, parts)

    print("Performing repository updates...")
    for repo in repositories:
        for remote, url, parts in repo.get_remotes():
            if repo.get_authentication_method(remote) == 'keyring':
                kr_creds = keyring.get_credentials(*parts)
                if kr_creds is False:
                    # If the server is not authenticating, indicate this in the
                    # credentials to pass.
                    kr_creds = [(None, None)]

                for kr_cred in kr_creds:
                    updater = repo.get_updater_for(remote)(*kr_cred)
                    updater.update()
