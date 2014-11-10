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


from cloudferrylib.base import storage
from cinderclient.v1 import client as cinder_client
from cloudferrylib.utils import mysql_connector
from fabric.api import settings
from fabric.api import run
import time

AVAILABLE = 'available'
IN_USE = "in-use"


class CinderStorage(storage.Storage):

    """
    The main class for working with Openstack cinder client
    """

    def __init__(self, config, cloud):
        self.config = config
        self.host = config.cloud.host
        self.cloud = cloud
        self.identity_client = cloud.resources['identity']
        self.cinder_client = self.get_cinder_client(self.config)
        super(CinderStorage, self).__init__(config)

    def get_cinder_client(self, params):

        """ Getting cinder client """

        return cinder_client.Client(
            params.cloud.user,
            params.cloud.password,
            params.cloud.tenant,
            "http://%s:35357/v2.0/" % params.cloud.host)

    def read_info(self, **kwargs):
        info = dict(resource=self, storage={})
        info['storage'] = {'volumes': {}}
        for vol in self.get_volumes_list(search_opts=kwargs):
            volume = {
                'id': vol.id,
                'size': vol.size,
                'display_name': vol.display_name,
                'display_description': vol.display_description,
                'volume_type': (
                    None if vol.volume_type == u'None' else vol.volume_type),
                'availability_zone': vol.availability_zone,
                'device': vol.attachments[0][
                    'device'] if vol.attachments else None,
                'bootable': True if vol.bootable.lower() == 'true' else False,
            }
            info['storage']['volumes'][vol.id] = {'volume': volume,
                                                  'meta': {
                                                      'image': None
                                                  }}
        if self.config['migrate']['keep_volume_storage']:
            info['storage']['volumes_db'] = \
                {'volumes': '/tmp/volumes'}
            for table_name, file_name in info['storage']['volumes_db'].iteritems():
                self.download_table_from_db_to_file(table_name, file_name)
        return info

    def convert(self, vol):
        info = {
            'size': vol['volume']['size'],
            'display_name': vol['volume']['display_name'],
            'display_description': vol['volume']['display_description'],
            'volume_type': vol['volume']['volume_type'],
            'availability_zone': vol['volume']['availability_zone'],
        }
        if 'image' in vol['meta']:
            if vol['meta']['image']:
                info['imageRef'] = vol['meta']['image']['id']
        return info

    def deploy(self, info):
        if info['storage']['volumes_db']:
            for table_name, file_name in info['storage']['volumes_db'].iteritems():
                self.upload_table_to_db(table_name, file_name)
            for tenant in info['identity']['tenants']:
                self.update_column_with_condition('volumes',
                                                  'project_id',
                                                  tenant['tenant']['id'],
                                                  tenant['meta']['new_id'])
            for user in info['identity']['users']:
                self.update_column_with_condition('volumes', 'user_id', user['user']['id'], user['meta']['new_id'])
            self.update_column_with_condition('volumes', 'attach_status', 'attached', 'detached')
            self.update_column_with_condition('volumes', 'status', 'in-use', 'available')
            self.update_column('volumes', 'instance_uuid', 'NULL')
            volumes = self.get_volumes_list(
                search_opts={'all_tenants': True})
            return volumes
        volumes = []
        for vol in info['storage']['volumes'].itervalues():
            vol_for_deploy = self.convert(vol)
            volume = self.create_volume(**vol_for_deploy)
            vol['volume']['id'] = volume.id
            self.wait_for_status(volume.id, AVAILABLE)
            self.finish(vol)
            volumes.append(volume)
        return volumes

    def attach_volume_to_instance(self, volume_info):
        if 'instance' in volume_info['meta']:
            if volume_info['meta']['instance']:
                self.attach_volume(volume_info['volume']['id'],
                                   volume_info['meta']['instance']['id'],
                                   volume_info['volume']['device'])
                self.wait_for_status(volume_info['volume']['id'], IN_USE)

    def get_volumes_list(self, detailed=True, search_opts=None):
        return self.cinder_client.volumes.list(detailed, search_opts)

    def create_volume(self, size, **kwargs):
        return self.cinder_client.volumes.create(size, **kwargs)

    def delete_volume(self, volume_id):
        volume = self.__get_volume_by_id(volume_id)
        self.cinder_client.volumes.delete(volume)

    def __get_volume_by_id(self, volume_id):
        return self.cinder_client.volumes.get(volume_id)

    def update_volume(self, volume_id, **kwargs):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.update(volume, **kwargs)

    def attach_volume(self, volume_id, instance_id, mountpoint, mode='rw'):
        volume = self.__get_volume_by_id(volume_id)
        return self.cinder_client.volumes.attach(volume,
                                                 instance_uuid=instance_id,
                                                 mountpoint=mountpoint,
                                                 mode=mode)

    def detach_volume(self, volume_id):
        return self.cinder_client.volumes.detach(volume_id)

    def finish(self, vol):
        self.__patch_option_bootable_of_volume(vol['volume']['id'],
                                               vol['volume']['bootable'])

    def __patch_option_bootable_of_volume(self, volume_id, bootable):
        cmd = ('use cinder;update volumes set volumes.bootable=%s where '
               'volumes.id="%s"') % (int(bootable), volume_id)
        self.__cmd_mysql_on_dest_controller(cmd)

    def __cmd_mysql_on_dest_controller(self, cmd):
        with settings(host_string=self.host):
            run('mysql %s %s -e \'%s\'' % (
                ("-u " + self.config['mysql']['user'])
                if self.config['mysql']['user'] else "",
                "-p" + self.config['mysql']['password']
                if self.config['mysql']['password'] else "",
                cmd))

    def upload_volume_to_image(self, volume_id, force, image_name,
                               container_format, disk_format):
        volume = self.__get_volume_by_id(volume_id)
        resp, image = self.cinder_client.volumes.upload_to_image(
            volume=volume,
            force=force,
            image_name=image_name,
            container_format=container_format,
            disk_format=disk_format)
        return resp, image['os-volume_upload_image']['image_id']

    def wait_for_status(self, id_res, status):
        while self.cinder_client.volumes.get(id_res).status != status:
            time.sleep(1)

    def download_table_from_db_to_file(self, table_name, file_name):
        connector = mysql_connector.MysqlConnector(self.config.mysql, 'cinder')
        connector.execute("SELECT * FROM %s INTO OUTFILE '%s';" % (table_name, file_name))

    def upload_table_to_db(self, table_name, file_name):
        connector = mysql_connector.MysqlConnector(self.config.mysql, 'cinder')
        connector.execute(("LOAD DATA INFILE '%s' INTO TABLE %s") % (file_name, table_name))

    def update_column_with_condition(self, table_name, column,
                                     old_value, new_value):

        connector = mysql_connector.MysqlConnector(self.config.mysql, 'cinder')
        connector.execute(("UPDATE %s SET %s='%s' WHERE %s='%s'") %
                          (table_name, column, new_value, column, old_value))

    def update_column(self, table_name, column_name, new_value):
        connector = mysql_connector.MysqlConnector(self.config.mysql, 'cinder')
        connector.execute(("UPDATE %s SET %s='%s'") % (table_name, column_name, new_value))
