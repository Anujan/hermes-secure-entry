"""Stage a separate plugin; optionally configure/enable through the Hermes CLI. Never restart."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from .broker import Broker


def stage(source, home):
    source, home = Path(source).resolve(), Path(home).resolve()
    parent = home / 'plugins'
    parent.mkdir(parents=True, exist_ok=True)
    target = parent / 'secure-entry'
    if target.exists():
        raise FileExistsError('secure-entry already exists; review and move that directory aside explicitly')
    # Build in the same filesystem for an atomic final directory rename.
    pending = Path(tempfile.mkdtemp(prefix='.secure-entry-stage-', dir=parent))
    try:
        for name in ('__init__.py','plugin.yaml','README.md','LICENSE','SECURITY.md'):
            if (source/name).is_file(): shutil.copy2(source/name, pending/name)
        for name in ('secure_entry','docs'):
            if (source/name).is_dir():
                shutil.copytree(source/name, pending/name, ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        if not (pending/'plugin.yaml').is_file() or not (pending/'__init__.py').is_file():
            raise ValueError('invalid plugin source')
        os.rename(pending, target)
    except BaseException:
        shutil.rmtree(pending, ignore_errors=True)
        raise
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-base-url')
    parser.add_argument('--enable', action='store_true')
    args = parser.parse_args(argv)
    if args.enable and not args.public_base_url:
        parser.error('--enable requires an explicitly trusted --public-base-url')
    if args.public_base_url:
        Broker(args.public_base_url)  # validates without opening a listener
    from hermes_constants import get_hermes_home
    target = stage(Path(__file__).resolve().parents[1], get_hermes_home())
    print('Staged separate plugin: ' + str(target))
    executable = shutil.which('hermes')
    if args.public_base_url:
        subprocess.run([executable, 'config', 'set', 'plugins.entries.secure-entry.settings.public_base_url', args.public_base_url], check=True)
        subprocess.run([executable, 'config', 'set', 'plugins.entries.secure-entry.settings.port', '8769'], check=True)
    if args.enable:
        subprocess.run([executable, 'plugins', 'enable', 'secure-entry', '--no-allow-tool-override'], check=True)
    print('No services restarted. A coordinated new gateway process/session is required to load the plugin.')


if __name__ == '__main__':
    main()
