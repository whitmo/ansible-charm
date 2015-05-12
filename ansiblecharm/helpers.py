from path import path
from charmhelpers import fetch


def hook_names(hook_dir):
    """
    Returns hooknames by inspecting symlinks in the hook_dir
    """
    here = path(hook_dir)
    for name in (x.basename() \
                 for x in here.files() if x.islink()):
        yield name


def write_hosts_file(ansible_hosts_path='/etc/ansible/hosts'):
    """
    Write the ansible hosts file if missing

    ansible requires a hosts file with a valid entry to run
    """
    ansible_hosts_path = path(ansible_hosts_path)
    if ansible_hosts_path.exists():
        ansible_hosts_path.write_text('localhost ansible_connection=local')


def install_ansible_support(from_ppa=True,
                            ppa_location='ppa:rquillo/ansible'):
    """Installs the ansible package.

    By default it is installed from the `PPA`_ linked from
    the ansible `website`_ or from a ppa specified by a charm config..

    .. _PPA: https://launchpad.net/~rquillo/+archive/ansible
    .. _website: http://docs.ansible.com/intro_installation.html#latest-releases-via-apt-ubuntu

    If from_ppa is empty, you must ensure that the package is available
    from a configured repository.
    """
    if from_ppa:
        fetch.add_source(ppa_location)
        fetch.apt_update(fatal=True)
    fetch.apt_install('ansible')
    write_hosts_file()
