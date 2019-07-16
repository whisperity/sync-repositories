"""
SYNOPSIS: Wrapper script that acts as an 'askpass' program, but in fact just
          returns the data stored in the keyring.
"""
from copy import deepcopy
import os
import sys
import tempfile

from sync_repositories.credentials import keyring


def create(protocol, host, port, objname):
    """
    Sets up an environment through which the program can be re-invoked by
    itself. In this new environment, the output will be the username and
    password stored in the keyring for the specified server.

    Refer to `credentials.keyring` for what the arguments mean.
    """
    # Set up an environment in which 'git fetch' will load username and
    # password from this script, not prompt the user in terminal.
    env = deepcopy(os.environ)
    env['GIT_ASKPASS'] = sys.argv[0]  # Use the entry point of the script.
    env['SR_ASKPASS'] = '1'

    env['SR_ASKPASS_PROTOCOL'] = protocol if protocol else ''
    env['SR_ASKPASS_SERVER'] = host if host else ''
    env['SR_ASKPASS_PORT'] = str(port) if port else '0'
    env['SR_ASKPASS_OBJECT'] = objname if objname else ''

    handle, filepath = tempfile.mkstemp()
    os.write(handle, 'U'.encode('ascii'))
    os.close(handle)

    env['SR_ASKPASS_TEMP'] = filepath

    return env


def create_with_credentials(username, password, protocol, host, port, objname):
    """
    Sets up an environment through which the program can be re-invoked by
    itself, but instead of the data stored actually in the keyring, returns a
    pre-set username and password.

    The credentials don't *actually* leave the keyring, as a temporary store
    is used by the wrapper.
    """

    storage = keyring.SecretStorage.get_storage()
    protocol = 'temp'
    objname = objname + '__TEMP'
    storage.set_credential(protocol, host, port, username, password, objname,
                           label="Temporary password for Sync-Repos ASKPASS")

    env = create(protocol, host, port, objname)
    env['SR_ASKPASS_TEMPORARY_CREDENTIAL'] = '1'

    return env


def execute():
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

    objname = os.environ['SR_ASKPASS_OBJECT']
    if not objname:  # Might be empty string.
        objname = None

    credentials = storage.get_credentials(os.environ['SR_ASKPASS_PROTOCOL'],
                                          os.environ['SR_ASKPASS_SERVER'],
                                          os.environ['SR_ASKPASS_PORT'],
                                          objname)
    if not credentials:
        # If no credentials are found, bail out. This *usually* shouldn't
        # happen, as the main script preemptively asks the user for
        # credentials.
        print("invalid")
        sys.exit(0)  # Need to exit with "success" here so the caller believes.

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

        if os.environ.get('SR_ASKPASS_TEMPORARY_CREDENTIAL', None) and \
                os.environ['SR_ASKPASS_PROTOCOL'] == 'temp' and \
                objname is not None and \
                objname.endswith('__TEMP'):
            # Delete a temporary credential if the wrapper invocation was
            # created with create_with_credentials.
            storage.delete_server(os.environ['SR_ASKPASS_PROTOCOL'],
                                  os.environ['SR_ASKPASS_SERVER'],
                                  os.environ['SR_ASKPASS_PORT'])

    sys.exit(0)
