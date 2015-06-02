# Copyright 2013 Canonical Ltd.
#
# Authors:
#  Charm Helpers Developers <juju@lists.ubuntu.com>
import dictdiffer as dd
import mock
import os
import shutil
import tempfile
import unittest
import yaml


class ApplyPlaybookTestCases(unittest.TestCase):

    unit_data = {
        'private-address': '10.0.3.2',
        'public-address': '123.123.123.123',
    }

    def makeone(self):
        from ansiblecharm import runner as ansible
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

        self.wfh_mock = mock.Mock(name="wfh")
        patcher = mock.patch.object(ansible.AnsibleHooks,
                                    'write_hosts_file', self.wfh_mock)
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
        self.mock_local_unit.return_value = "svc/1"

        def unit_get_data(argument):
            "dummy unit_get that accesses dummy unit data"
            return self.unit_data[argument]

        patcher = mock.patch(
            'charmhelpers.core.hookenv.unit_get', unit_get_data)
        self.mock_unit_get = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch('ansiblecharm.runner.subprocess')
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
            control = {
                "group_code_owner": "webops_deploy",
                "user_code_runner": "ubunet",
                "private_address": "10.10.10.10",
                "charm_dir": "",
                "service_name": "svc",
                "local_unit": "svc/1",
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
            }
            assert control == result, tuple(dd.diff(control, result))

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
                '--tags', 'foo'], env={'PYTHONUNBUFFERED': '1'})
            assert self.wfh_mock.called

    def test_specifying_ansible_handled_hooks(self):
        ansible, hookenv = self.makeone()
        with mock.patch.object(hookenv, 'config'):
            hooks = ansible.AnsibleHooks(
                'my/playbook.yaml', default_hooks=['start', 'stop'])

            hooks.execute(['start'])

            self.mock_subprocess.check_call.assert_called_once_with([
                'ansible-playbook', '-c', 'local', '-v', 'my/playbook.yaml',
                '--tags', 'start'], env={'PYTHONUNBUFFERED': '1'})
            assert self.wfh_mock.called
