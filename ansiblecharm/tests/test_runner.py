# Copyright 2013 Canonical Ltd.
#
# Authors:
#  Charm Helpers Developers <juju@lists.ubuntu.com>
import mock
import os
import shutil
import tempfile
import unittest
import yaml


class InstallAnsibleSupportTestCase(unittest.TestCase):

    def makeone(self):
        from charmhelpers.contrib import ansible
        from charmhelpers.core import hookenv

        hosts_file = tempfile.NamedTemporaryFile()
        self.ansible_hosts_path = hosts_file.name
        self.addCleanup(hosts_file.close)

        patcher = mock.patch.object(ansible,
                                    'ansible_hosts_path',
                                    self.ansible_hosts_path)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(ansible, 'log')
        patcher.start()
        self.addCleanup(patcher.stop)
        return ansible, hookenv

    def setUp(self):
        super(InstallAnsibleSupportTestCase, self).setUp()

        patcher = mock.patch('charmhelpers.fetch')
        self.mock_fetch = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('charmhelpers.core')
        self.mock_core = patcher.start()
        self.addCleanup(patcher.stop)

    def test_adds_ppa_by_default(self):
        ansible, hookenv = self.makeone()
        ansible.install_ansible_support()

        self.mock_fetch.add_source.assert_called_once_with(
            'ppa:rquillo/ansible')
        self.mock_fetch.apt_update.assert_called_once_with(fatal=True)
        self.mock_fetch.apt_install.assert_called_once_with(
            'ansible')

    def test_no_ppa(self):
        ansible, hookenv = self.makeone()
        ansible.install_ansible_support(from_ppa=False)

        self.assertEqual(self.mock_fetch.add_source.call_count, 0)
        self.mock_fetch.apt_install.assert_called_once_with(
            'ansible')

    def test_writes_ansible_hosts(self):
        ansible, hookenv = self.makeone()
        with open(self.ansible_hosts_path) as hosts_file:
            self.assertEqual(hosts_file.read(), '')

        ansible.install_ansible_support()

        with open(self.ansible_hosts_path) as hosts_file:
            self.assertEqual(hosts_file.read(),
                             'localhost ansible_connection=local')


class ApplyPlaybookTestCases(unittest.TestCase):

    unit_data = {
        'private-address': '10.0.3.2',
        'public-address': '123.123.123.123',
    }

    def makeone(self):
        from charmhelpers.contrib import ansible
        from charmhelpers.core import hookenv

        patcher = mock.patch('charmhelpers.core.hookenv.config')
        self.mock_config = patcher.start()
        self.addCleanup(patcher.stop)
        Serializable = hookenv.Serializable
        self.mock_config.return_value = Serializable({})

        hosts_file = tempfile.NamedTemporaryFile()
        self.ansible_hosts_path = hosts_file.name
        self.addCleanup(hosts_file.close)

        etc_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, etc_dir)
        self.vars_path = os.path.join(etc_dir, 'ansible', 'vars.yaml')
        patcher = mock.patch.object(ansible,
                                    'ansible_vars_path', self.vars_path)
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(ansible.os,
                                    'environ', {})
        patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(ansible, 'log')
        patcher.start()
        self.addCleanup(patcher.stop)
        return ansible, hookenv

    def setUp(self):
        super(ApplyPlaybookTestCases, self).setUp()

        # Hookenv patches (a single patch to hookenv doesn't work):

        patcher = mock.patch('charmhelpers.core.hookenv.relation_get')
        self.mock_relation_get = patcher.start()
        self.mock_relation_get.return_value = {}
        self.addCleanup(patcher.stop)
        patcher = mock.patch('charmhelpers.core.hookenv.relations')
        self.mock_relations = patcher.start()
        self.mock_relations.return_value = {
            'wsgi-file': {},
            'website': {},
            'nrpe-external-master': {},
        }
        self.addCleanup(patcher.stop)
        patcher = mock.patch('charmhelpers.core.hookenv.relations_of_type')
        self.mock_relations_of_type = patcher.start()
        self.mock_relations_of_type.return_value = []
        self.addCleanup(patcher.stop)
        patcher = mock.patch('charmhelpers.core.hookenv.relation_type')
        self.mock_relation_type = patcher.start()
        self.mock_relation_type.return_value = None
        self.addCleanup(patcher.stop)
        patcher = mock.patch('charmhelpers.core.hookenv.local_unit')
        self.mock_local_unit = patcher.start()
        self.addCleanup(patcher.stop)
        self.mock_local_unit.return_value = {}

        def unit_get_data(argument):
            "dummy unit_get that accesses dummy unit data"
            return self.unit_data[argument]

        patcher = mock.patch(
            'charmhelpers.core.hookenv.unit_get', unit_get_data)
        self.mock_unit_get = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('charmhelpers.contrib.ansible.subprocess')
        self.mock_subprocess = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('charmhelpers.core.hookenv.log')
        self.mock_hooklog = patcher.start()
        self.addCleanup(patcher.stop)

    def test_calls_ansible_playbook(self):
        ansible, hookenv = self.makeone()
        ansible.apply_playbook('playbooks/dependencies.yaml')

        self.mock_subprocess.check_call.assert_called_once_with([
            'ansible-playbook', '-c', 'local', 'playbooks/dependencies.yaml'],
            env={'PYTHONUNBUFFERED': '1'})

    def test_writes_vars_file(self):
        ansible, hookenv = self.makeone()
        self.assertFalse(os.path.exists(self.vars_path))
        self.mock_config.return_value = hookenv.Serializable({
            'group_code_owner': 'webops_deploy',
            'user_code_runner': 'ubunet',
            'private-address': '10.10.10.10',
        })
        self.mock_relation_type.return_value = 'wsgi-file'
        self.mock_relation_get.return_value = {
            'relation_key1': 'relation_value1',
            'relation-key2': 'relation_value2',
        }

        ansible.apply_playbook('playbooks/dependencies.yaml')

        self.assertTrue(os.path.exists(self.vars_path))
        with open(self.vars_path, 'r') as vars_file:
            result = yaml.load(vars_file.read())
            self.assertEqual({
                "group_code_owner": "webops_deploy",
                "user_code_runner": "ubunet",
                "private_address": "10.10.10.10",
                "charm_dir": "",
                "local_unit": {},
                'current_relation': {
                    'relation_key1': 'relation_value1',
                    'relation-key2': 'relation_value2',
                },
                'relations_full': {
                    'nrpe-external-master': {},
                    'website': {},
                    'wsgi-file': {},
                },
                'relations': {
                    'nrpe-external-master': [],
                    'website': [],
                    'wsgi-file': [],
                },
                "wsgi_file__relation_key1": "relation_value1",
                "wsgi_file__relation_key2": "relation_value2",
                "unit_private_address": "10.0.3.2",
                "unit_public_address": "123.123.123.123",
            }, result)

    def test_calls_with_tags(self):
        ansible, hookenv = self.makeone()
        ansible.apply_playbook('playbooks/complete-state.yaml',
                               tags=['install', 'somethingelse'])

        self.mock_subprocess.check_call.assert_called_once_with([
            'ansible-playbook', '-c', 'local', 'playbooks/complete-state.yaml',
            '--tags', 'install,somethingelse'], env={'PYTHONUNBUFFERED': '1'})

    def test_hooks_executes_playbook_with_tag(self):
        ansible, hookenv = self.makeone()
        with mock.patch.object(hookenv, 'config'):
            hooks = ansible.AnsibleHooks('my/playbook.yaml')
            foo = mock.MagicMock()
            hooks.register('foo', foo)

            hooks.execute(['foo'])

            self.assertEqual(foo.call_count, 1)
            self.mock_subprocess.check_call.assert_called_once_with([
                'ansible-playbook', '-c', 'local', '-v', 'my/playbook.yaml',
                '--tags', 'foo,all'], env={'PYTHONUNBUFFERED': '1'})

    def test_specifying_ansible_handled_hooks(self):
        ansible, hookenv = self.makeone()
        with mock.patch.object(hookenv, 'config'):
            hooks = ansible.AnsibleHooks(
                'my/playbook.yaml', default_hooks=['start', 'stop'])

            hooks.execute(['start'])

            self.mock_subprocess.check_call.assert_called_once_with([
                'ansible-playbook', '-c', 'local', '-v', 'my/playbook.yaml',
                '--tags', 'start,all'], env={'PYTHONUNBUFFERED': '1'})
