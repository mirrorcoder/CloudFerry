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

import os
import yaml

from cloudferry.lib.base.action import action
from cloudferry.lib.utils import extensions
from cloudferry.lib.utils import log

LOG = log.getLogger(__name__)

STAGES_SCENARIO = ['process', 'preparation', 'rollback']


class Scenario(object):
    def __init__(self, path_tasks, path_scenario):
        self.path_tasks = path_tasks
        self.path_scenario = path_scenario
        self.tasks = None
        self.namespace = None
        self.process = None
        self.preparation = None
        self.rollback = None
        self.raw_scenario_file = []

    def init_tasks(self, init):
        if not os.path.isfile(self.path_tasks):
            raise NotFoundTasksFileError(self.path_tasks)
        with open(self.path_tasks) as tasks_file:
            tasks_file = yaml.load(tasks_file)
            actions = {}
            for path in tasks_file['paths']:
                actions.update({e.__name__: e
                                for e in extensions.available_extensions(
                                    action.Action, path)})

            tasks = {}
            for task in tasks_file['tasks']:
                args = tasks_file['tasks'][task][1:]
                if args and isinstance(args[-1], dict):
                    args_map = args[-1]
                    args = args[:-1]
                else:
                    args_map = {}
                tasks[task] = actions[tasks_file['tasks'][task][0]](init,
                                                                    *args,
                                                                    **args_map)
            self.tasks = tasks

    def load_scenario_with_num_lines(self, path_scenario):
        self.raw_scenario_file = []
        with open(path_scenario) as scenario_file:
            self.raw_scenario_file = scenario_file.readlines()

    def load_scenario(self, path_scenario=None):
        if path_scenario is None:
            path_scenario = self.path_scenario
        if not os.path.isfile(path_scenario):
            raise NotFoundScenarioFileError(path_scenario)
        with open(path_scenario) as scenario_file:
            migrate = yaml.load(scenario_file)
            ScenarioChecker.check_structure(migrate)
            self.namespace = migrate.get('namespace', {})
            # "process" yaml chain is responsible for process
            self.process = migrate.get("process")
            # "preparation" yaml chain can be added to process pre-migration
            # tasks
            self.preparation = migrate.get("preparation")
            # "rollback" yaml chain can be added to rollback to previous state
            #                                    in case of main chain failure
            self.rollback = migrate.get("rollback")
        self.load_scenario_with_num_lines(path_scenario)

    def get_net(self):
        result = {}
        for key in STAGES_SCENARIO:
            if hasattr(self, key) and getattr(self, key):
                scenario = getattr(self, key)
                checker = ScenarioChecker(self.tasks.keys(), key, scenario,
                                          self.raw_scenario_file)
                checker.check()
                result.update({key: self.construct_net(scenario, self.tasks)})
        return result

    def construct_net(self, process, tasks):
        net = None
        for item in process:
            name, value = item.items()[0]
            elem = tasks[name] if name in tasks else None
            if isinstance(value, list):
                if isinstance(value[0], dict):
                    elem = self.construct_net(value, tasks)
                else:
                    for task in value:
                        tasks[name] = tasks[name] | tasks[task]
            if not net and value:
                net = elem
            elif value and elem:
                net = net >> elem
        return net


class ScenarioChecker():
    def __init__(self, tasks, key, scenario, raw_scenario):
        self.tasks = tasks
        self.key = key
        self.scenario = scenario
        self.missed_tasks = set()
        self.duplicated_tasks = set()
        self.missed_links = set()
        self.links = set()
        self.active_tasks = set()
        self.raw_scenario = raw_scenario

    @staticmethod
    def check_structure(body):
        if not body or not isinstance(body, dict):
            raise IncorrectScenarioStructure()
        if set(STAGES_SCENARIO).isdisjoint(body.keys()):
            raise NoStagesScenario()

    def get_lines_tasks(self, tasks):
        lines = {}
        for task in tasks:
            lines[task] = []
            for index, line in enumerate(self.raw_scenario, 1):
                if task in line:
                    lines[task].append(str(index))
        return lines

    def render_lines_to_msg(self, lines):
        render_tasks = ["%s lines: %s" % (task, ", ".join(num_lines))
                        for task, num_lines in lines.items()]
        msg_by_tasks = "\n".join(render_tasks)
        return msg_by_tasks

    def check(self):
        self.check_dict_list(self.scenario)

        # check missed links
        for link in self.links:
            if link not in self.active_tasks:
                self.missed_links.add(link)

        throw_exception = False
        # log all errors if needed
        if self.missed_links:
            lines = self.get_lines_tasks(self.missed_links)
            LOG.error("Scenario has missed links: \n %s",
                      self.render_lines_to_msg(lines))
            throw_exception = True

        if self.duplicated_tasks:
            lines = self.get_lines_tasks(self.duplicated_tasks)
            LOG.error("Scenario has duplicated tasks: \n %s",
                      self.render_lines_to_msg(lines))
            throw_exception = True

        if self.missed_tasks:
            lines = self.get_lines_tasks(self.missed_tasks)
            LOG.error("Following tasks not described in tasks.yaml: \n %s",
                      self.render_lines_to_msg(lines))
            throw_exception = True

        if throw_exception:
            raise ScenarioError(self)

    def check_string_list(self, node_list):
        for node in node_list:
            self.links.add(node)

    def check_node(self, node):
        key, value = node
        if isinstance(value, list):
            list_value = value[0]
            if isinstance(list_value, str):
                self.check_task(key)
                self.check_string_list(value)
                return
            if isinstance(list_value, dict):
                self.check_dict_list(value)
                return
            return
        if isinstance(value, bool):
            if value:
                self.check_task(key)
            return

    def check_dict_list(self, node):
        for item in node:
            dict_items = item.items()
            self.check_node(dict_items[0])

    def check_task(self, task_name):
        if task_name in self.active_tasks:
            self.duplicated_tasks.add(task_name)
        if task_name not in self.tasks:
            self.missed_tasks.add(task_name)
        self.active_tasks.add(task_name)


class ScenarioError(RuntimeError):
    def __init__(self, scenario_checker):
        self.missed_tasks = scenario_checker.missed_tasks
        self.duplicated_tasks = scenario_checker.duplicated_tasks
        self.missed_links = scenario_checker.missed_links
        super(ScenarioError, self).__init__("Not valid scenario")


class IncorrectScenarioStructure(RuntimeError):
    def __init__(self):
        super(IncorrectScenarioStructure, self)\
            .__init__("Empty or not dictonary-like strcuture")


class NoStagesScenario(RuntimeError):
    def __init__(self):
        super(NoStagesScenario, self)\
            .__init__("None of any of the basic steps for migration. "
                      "Please add stages of "
                      "migration %s" % str(STAGES_SCENARIO))


class NotFoundScenarioFileError(RuntimeError):
    def __init__(self, path):
        super(NotFoundScenarioFileError, self).__init__(
            "Not found on path %s. "
            "Make sure you specified correct config value `scenario`" % path)


class NotFoundTasksFileError(RuntimeError):
    def __init__(self, path):
        super(NotFoundTasksFileError, self).__init__(
            "Not found on path %s. Make sure you specified "
            "correct config value `tasks_mapping`" % path)
