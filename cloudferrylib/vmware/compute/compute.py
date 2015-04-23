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

# displayName = "ubuntu1"
# memSize = "1024"
# ----------- Split in separate category 'disk' -------------
# ethernet0.virtualDev = "vmxnet3"
# ethernet0.networkName = "VM Network"
# ethernet0.addressType = "vpx"
# ethernet0.generatedAddress = "00:50:56:8d:1e:c9"

# guestOS = "ubuntu-64"
#scsi0:0.deviceType = "scsi-hardDisk"
#scsi0:0.fileName = "CentOS.vmdk"
#scsi0:0.present = "TRUE"
# sched.swap.derivedName = "/vmfs/volumes/5510090f-229cfc1c-532e-002590a25198/ubuntu1/ubuntu1-2ef6e383.vswp"
# if numvcpus = 1 then options `numvcpus` is missing
#numvcpus = 2
__author__ = 'mirrorcoder'
from cloudferrylib.utils.ssh_util import SshUtil
from cloudferrylib.vmware.client import client
from cloudferrylib.utils import timeout_exception
import json
import time
from pyVim import connect
from pyVmomi import vmodl
from pyVmomi import vim


class ComputeVMWare:
    def __init__(self, config, cloud):
        self.config = config
        self.cloud = cloud
        self.client = client.ClientDatastore(self.config.cloud.user,
                                             self.config.cloud.password,
                                             None,
                                             self.config.cloud.auth_url)
        self.si = connect.SmartConnect(
            host=self.config.cloud.host,
            user=self.config.cloud.user,
            pwd=self.config.cloud.password,
            port=443)
        self.ssh = SshUtil(None, None, "localhost")

    def change_status(self, status, instance_id):
        search_index = self.si.content.searchIndex
        vm = search_index.FindByUuid(None, instance_id, True, True)
        if status == 'active':
            vm.PowerOn()
        if status == 'shutoff':
            vm.PowerOff()

    def wait_for_status(self, id_obj, status, limit_retry=90):
        count = 0
        search_index = self.si.content.searchIndex
        vm = search_index.FindByUuid(None, id_obj, True, True)
        if status == 'active':
            status = vim.VirtualMachinePowerState.poweredOn
        if status == 'shutoff':
            status = vim.VirtualMachinePowerState.poweredOff
        while vm.runtime.powerState != status.lower():
            time.sleep(2)
            vm = search_index.FindByUuid(None, id_obj, True, True)
            count += 1
            if count > limit_retry:
                raise timeout_exception.TimeoutException(
                    vm.runtime.powerState, status, "Timeout exp")

    def parse_cfg(self, data):
        res = {}
        for i in data.split("\n"):
            if i:
                key, value = i.split(" = ")
                res[key] = value
        return res

    def download_disk(self, user, host, dc, ds, file_obj, vm="", output=""):
        tmp = self.config.cloud.temp
        return self.client.download_to_host(user, host, dc, ds, file_obj, vm, tmp+'/'+output)

    def convert_flat_disk(self, user, host, src_path, dst_path, format_disk='qcow2'):
        tmp = self.config.cloud.temp
        cmd = 'qemu-img convert %s -O %s %s' % (src_path, format_disk, tmp+'/'+dst_path)
        self.ssh.execute(cmd, host_exec=host, user=user)

    def get_info_instance(self, dcPath, dsName, vmName):
        return self.parse_cfg(self.client.download(dcPath, dsName, "%s.vmx" % vmName, vmName))

    def read_info(self, target='instances', **kwargs):
        if target != 'instances':
            raise ValueError('Only "instances" values allowed')

        search_opts = kwargs.get('search_opts')
        info = {
            'instances': {}
        }
        for opts in search_opts:
            if not isinstance(opts, str):
                info['instances'].update(self.get(opts['dc'], opts['ds'], opts['vm']))
            else:
                info['instances'].update(self.get_by_id(opts))
        return info

    def get_by_id(self, instance_id):
        search_index = self.si.content.searchIndex
        vm = search_index.FindByUuid(None, instance_id, True, True)
        sufffix_disk_file_flat = '-flat.vmdk'
        devices = vm.config.hardware.device
        mac_addr = [dev.macAddress for dev in devices if 'macAddress' in dev.__dict__][0]
        disks = {dev.unitNumber: (dev.backing.fileName.split("]")[1].split("/")[1],
                                  
                                  dev.capacityInBytes / (1024*1024*1024),
                                  dev.backing.fileName) for dev in devices
                     if (isinstance(dev, vim.vm.device.VirtualDisk))}

        res = {vm.config.instanceUuid: {'instance': {
            'dcPath': vm.parent.parent.name,
            'dsName': vm.config.datastoreUrl[0].name,
            'vmName': vm.config.name,
            'diskFile': [disk_file_flat],
            'name': vm.config.name,
            'guestOS': vm.config.guestFullName,
            'network': [{
                            'mac': mac_addr,
                            'ip': None
                        }],
            'interfaces': [{
                'ip': None,
                'mac': mac_addr,
                'name': 'net04',
                'floatingip': None
            }],
            'security_groups': ['default'],
            'tenant_name': 'admin',
            'nics': [],
            'key_name': self.config.migrate.key_name_use,
            'flavor': None,
            'image': None,
            'boot_mode': 'image',
            'flavors': [{
                'name': "%s_flavor" % vm.config.name,
                'ram': vm.config.hardware.memoryMB,
                'vcpus': vm.config.hardware.numCPU,
                'disk': flat_size,
                'swap': vm.config.hardware.memoryMB/1024,
                'ephemeral': 0,
                'rxtx_factor': 1.0,
                'is_public': True
                        }]}}}
        return res

    def __normalize_uuid(self, in_uuid):
        _uuid = in_uuid.replace(" ", "").replace("-", "")
        part1_uuid = _uuid[:8]
        part2_uuid = _uuid[8:12]
        part3_uuid = _uuid[12:16]
        part4_uuid = _uuid[16:20]
        part5_uuid = _uuid[20:]
        return "%s-%s-%s-%s-%s" % (part1_uuid, part2_uuid, part3_uuid, part4_uuid, part5_uuid)

    def get(self, dcPath, dsName, vmName):
        data = self.get_info_instance(dcPath, dsName, vmName)
        swap_file = data['sched.swap.derivedName'].split('/')[-1].replace("\"", "")
        disk_file = data['scsi0:0.fileName'].replace("\"", "")
        disk_file_flat = "%s-flat.vmdk" % disk_file.split(".")[0]
        list_files = self.client.get_files_vm(dcPath, dsName, vmName)
        size_flat = 0
        size_swap = 0
        for f in list_files:
            if f['Name'] == disk_file_flat:
                size_flat = int(f['Size']) / (1024*1024*1024)
            if f['Name'] == swap_file:
                size_swap = int(f['Size']) / (1024*1024*1024)
        uuid = self.__normalize_uuid(data['vc.uuid'])
        res = {data['vc.uuid']: {'instance': {
            'dcPath': dcPath,
            'dsName': dsName,
            'vmName': vmName,
            'diskFile': [disk_file_flat],
            'name': data['displayName'].replace("\"", ''),
            'guestOS': data['guestOS'].replace("\"", ''),
            'network': [{
                            'mac': data['ethernet0.generatedAddress'].replace("\"", ''),
                            'ip': None
                        }],
            'interfaces': [{
                'ip': None,
                'mac': data['ethernet0.generatedAddress'].replace("\"", ''),
                'name': 'net04',
                'floatingip': None
            }],
            'security_groups': ['default'],
            'tenant_name': 'admin',
            'nics': [],
            'key_name': self.config.migrate.key_name_use,
            'flavor': None,
            'image': None,
            'boot_mode': 'image',
            'flavors': [{
                'name': "%s_flavor" % vmName.replace("\"", ''),
                'ram': int(data['memSize'].replace("\"", '')),
                'vcpus': int(data['numvcpus'].replace("\"", '')) if 'numvcpus' in data else 1,
                'disk': size_flat,
                'swap': int(data['memSize'].replace("\"", ''))/1024,
                'ephemeral': 0,
                'rxtx_factor': 1.0,
                'is_public': True
                        }]}}}
        return res