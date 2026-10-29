"""Require the supported, security-patched Python branch for Windows binaries."""
import sys

MINIMUM=(3,14,10)


def check(version=None):
    version=tuple(sys.version_info[:3] if version is None else version)
    if not MINIMUM<=version<(3,15):
        raise ValueError('Windows distributions require Python 3.14.10 or newer 3.14.x. Install a patched Python 3.14 x64 runtime and rebuild.')


if __name__=='__main__':
    try:check()
    except ValueError as error:raise SystemExit(str(error))
    print('Windows build Python:',sys.version.split()[0])
