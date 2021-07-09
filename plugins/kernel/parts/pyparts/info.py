import os
import re

from common import constants
from kernel_common import KernelChecksBase

YAML_PRIORITY = 0


class KernelGeneralChecks(KernelChecksBase):

    def get_version_info(self):
        if self.kernel_version:
            self._output["version"] = self.kernel_version

    def get_cmdline_info(self):
        if self.boot_parameters:
            self._output["boot"] = " ".join(self.boot_parameters)

    def get_systemd_info(self):
        path = os.path.join(constants.DATA_ROOT, "etc/systemd/system.conf")
        if os.path.exists(path):
            self._output["systemd"] = {"CPUAffinity": "not set"}
            for line in open(path):
                ret = re.compile("^CPUAffinity=(.+)").match(line)
                if ret:
                    self._output["systemd"]["CPUAffinity"] = ret[1]

    def get_cpu_info(self):
        """
        If isolcpus is set on the proc/cmdline this should equal that value
        otherwise it has not taken effect.
        """
        path = os.path.join(constants.DATA_ROOT,
                            "sys/devices/system/cpu/isolated")
        if not os.path.exists(path):
            return

        with open(path) as fd:
            isolated = fd.read()

        isolated = isolated.strip()
        if isolated:
            self._output["cpu"] = {"isolated": isolated}

    def __call__(self):
        self.get_version_info()
        self.get_cmdline_info()
        self.get_systemd_info()
        self.get_cpu_info()
