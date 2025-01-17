import os

from unittest import mock

from . import utils

from hotsos.core.config import setup_config
from hotsos.core.issues.utils import IssuesStore
from hotsos.core.issues import KubernetesWarning
from hotsos.core import host_helpers
from hotsos.core.plugins import kubernetes as kubernetes_core
from hotsos.core.ycheck.scenarios import YScenarioChecker
from hotsos.plugin_extensions.kubernetes import summary


class KubernetesTestsBase(utils.BaseTestCase):

    def setUp(self):
        super().setUp()
        setup_config(PLUGIN_NAME='kubernetes',
                     DATA_ROOT=os.path.join(utils.TESTS_DIR,
                                            'fake_data_root/kubernetes'))


class TestKubernetesSummary(KubernetesTestsBase):

    def setUp(self):
        self.snaps_list = host_helpers.CLIHelper().snap_list_all()
        super().setUp()

    def test_get_service_info(self):
        expected = {'systemd': {
                        'enabled': [
                            'calico-node',
                            'containerd',
                            'flannel',
                            'kube-proxy-iptables-fix',
                            'snap.kube-apiserver.daemon',
                            'snap.kube-controller-manager.daemon',
                            'snap.kube-proxy.daemon',
                            'snap.kube-scheduler.daemon']
                        },
                    'ps': [
                        'calico-node (3)',
                        'containerd (1)',
                        'containerd-shim-runc-v2 (1)',
                        'flanneld (1)',
                        'kube-apiserver (1)',
                        'kube-controller-manager (1)',
                        'kube-proxy (1)',
                        'kube-scheduler (1)']}
        inst = summary.KubernetesSummary()
        self.assertEqual(self.part_output_to_actual(inst.output)['services'],
                         expected)

    def test_get_snap_info_from_line(self):
        result = ['cdk-addons 1.23.0',
                  'core 16-2.54.2',
                  'core18 20211215',
                  'core20 20220114',
                  'kube-apiserver 1.23.3',
                  'kube-controller-manager 1.23.3',
                  'kube-proxy 1.23.3',
                  'kube-scheduler 1.23.3',
                  'kubectl 1.23.3']
        inst = summary.KubernetesSummary()
        self.assertEqual(self.part_output_to_actual(inst.output)['snaps'],
                         result)

    @mock.patch.object(host_helpers.packaging, 'CLIHelper')
    def test_get_snap_info_from_line_no_k8s(self, mock_helper):
        mock_helper.return_value = mock.MagicMock()
        filterered_snaps = []
        for line in self.snaps_list:
            found = False
            for pkg in kubernetes_core.K8S_PACKAGES:
                obj = summary.KubernetesSummary()
                if obj.snaps._get_snap_info_from_line(line, pkg):
                    found = True
                    break

            if not found:
                filterered_snaps.append(line)

        mock_helper.return_value.snap_list_all.return_value = filterered_snaps
        inst = summary.KubernetesSummary()
        self.assertFalse(inst.plugin_runnable)
        self.assertTrue('snaps' not in inst.output)

    def test_get_network_info(self):
        expected = {'flannel.1': {'addr': '10.1.84.0',
                                  'vxlan': {'dev': 'ens3',
                                            'id': '1',
                                            'local_ip': '10.6.3.201'}}}
        inst = summary.KubernetesSummary()
        self.assertEqual(self.part_output_to_actual(inst.output)['flannel'],
                         expected)


class TestKubernetesScenarioChecks(KubernetesTestsBase):

    @mock.patch('hotsos.core.ycheck.engine.YDefsLoader._is_def',
                new=utils.is_def_filter('system_cpufreq_mode.yaml'))
    @mock.patch('hotsos.core.plugins.system.system.SystemBase.'
                'virtualisation_type', None)
    @mock.patch('hotsos.core.plugins.kernel.sysfs.CPU.'
                'cpufreq_scaling_governor_all', 'powersave')
    @mock.patch('hotsos.core.plugins.kubernetes.KubernetesChecksBase.'
                'plugin_runnable', True)
    @mock.patch.object(host_helpers.packaging, 'CLIHelper')
    def test_system_cpufreq_mode(self, mock_cli):
        mock_cli.return_value = mock.MagicMock()
        mock_cli.return_value.snap_list_all.return_value = \
            ['kubelet 1.2.3 123\n']
        mock_cli.return_value.systemctl_list_unit_files.return_value = \
            ['ondemand.service enabled\n']

        YScenarioChecker()()
        msg = ('This node is used for Kubernetes but is not using '
               'cpufreq scaling_governor in "performance" mode '
               '(actual=powersave). This is not recommended and can result in '
               'performance degradation. To fix this you can install '
               'cpufrequtils, set "GOVERNOR=performance" in '
               '/etc/default/cpufrequtils and run systemctl restart '
               'cpufrequtils. You will also need to stop and disable the '
               'ondemand systemd service in order for changes to persist.')
        issues = list(IssuesStore().load().values())[0]
        self.assertEqual([issue['type'] for issue in issues],
                         [KubernetesWarning('').name])
        self.assertEqual([issue['desc'] for issue in issues], [msg])
