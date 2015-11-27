# Copyright 2015: Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


import collections
from cloudferrylib.base.action import action
from cloudferrylib.utils import utils

LOG = utils.get_log(__name__)


class FilterSimilarVMs(action.Action):
    """
    Exclude src instances from migration workflow if they exists on dst or if
    they ip's overlaps with dst instances ip's. Also looking
    for similar tenants.
    """
    def run(self, **kwargs):
        filter_instances = kwargs.get('search_opts', {})
        sim_inst = self.get_similar_instances(filter_instances)
        return {
            'similar_instances': sim_inst
        }

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

    def get_instances(self, cloud, search_opts={}):
        compute = cloud.resources[utils.COMPUTE_RESOURCE]
        instances = compute.read_info('instances',
                                      search_opts=
                                      search_opts)['instances']
        return instances

    def get_similar_instances(self, instances):
        src_instances = self.get_instances(self.src_cloud, instances)
        dst_instances = self.get_instances(self.dst_cloud)
        dst_instances_restruct = {
            utils.Instance(
                di): di
            for index, di in dst_instances.iteritems()}
        similar_tenants = self.get_similar_tenants()
        similar_instances = []
        for v, k in dst_instances_restruct.iteritems():
            LOG.debug("Instance DST: %s ", k)
        for index, si in src_instances.iteritems():
            src_signs = utils.Instance(si)
            LOG.debug("Check source instance: %s", si['instance'])
            if src_signs in dst_instances_restruct.keys():
                LOG.debug("Check tenants instances....")
                sign = [k for k in dst_instances_restruct.keys()
                        if src_signs == k]
                if len(sign) > 1:
                    LOG.warning("!!Two or more similar instances!!")
                di = dst_instances_restruct[sign[0]]
                src_ten = si['instance']['tenant_id']
                dst_ten = di['instance']['tenant_id']
                LOG.debug("Tenant instance on src %s ", src_ten)
                LOG.debug("Tenant instance on dst %s ", dst_ten)
                if src_ten in similar_tenants:
                    if similar_tenants[src_ten] != dst_ten:
                        continue
                LOG.debug("Detect similar instance")
                similar_instances.append(di)
        return similar_instances
