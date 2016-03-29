# Copyright (c) 2015 Mirantis Inc.
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
from cloudferrylib.utils import log
from cloudferrylib.utils import utils
import copy

LOG = log.getLogger(__name__)
VM_STATUSES = "VM_STATUSES"


class VmSnapshotBasic(action.Action):

    """Base class that contains common to vm_snapshot methods"""

    def get_compute_resource(self):
        """returns cloudferry compute resource"""
        return self.cloud.resources[utils.COMPUTE_RESOURCE]

    @property
    def namespace_variable(self):
        """returns unique for cloud variable from namespace"""
        return '_'.join([VM_STATUSES, self.cloud.position])

    def get_similar_tenants(self):
        src_identity = self.src_cloud.resources[utils.IDENTITY_RESOURCE]
        dst_identity = self.dst_cloud.resources[utils.IDENTITY_RESOURCE]
        src_tenants = src_identity.read_info()['tenants']
        dst_tenants = {t['tenant']['name']: t['tenant']['id']
                       for t in dst_identity.read_info()['tenants']}
        similar_tenants = {}
        for ts in src_tenants:
            index = ts['tenant']['name']
            if index in dst_tenants:
                similar_tenants[ts['tenant']['id']] = dst_tenants[index]
            else:
                similar_tenants[ts['tenant']['id']] = ''
        return similar_tenants

    def get_list_of_vms(self, search_opts_tenants):
        is_dst = self.cloud.position == 'dst'
        tenants = search_opts_tenants.get('tenant_id', None)
        search_opts = search_opts_tenants.get('search_opts', {}) \
            if not is_dst else {}
        search_opts = search_opts if search_opts else {}
        search_opts.update(all_tenants=True)
        tenants_map = {}
        if is_dst and tenants:
            tenants_map = self.get_similar_tenants()
        if tenants:
            tenant_id = tenants_map[tenants[0]] if is_dst else tenants[0]
            search_opts.update(tenant_id=tenant_id)
        return self.get_compute_resource()\
            .get_instances_list(search_opts)


class VmSnapshot(VmSnapshotBasic):

    def run(self, *args, **kwargs):
        LOG.debug("creation of vm snapshots")
        # we gonna store only id and vm status in the state (for now)
        state_to_record = {}
        search_opts_tenants = kwargs.get('search_opts_tenant',
                                         {'all_tenant': True})
        for vm in self.get_list_of_vms(search_opts_tenants):
            state_to_record.update({vm.id: vm.status})
        return {
            self.namespace_variable: state_to_record,
            'rollback_vars': {
                'vms': []
            }
        }


class CheckPointVm(action.Action):
    """
    This task needs to save successfully migrated instances.
    Need for Vm Restore.

    in Namespace must be info about instance.
    """
    def __init__(self, init,
                 var_info="info"):
        self.var_info = var_info
        super(CheckPointVm, self).__init__(init)

    def run(self, rollback_vars=None, *args, **kwargs):
        info = kwargs[self.var_info]['instances']
        if not info.keys():
            return {}
        vm = info[info.keys()[0]]
        rollback_vars_local = copy.deepcopy(rollback_vars)
        success_vms = rollback_vars_local['vms']
        pair_vm = {
            'src_id': vm['old_id'] if 'old_id' in vm else '',
            'dst_id': info.keys()[0]
        }
        success_vms.append(pair_vm)
        return {
            'rollback_vars': rollback_vars_local
        }


class VmRestore(VmSnapshotBasic):

    def run(self, rollback_vars=None, *args, **kwargs):
        LOG.debug("restoring vms from snapshot")

        snapshot_from_namespace = kwargs.get(self.namespace_variable)
        compute = self.get_compute_resource()
        position = self.cloud.position
        vm_id_targets = ('src_id', 'dst_id') \
            if position == 'src' else ('dst_id', 'src_id')

        vms_succeeded = {}
        if rollback_vars:
            vms = rollback_vars.get('vms', [])
            vms_succeeded = {pair_vms[vm_id_targets[0]]: pair_vms[
                vm_id_targets[1]] for pair_vms in vms}

        search_opts_tenants = kwargs.get('search_opts_tenant',
                                         {'all_tenant': True})
        vms_cloud = self.get_list_of_vms(search_opts_tenants)
        for vm in vms_cloud:
            if vm.id in vms_succeeded:
                LOG.debug("Successfully copied instances")
                if position == 'src':
                    LOG.debug("SRC ID %s", vm.id)
                    LOG.debug("DST ID %s", vms_succeeded[vm.id])
                else:
                    LOG.debug("SRC ID %s", vms_succeeded[vm.id])
                    LOG.debug("DST ID %s", vm.id)
                continue
            if position == 'dst':
                if vm.id not in snapshot_from_namespace:
                    # delete this vm - we don't have its id in snapshot data
                    LOG.debug("VM %s will be deleted on %s", vm.id, position)
                    compute.delete_vm_by_id(vm.id)
            if position == 'src':
                if vm.status != \
                        snapshot_from_namespace.get(vm.id):
                    LOG.debug("Status of %s is changed from %s to %s on %s",
                              vm.id, vm.status,
                              snapshot_from_namespace.get(vm.id),
                              position)
                    # reset status of vm
                    compute.change_status(
                        snapshot_from_namespace.get(vm.id),
                        instance_id=vm.id)
        return {}
