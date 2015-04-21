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


class TransportInstance(action.Action):
    # TODO constants

    def run(self, info=None, **kwargs):
        dst_cloud = self.dst_cloud
        compute = dst_cloud.resources['compute']
        for (id_inst, inst) in info['instances'].iteritems():
            data = inst['instance']
            data['id'] = compute.create_instance(**{'name': data['name'],
                                                    'flavor': data['flavor'],
                                                    'key_name': data['key_name'],
                                                    'nics': data['nics'],
                                                    'image': data['image']})
        return {'info': info}