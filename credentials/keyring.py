import getpass
import sys

try:
    import secretstorage
except ImportError:
    print("Error! `secretstorage` is a dependency, please install.",
          file=sys.stderr)
    raise


class SecretStorage():
    def __init__(self, bus, collection):
        self._bus = bus
        self._collection = collection

        if self._collection.is_locked():
            raise AttributeError("Cannot initialise a keyring from a locked "
                                 "storage.")

    @classmethod
    def get_storage(cls):
        """
        User-facing factory method that creates the `SecretStorage` for the
        default secure secret backend.
        """
        bus = secretstorage.dbus_init()
        def_collection = secretstorage.get_default_collection(bus)

        if def_collection.is_locked():
            name = def_collection.get_label()
            if not name:
                name = "<unnamed>"

            print("The keyring '%s' used for storing passwords is locked, "
                  "please enter unlock password." % name)

            def_collection.unlock()
            if def_collection.is_locked():
                raise PermissionError("Failed to unlock keyring.")

        return SecretStorage(bus, def_collection)

    def get_credentials(self, protocol, server, port, objname=None):
        """
        Retrieve the stored credentials for a specified remote server.

        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        :param objname: (Optional) Constrain the search of credentials to the
            given shared authentication object.
        :return: A list of credential pairs (username, password) if the server
            is authenticating, and credentials are known.
            An empty list, if the server is known to be authenticating, but no
            credentials are known. (This case should rarely happen!)
            A `False` if the server is known not to be authenticating.
            `None` if no knowledge exists about the server.
        """
        # First, check if the server *is* authenticating.
        nattrs = {
            'xdg:schema': "org.gnome.keyring.Note",
            'application': "whisperity/sync-repositories",
            'protocol': protocol,
            'server': server,
            'port': str(port)
        }
        if objname:
            nattrs['object'] = objname
        notes = self._collection.search_items(nattrs)
        note = next(notes, None)
        if not note:
            return None
        if note.get_secret().decode('utf-8') == 'False':
            return False

        # Now search for the actual credentials.
        attrs = {
            'xdg:schema': "org.gnome.keyring.NetworkPassword",
            'authtype': "username-password",
            'application': "whisperity/sync-repositories",
            'protocol': protocol,
            'server': server,
            'port': str(port)
        }
        if objname:
            attrs['object'] = objname
        credentials = self._collection.search_items(attrs)
        ret = []
        for cred in credentials:
            ret.append((cred.get_attributes()['user'],
                        cred.get_secret().decode('utf-8')))
        return ret

    def set_credential(self, protocol, server, port, user, password,
                       objname=None, label=None):
        """
        Store (or overwrite) a credential for the given remote server.

        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        :param user: The username to authenticate with.
        :param password: The password that is used to authenticate.
        :param objname: (Optional) Constrain the credential to the given shared
            authentication object.
        :param label: (Optional) A label that is attached to the secret item
            and shown in the keyring.
        """
        attrs = {'xdg:schema': "org.gnome.keyring.NetworkPassword",
                 'authtype': "username-password",
                 'application': "whisperity/sync-repositories",
                 'protocol': protocol,
                 'server': server,
                 'port': str(port),
                 'user': user}
        if objname:
            attrs['object'] = objname
        if not label:
            label = "%s password for '%s' on '%s'" % (protocol, user, server)
        self._collection.create_item(label, attrs, password, replace=True)

        self._set_authenticating(protocol, server, port, objname)

    def delete_credential(self, protocol, server, port, user, objname=None):
        """
        Delete the credential associated with the specified remote server.
        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        :param user: The username to authenticate with.
        :param objname: (Optional) Constrain the search of credentials to the
            given shared authentication object.
        """
        attrs = {
            'xdg:schema': "org.gnome.keyring.NetworkPassword",
            'authtype': "username-password",
            'application': "whisperity/sync-repositories",
            'protocol': protocol,
            'server': server,
            'port': str(port),
            'user': user
        }
        if objname:
            attrs['object'] = objname
        items = self._collection.search_items(attrs)
        items = list(items)
        if not items:
            raise KeyError("No secret found for %s:%s:%s:%s" %
                           (protocol, server, port, user))
        return next(items).delete()

    def delete_server(self, protocol, server, port):
        """
        Deletes all information (including all credentials) known about the
        specified server.

        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        """
        credentials = self._collection.search_items({
            'authtype': "username-password",
            'application': "whisperity/sync-repositories",
            'protocol': protocol,
            'server': server,
            'port': str(port)
        })
        for cred in credentials:
            cred.delete()

        notes = self._collection.search_items({
            'xdg:schema': "org.gnome.keyring.Note",
            'application': "whisperity/sync-repositories",
            'protocol': protocol,
            'server': server,
            'port': str(port)
        })
        for note in notes:
            note.delete()

    def _store_authentication_bool(self, protocol, server, port, objname,
                                   is_authenticating):
        """
        Stores whether the remote server specified needs authentication.

        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        :param is_authenticating: The value to store in the secure storage.
        :param objname: The shared authentication object's identifier to which
            the knowledge should be constrained.
        """
        if not isinstance(is_authenticating, bool):
            raise TypeError("is_authenticating must be boolean.")

        attrs = {'xdg:schema': "org.gnome.keyring.Note",
                 'application': "whisperity/sync-repositories",
                 'protocol': protocol,
                 'server': server,
                 'port': str(port)
                 }
        if objname:
            attrs['object'] = objname
        label = "Is '%s:%d/%s' for '%s' authenticating?"\
                % (server, port, str(objname), protocol)
        self._collection.create_item(label, attrs, str(is_authenticating),
                                     replace=True)

    def _set_authenticating(self, protocol, server, port, objname=None):
        """
        Marks the given remote server as a connection that does need
        authentication.

        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        :param objname: (Optional) Constrain the knowledge to the given shared
            authentication object.
        """
        self._store_authentication_bool(protocol, server, port, objname, True)

    def set_unauthenticated(self, protocol, server, port, objname=None):
        """
        Marks the given remote server as a connection that does not need
        authentication.

        This method does NOT automatically remove the associated credentials.

        :param protocol: The protocol that is used to communicate with the
            server.
        :param server: The server's address.
        :param port: The server's port.
        :param objname: (Optional) Constrain the knowledge to the given shared
            authentication object.
        """
        self._store_authentication_bool(protocol, server, port, objname, False)


_security_headsup_shown = False


def discuss_keyring_security():
    global _security_headsup_shown
    if not _security_headsup_shown:
        print("--------- SECURITY INFORMATION ----------")
        print("Username and password-based authentication details for "
              "repositories will be saved into your Keyring or Wallet.")
        print("This is a secure solution for storing secret information "
              "for your user only!")
        print("The keyring and the data within are encrypted, and need to be "
              "unlocked every time you start your computer.")
        print("(In most cases, this is done automatically at log-in.)")
        print("Next time you use this tool, the saved information will be "
              "reused, and the details won't be asked for again.")
        print("--------- SECURITY INFORMATION ----------")

        _security_headsup_shown = True


def ask_user_for_password(keyring, url, parts):
    """
    Helper method that nicely asks the user for the authentication credentials
    for the given remote server.
    :param keyring: The keyring to save the authentication knowledge to.
    :param url: The full URL of the remote server. This is only used for
        prompting the user.
    :param parts: The tuple (protocol, server, port, objname) to save the
        credentials for.
    """
    print("Entering authentication details for '%s'..." % url)
    print("Leave username EMPTY if you know the server requires NO "
          "authentication.")
    username = input("Username (empty if no authentication): ")
    if not username.strip():
        # Empty username given.
        print("No authentication needed.")
        keyring.set_unauthenticated(*parts)
    else:
        password = ''
        while not password.strip():
            password = getpass.getpass("Password for user '%s': " % username)
            if not password.strip():
                print("ERROR: Empty password given.", file=sys.stderr)

        protocol, server, port, objname = parts
        keyring.set_credential(protocol, server, port,
                               username, password,
                               objname)
