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

from cloudferrylib.base.action import transporter
from cloudferrylib.os.actions import utils
from cloudferrylib.utils import utils as utl
__author__ = 'mirrorcoder'


class TransportFileToFileViaSsh(transporter.Transporter):

    def run(self, cfg=None,
            cloud_src=None,
            cloud_dst=None,
            info={},
            resource_type=utl.STORAGE_RESOURCE,
            resource_name=utl.VOLUMES_TYPE,
            resource_root_name=utl.VOLUME_BODY, **kwargs):
        data_for_trans = info[resource_type][resource_name]
        for item in data_for_trans.itervalues():
            i = item[resource_root_name]
            host_src = i['host_src']
            host_dst = i['host_dst']
            path_src = i['path_src']
            path_dst = i['path_dst']
            utils.transfer_file_to_file(cloud_src, cloud_dst, host_src, host_dst, path_src, path_dst, cfg.migrate)
        return {}
