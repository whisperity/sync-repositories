import urllib.parse


class Repository:
    def __init__(self, path, datadir, kind):
        self.path = path
        self.datadir = datadir
        self.kind = kind
        self.urls = []

    def get_authentication_method(self, remote):
        """
        Retrieve the authentication method 'backend' needed to authenticate
        against a given remote.
        """
        raise NotImplementedError()

    def get_remote_parts(self, remote):
        """
        Returns a tuple of (`protocol`, `server hostname`, `port` and
        `object`).

        If `port` is not known, it is replaced by `0`.

        :returns: A pair of (url, parts) where `url` is the full URL, and
            `parts` is a tuple containing `protocol`, `hostname`, `port` and
            optionally the server sub-object (such as folder) in this order.
        """
        url = next(filter(lambda r: r[0] == remote, self.urls))[1]
        parse_result = urllib.parse.urlparse(url, 'unk')
        protocol = self.kind + '-' + parse_result.scheme
        host = parse_result.hostname
        port = parse_result.port if parse_result.port else 0

        return (url, (protocol, host, port, self.get_remote_objname(remote)))

    def get_remotes(self):
        """
        Returns a generator that produces, for each remote repository URL known
        for the instance, a triple of (`protocol`, `server hostname`
        and `port`).

        If `port` is not known, it is replaced by `0`.

        :returns: A triple of (remote, url, parts) where `remote` is the
            name of the remote, `url` is the full URL, and `parts` is a
            tuple containing `protocol`, `hostname`, `port` and optionally the
            server sub-object (such as folder) in this order.
        """
        for remote, url in self.urls:
            parse_result = urllib.parse.urlparse(url, 'unk')
            protocol = self.kind + '-' + parse_result.scheme
            host = parse_result.hostname
            port = parse_result.port if parse_result.port else 0

            yield (remote, url,
                   (protocol, host, port, self.get_remote_objname(remote)))

    def get_updater_for(self, remote):
        """
        Return a factory function for the current repository that can be used
        to instantiate an `Updater` instance.
        """
        raise NotImplementedError()

    def get_remote_objname(self, remote):
        """
        Get an identifying "object name" for the current repository and
        specified remote. This is used to distinguish remotes on the same
        server endpoint.
        """
        raise NotImplementedError()

    def __repr__(self):
        return '(' + type(self).__name__ + " @ " + self.path + ')'


class Updater:
    def __init__(self, repository):
        self._repository = repository

    def update(self):
        """
        Performs the update action for the repository.
        :return: False if the update failed, True if successful.
        """
        raise NotImplementedError()
