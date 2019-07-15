from enum import Enum


class Backends(Enum):
    KEYRING = 1,
    SSH_AGENT = 2
