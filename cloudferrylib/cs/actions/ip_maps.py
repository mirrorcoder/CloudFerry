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
from cloudferrylib.utils import utils as utl
from fabric.api import settings, run
from cloudferrylib.utils.drivers import ssh_file_to_file
from cloudferrylib.os.actions import prepare_networks
import time
AVAILABLE = 'available'
ID_ROUTER = "b4f46132-2b6b-487f-b739-c7807d85d8b3"

MAPS = {
    '172.16.66.80': '172.18.172.112',
    '172.16.66.88': '172.18.172.110'
}


class IpMaps(action.Action):
    def __init__(self, init, cloud=None):
        super(IpMaps, self).__init__(init, cloud)

    def run(self, info=None, **kwargs):
        # search_opts = kwargs.get('search_opts', {})
        compute_resource_src = self.src_cloud.resources[utl.COMPUTE_RESOURCE]
        compute_resource_dst = self.dst_cloud.resources[utl.COMPUTE_RESOURCE]
        cfg_cloud_src = compute_resource_src.config.cloud
        cfg_cloud_dst = compute_resource_dst.config.cloud
        temp = cfg_cloud_src.temp
        #Create LOOP
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            if data['interfaces'][0]['floatingip'] in MAPS:
                data['interfaces'][0]['floatingip'] = MAPS[data['interfaces'][0]['floatingip']]

        return {
            'info': info
        }
