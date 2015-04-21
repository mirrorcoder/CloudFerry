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


class CreateFlavor(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        dst_cloud = self.dst_cloud
        compute = dst_cloud.resources['compute']
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            # Task Create Flavor
            dest_flavors = {flavor.name: flavor.id for flavor in
                            compute.get_flavor_list(is_public=None)}
            if data['flavors'][0]['name'] not in dest_flavors:
                data['flavor'] = compute.create_flavor(
                    name=data['flavors'][0]['name'],
                    ram=data['flavors'][0]['ram'],
                    vcpus=data['flavors'][0]['vcpus'],
                    disk=data['flavors'][0]['disk'],
                    ephemeral=data['flavors'][0]['ephemeral'],
                    swap=data['flavors'][0]['swap'],
                    rxtx_factor=data['flavors'][0]['rxtx_factor'],
                    is_public=data['flavors'][0]['is_public']).id
            else:
                data['flavor'] = dest_flavors[data['flavors'][0]['name']]

        return {'info': info}