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


import copy

from fabric.api import env
from fabric.api import run
from fabric.api import settings

from cloudferrylib.base.action import action
from cloudferrylib.os.actions import convert_file_to_image
from cloudferrylib.os.actions import convert_image_to_file
from cloudferrylib.os.actions import convert_volume_to_image
from cloudferrylib.os.actions import copy_g2g
from cloudferrylib.os.actions import task_transfer
from cloudferrylib.utils import utils as utl, forward_agent


CLOUD = 'cloud'
BACKEND = 'backend'
CEPH = 'ceph'
ISCSI = 'iscsi'
COMPUTE = 'compute'
INSTANCES = 'instances'
INSTANCE_BODY = 'instance'
INSTANCE = 'instance'
DIFF = 'diff'
EPHEMERAL = 'ephemeral'
DIFF_OLD = 'diff_old'
EPHEMERAL_OLD = 'ephemeral_old'

PATH_DST = 'path_dst'
HOST_DST = 'host_dst'
PATH_SRC = 'path_src'
HOST_SRC = 'host_src'

TEMP = 'temp'
FLAVORS = 'flavors'


TRANSPORTER_MAP = {CEPH: {CEPH: 'ssh_ceph_to_ceph',
                          ISCSI: 'ssh_ceph_to_file'},
                   ISCSI: {CEPH: 'ssh_file_to_ceph',
                           ISCSI: 'ssh_file_to_file'}}


class ConvertDiskVMwareToOS(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        src_cloud = self.src_cloud
        dst_cloud = self.dst_cloud
        computeVMWare = src_cloud.resources['compute']
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            computeVMWare.convert_flat_disk(None,
                                            dst_cloud.getIpSsh(),
                                            data['diskFile'][0],
                                            "%s.img" % data['diskFile'][0])

        return {}