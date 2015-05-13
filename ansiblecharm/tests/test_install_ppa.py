from functools import partial
from mock import patch
import mock
import tempfile
import unittest
from path import path


class InstallAnsibleSupportTestCase(unittest.TestCase):

    def makeone(self):
        from ansiblecharm import runner as ansible
        from ansiblecharm import helpers
        from charmhelpers.core import hookenv

        hosts_file = tempfile.NamedTemporaryFile()
        self.ansible_hosts_path = path(hosts_file.name)
        self.addCleanup(hosts_file.close)

        patcher = mock.patch.object(helpers,
                                    'write_hosts_file',
                                    partial(helpers.write_hosts_file,
                                            self.ansible_hosts_path))
        self.whfm = patcher.start()
        self.addCleanup(patcher.stop)

        patcher = mock.patch.object(ansible, 'log')
        patcher.start()
        self.addCleanup(patcher.stop)
        return helpers, hookenv

    def setUp(self):
        super(InstallAnsibleSupportTestCase, self).setUp()

        self.mocks = {}
        for func in ('add_source', 'apt_update', 'apt_install'):
            patcher = patch('charmhelpers.fetch.%s' % func)
            self.mocks[func] = patcher.start()
            self.addCleanup(patcher.stop)

        patcher = patch('charmhelpers.core')
        self.mock_core = patcher.start()
        self.addCleanup(patcher.stop)

    def test_adds_ppa_by_default(self):
        ansible, hookenv = self.makeone()
        ansible.install_ansible_support()

        self.mocks['add_source'].assert_called_once_with(
            'ppa:rquillo/ansible')
        self.mocks['apt_update'].assert_called_once_with(fatal=True)
        self.mocks['apt_install'].assert_called_once_with(
            'ansible')

    def test_no_ppa(self):
        ansible, hookenv = self.makeone()
        ansible.install_ansible_support(from_ppa=False)

        self.assertEqual(self.mocks['add_source'].call_count, 0)
        self.mocks['apt_install'].assert_called_once_with('ansible')

    def test_writes_ansible_hosts(self):
        ansible, hookenv = self.makeone()
        with open(self.ansible_hosts_path) as hosts_file:
            self.assertEqual(hosts_file.read(), '')

        self.ansible_hosts_path.remove()
        ansible.install_ansible_support()

        assert self.ansible_hosts_path.text() == \
            'localhost ansible_connection=local'
