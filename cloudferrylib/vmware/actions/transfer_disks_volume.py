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
from cloudferrylib.utils.ssh_util import SshUtil


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


class TransferDisksVolume(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        src_cloud = self.src_cloud
        dst_cloud = self.dst_cloud
        computeVMWare = src_cloud.resources[utl.COMPUTE_RESOURCE]
        volume_resource = dst_cloud.resources[utl.STORAGE_RESOURCE]
        image_resource = dst_cloud.resources[utl.IMAGE_RESOURCE]
        cfg = self.dst_cloud.cloud_config.cloud
        ssh = SshUtil(None, None, "localhost")
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            # Task Transport Disk
            for unit, disk in data['disks'].items():
                computeVMWare.download_disk('root',
                                            dst_cloud.getIpSsh(),
                                            data['dcPath'],
                                            data['dsName'],
                                            disk['fileName-flat'],
                                            data['vmName'],
                                            disk['fileName-flat'])
                computeVMWare.convert_flat_disk(None,
                                                dst_cloud.getIpSsh(),
                                                disk['fileName-flat'],
                                                "%s.img" % disk['fileName-flat'])
                cmd = ("glance --os-username=%s --os-password=%s --os-tenant-name=%s " +
                       "--os-auth-url=%s " +
                       "image-create --name %s --disk-format=%s --container-format=bare --file %s| " +
                       "grep id") %\
                  (cfg.user,
                   cfg.password,
                   cfg.tenant,
                   cfg.auth_url,
                   data['vmName'] + '.img',
                   'qcow2',
                   cfg.temp+'/'+"%s.img" % disk['fileName-flat'])
                image_id = ssh.execute(cmd, host_exec=cfg.host, user='root').split("|")[2].replace(' ', '')
                volume_id = volume_resource.create_volume(disk['size'],
                                                          display_name=data['vmName'] + '.img',
                                                          imageRef=image_id).id
                volume_resource.wait_for_status(volume_id, 'available')
                image_resource.delete_image(image_id)
                inst['meta']['volume'].append({
                    'volume': {
                        'id': volume_id,
                        'device': "/dev/vd"+chr(ord('b') + unit)
                    }
                })
        return {'info': info}