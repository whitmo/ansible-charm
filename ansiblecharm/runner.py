# Copyright 2014-2015 Canonical Limited.
#
# AnsibleCharm is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# charm-helpers is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with charm-helpers.  If not, see <http://www.gnu.org/licenses/>.

# Copyright 2013 Canonical Ltd.
#
# Authors:
#  Charm Helpers Developers <juju@lists.ubuntu.com>
"""Charm Helpers ansible - declare the state of your machines.

This helper enables you to declare your machine state, rather than
program it procedurally (and have to test each change to your procedures).
Your install hook can be as simple as::

    {{{
    import charmhelpers.contrib.ansible


    def install():
        charmhelpers.contrib.ansible.install_ansible_support()
        charmhelpers.contrib.ansible.apply_playbook('playbooks/install.yaml')
    }}}

and won't need to change (nor will its tests) when you change the machine
state.

All of your juju config and relation-data are available as template
variables within your playbooks and templates. An install playbook looks
something like::

    {{{
    ---
    - hosts: localhost
      user: root

      tasks:
        - name: Add private repositories.
          template:
            src: ../templates/private-repositories.list.jinja2
            dest: /etc/apt/sources.list.d/private.list

        - name: Update the cache.
          apt: update_cache=yes

        - name: Install dependencies.
          apt: pkg={{ item }}
          with_items:
            - python-mimeparse
            - python-webob
            - sunburnt

        - name: Setup groups.
          group: name={{ item.name }} gid={{ item.gid }}
          with_items:
            - { name: 'deploy_user', gid: 1800 }
            - { name: 'service_user', gid: 1500 }

      ...
    }}}

Read more online about `playbooks`_ and standard ansible `modules`_.

.. _playbooks: http://www.ansibleworks.com/docs/playbooks.html
.. _modules: http://www.ansibleworks.com/docs/modules.html

"""
from . import state
from charmhelpers.core import hookenv
from charmhelpers.core.hookenv import log
from path import path
import charmhelpers.fetch
import os
import subprocess

charm_dir = os.environ.get('CHARM_DIR', '')
ansible_hosts_path = '/etc/ansible/hosts'
# Ansible will automatically include any vars in the following
# file in its inventory when run locally.
ansible_vars_path = '/etc/ansible/host_vars/localhost'


def install_ansible_support(from_ppa=True, ppa_location='ppa:rquillo/ansible'):
    """Installs the ansible package.

    By default it is installed from the `PPA`_ linked from
    the ansible `website`_ or from a ppa specified by a charm config..

    .. _PPA: https://launchpad.net/~rquillo/+archive/ansible
    .. _website: http://docs.ansible.com/intro_installation.html#latest-releases-via-apt-ubuntu

    If from_ppa is empty, you must ensure that the package is available
    from a configured repository.
    """
    if from_ppa:
        charmhelpers.fetch.add_source(ppa_location)
        charmhelpers.fetch.apt_update(fatal=True)
    charmhelpers.fetch.apt_install('ansible')
    with open(ansible_hosts_path, 'w+') as hosts_file:
        hosts_file.write('localhost ansible_connection=local')


def apply_playbook(playbook, tags=None, verbosity=0, module_path=None):
    tags = tags or []
    tags = ",".join(tags)

    state.juju_state_to_yaml(
        ansible_vars_path, namespace_separator='__',
        allow_hyphens_in_keys=False)

    log("ANSIBLE VARS: %s" % ansible_vars_path, level="INFO")
    if verbosity > 1:
        with open(ansible_vars_path) as fp:
            print(fp.read())

    # we want ansible's log output to be unbuffered
    env = os.environ.copy()
    env['PYTHONUNBUFFERED'] = "1"

    call = [
        'ansible-playbook',
        '-c',
        'local'
        ]
    if verbosity > 0:
        verbosity = '-' + ''.join(["v" for x in range(verbosity)])
        call.append(verbosity)

    call.append(playbook)

    if tags:
        call.extend(['--tags', '{}'.format(tags)])

    if module_path:
        call.append("--module_path={}".format(module_path))

    log(' '.join(call), level="INFO")
    subprocess.check_call(call, env=env)


class AnsibleHooks(hookenv.Hooks):
    """Run a playbook with the hook-name as the tag.

    This helper builds on the standard hookenv.Hooks helper,
    but additionally runs the playbook with the hook-name specified
    using --tags (ie. running all the tasks tagged with the hook-name).

    Example::

        hooks = AnsibleHooks(playbook_path='playbooks/my_machine_state.yaml')

        # All the tasks within my_machine_state.yaml tagged with 'install'
        # will be run automatically after do_custom_work()
        @hooks.hook()
        def install():
            do_custom_work()

        # For most of your hooks, you won't need to do anything other
        # than run the tagged tasks for the hook:
        @hooks.hook('config-changed', 'start', 'stop')
        def just_use_playbook():
            pass

        # As a convenience, you can avoid the above noop function by specifying
        # the hooks which are handled by ansible-only and they'll be registered
        # for you:
        # hooks = AnsibleHooks(
        #     'playbooks/my_machine_state.yaml',
        #     default_hooks=['config-changed', 'start', 'stop'])

        if __name__ == "__main__":
            # execute a hook based on the name the program is called by
            hooks.execute(sys.argv)

    """
    playbook = staticmethod(apply_playbook)
    charm_dir = path(charm_dir)
    charm_modules = charm_dir / "modules"
    charm_name = hookenv.charm_name

    def __init__(self, playbook_path, default_hooks=None):
        """Register any hooks handled by ansible."""
        super(AnsibleHooks, self).__init__()

        self.playbook_path = playbook_path

        default_hooks = default_hooks or []
        noop = lambda *args, **kwargs: None
        for hook in default_hooks:
            self.register(hook, noop)

    def execute(self, args, verbosity=1, any_tag=False, modules=None):
        """Execute the hook followed by the playbook using the hook as tag."""
        super(AnsibleHooks, self).execute(args)
        hook_file = path(args[0])
        hook_name = hook_file.basename()

        modules = modules is None and []
        modules = isinstance(modules, basestring) and [modules]

        # pick up implicit module path
        if self.charm_modules.exists():
            modules.append(self.charm_modules)

        modules = isinstance(modules, list) and ":".join(modules)

        tags = [hook_name]
        if any_tag is True:
            tags.append("any")

        self.playbook(self.playbook_path,
                      tags=tags, verbosity=verbosity, module_path=modules)
