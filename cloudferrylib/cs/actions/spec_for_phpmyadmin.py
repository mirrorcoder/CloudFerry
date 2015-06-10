# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.


from cloudferrylib.base.action import action
from fabric.api import settings, run
import time


class SpecForPhpmyadmin(action.Action):
    def __init__(self, init, cloud=None):
        super(SpecForPhpmyadmin, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        ip_internal_mysql = None
        ip_phpmyadmin = None

        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            if data['name'] == 'vm3':
                ip_internal_mysql = data['interfaces'][0]['ip']
            if data['name'] == 'vm1':
                ip_phpmyadmin = data['interfaces'][0]['floatingip']
        str_sed = 'sed -i -e "/dbserver=.*$/ s//dbserver=\'%s\';/g" /etc/phpmyadmin/config-db.php'
        str_sed = str_sed % ip_internal_mysql
        print "Wait ssh daemon UP: (about 120 secs)...."
        while True:
            print "Wait..."
            time.sleep(30)
            try:
                with settings(host_string=ip_phpmyadmin, password="swordfish"):
                    run(str_sed)
            except Exception:
                print "Error!"
                print "ReTry!"
                continue
            break

        return {
        }
