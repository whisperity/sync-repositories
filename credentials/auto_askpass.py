"""
SYNOPSIS: Helper script that acts as an 'askpass' program, but in fact just
          returns the data stored in the keyring.
"""

import os
import sys


def create(protocol, host, port, objname):
    """
    Sets up an environment through which the program can be re-invoked by
    itself. In this new environment, the output will be the username and
    password stored in the keyring for the specified server.

    Refer to `credentials.keyring` for what the arguments mean.
    """
    # Set up an environment in which 'git fetch' will load username and
    # password from this script, not prompt the user in terminal.
    from copy import deepcopy
    import tempfile

    env = deepcopy(os.environ)
    env['GIT_ASKPASS'] = sys.argv[0]  # Use the entry point of the script.
    env['SR_ASKPASS'] = '1'

    env['SR_ASKPASS_PROTOCOL'] = protocol
    env['SR_ASKPASS_SERVER'] = host
    env['SR_ASKPASS_PORT'] = str(port)
    env['SR_ASKPASS_OBJECT'] = objname

    handle, filepath = tempfile.mkstemp()
    os.write(handle, 'U'.encode('ascii'))
    os.close(handle)

    env['SR_ASKPASS_TEMP'] = filepath

    return env


def execute():
    from credentials import keyring

    if 'SR_ASKPASS_PROTOCOL' not in os.environ or \
            'SR_ASKPASS_SERVER' not in os.environ or \
            'SR_ASKPASS_PORT' not in os.environ or \
            'SR_ASKPASS_OBJECT' not in os.environ or \
            'SR_ASKPASS_TEMP' not in os.environ:
        print("ERROR! Bad invocation -- environment wasn't set up.",
              file=sys.stderr)
        sys.exit(1)

    # We can safely assume that the storage obtained here is unlocked, as this
    # script should be called from under __main__ anyways.
    storage = keyring.SecretStorage.get_storage()

    credentials = storage.get_credentials(os.environ['SR_ASKPASS_PROTOCOL'],
                                          os.environ['SR_ASKPASS_SERVER'],
                                          os.environ['SR_ASKPASS_PORT'],
                                          os.environ['SR_ASKPASS_OBJECT'])
    if not credentials:
        # If no credentials are found, bail out. This *usually* shouldn't
        # happen, as the main script preemptively asks the user for
        # credentials.
        print("invalid")
        sys.exit(1)

    username, password = credentials[0]

    # Check what the invoker is searching for. The first invocation for a
    # repository queries a username, and the second queries the password.
    clean_up_temp_file = False
    with open(os.environ['SR_ASKPASS_TEMP'], 'r+') as f:
        content = f.readline().rstrip()

        if content == 'U':
            print(username, end='')  # Actual output to invoker.

            f.truncate(0)
            f.seek(0)
            f.write('P')
        elif content == 'P':
            print(password, end='')  # Actual output to invoker.

            f.truncate(0)
            clean_up_temp_file = True

    if clean_up_temp_file:
        os.unlink(os.environ['SR_ASKPASS_TEMP'])

    sys.exit(0)
