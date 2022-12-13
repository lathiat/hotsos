import re

from hotsos.core.log import log
from hotsos.core.host_helpers import CLIHelper
from hotsos.core.utils import cached_property


class UptimeHelper(object):
    def __init__(self):
        # unfortunately sosreports dont have proc/uptime otherwise we would use
        # that.
        self.uptime = CLIHelper().uptime() or ""
        # this needs to take into account the different formats supported by
        # https://gitlab.com/procps-ng/procps/-/blob/newlib/library/uptime.c
        etime_expr = r"(?:([\d:]+)|(\d+\s+\S+,\s+[\d:]+)|(\d+\s+\S+)),"
        expr = r"\s*[\d:]+ up {}.+ load average: (.+)".format(etime_expr)
        ret = re.compile(expr).match(self.uptime)
        self.subgroups = {}
        if ret:
            self.subgroups['hour'] = {'value': ret.group(1),
                                      'expr': r'(\d+):(\d+)'}
            self.subgroups['day'] = {'value': ret.group(2),
                                     'expr': r"(\d+)\s+\S+,\s+(\d+):(\d+)"}
            self.subgroups['min'] = {'value': ret.group(3),
                                     'expr': r"(\d+)\s+(\S+)"}
            self.subgroups['loadavg'] = {'value': ret.group(4)}

    @cached_property
    def minutes(self):
        if not self.subgroups:
            log.info("uptime not available")
            return

        if self.subgroups['hour']['value']:
            expr = self.subgroups['hour']['expr']
            ret = re.match(expr, self.subgroups['hour']['value'])
            if ret:
                return (int(ret.group(1)) * 60) + int(ret.group(2))
        elif self.subgroups['day']['value']:
            expr = self.subgroups['day']['expr']
            ret = re.match(expr, self.subgroups['day']['value'])
            if ret:
                count = int(ret.group(1))
                hours = int(ret.group(2))
                mins = int(ret.group(3))
                day_mins = 24 * 60
                sum = count * day_mins
                sum += hours * 60
                sum += mins
                return sum
        elif self.subgroups['min']['value']:
            expr = self.subgroups['min']['expr']
            ret = re.match(expr, self.subgroups['min']['value'])
            if ret:
                return int(ret.group(1))

        log.warning("unknown uptime format in %s", self.uptime)

    @property
    def seconds(self):
        if self.minutes:
            return self.minutes * 60

    @property
    def hours(self):
        if self.minutes:
            return int(self.minutes / 60)

    @property
    def loadavg(self):
        if self.subgroups:
            return self.subgroups['loadavg']['value']