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

__author__ = 'mirrorcoder'

from scheduler.Scheduler import Scheduler, NO_ERROR
from tests import test
from oslotest import mockpatch
import mock
from scheduler import Scheduler as ModuleScheduler


class SchedulerTestCase(test.TestCase):
    def setUp(self):
        super(SchedulerTestCase, self).setUp()
        self.fake_cursor = mock.MagicMock()
        self.cursor_patch = mockpatch.PatchObject(ModuleScheduler, 'Cursor',
                                                  new=self.fake_cursor)
        self.useFixture(self.cursor_patch)

        self.fake_process = mock.MagicMock()
        self.process_patch = mockpatch.PatchObject(ModuleScheduler, 'Process',
                                                   new=self.fake_process)
        self.useFixture(self.process_patch)
        self.fake_wrap_tt = mock.MagicMock()
        self.fake_wrap_tt.__name__ = 'WrapThreadTask'
        self.wrap_tt_patch = mockpatch.PatchObject(ModuleScheduler, 'WrapThreadTask',
                                                   new=self.fake_wrap_tt)
        self.useFixture(self.wrap_tt_patch)
        self.fake_base_task = mock.MagicMock()
        self.fake_base_task.__name__ = 'BaseTask'
        self.wrap_base_task = mockpatch.PatchObject(ModuleScheduler, 'BaseTask',
                                                    new=self.fake_base_task)
        self.useFixture(self.wrap_base_task)
        self.fake_namespace = mock.MagicMock()
        self.wrap_namespace = mockpatch.PatchObject(ModuleScheduler, 'Namespace',
                                                    new=self.fake_namespace)
        self.useFixture(self.wrap_namespace)

    def test_start_scheduler(self):
        fake_cursor = [self.fake_base_task(), self.fake_wrap_tt(), self.fake_base_task()]
        scheduler = Scheduler(cursor=fake_cursor)
        scheduler.event_start_task = mock.Mock()
        scheduler.event_start_task.return_value = True
        scheduler.event_end_task = mock.Mock()
        scheduler.start()
        self.assertEqual(NO_ERROR, scheduler.status_error)
        self.assertIsNotNone(scheduler.event_start_task.call_args)
        self.assertIn(fake_cursor[0], scheduler.event_start_task.call_args[0])
        self.assertIsNotNone(scheduler.event_end_task.call_args)
        self.assertIn(fake_cursor[0], scheduler.event_end_task.call_args[0])
        self.assertTrue(fake_cursor[0].called)
        self.assertTrue(fake_cursor[2].called)

