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
import json

__author__ = 'mirrorcoder'

CHILDREN = '__children__'
PRIMITIVE_STRUCT = [dict, list, tuple, set, int,
                    float, str, long, type(None), bool, unicode]
ITERABLE_STRUCT = [dict, list, tuple, set]
SYSTEM_VARS = ['rollback_vars', 'VM_STATUSES_src', 'VM_STATUSES_dst']


class ConvertNamespace:
    def convert_obj2prim(self, obj):
        type_obj = type(obj)
        if type_obj in PRIMITIVE_STRUCT:
            if type_obj in ITERABLE_STRUCT:
                res = dict() if type_obj is dict else list()
                for elem in obj:
                    if type(obj) is dict:
                        res[elem] = self.convert_obj2prim(obj[elem])
                    else:
                        res.append(self.convert_obj2prim(elem))
                res = type_obj(res)
            else:
                res = copy.copy(obj)
        else:
            res = self.serialize(obj)
        return res

    def serialize(self, obj):
        if callable(getattr(obj, "to_serialize", None)):
            return obj.to_serialize()
        return object()

    def deserialize(self, obj, init):
        param_obj = obj.split("|")
        res = object()
        if param_obj[1] == 'init':
            cloud = "%s_cloud" % param_obj[2]
            res = init[cloud].resources[param_obj[3]]
        return res

    def convert_prim2obj(self, obj, init):
        type_obj = type(obj)
        res = None
        if type_obj in PRIMITIVE_STRUCT:
            if type_obj in ITERABLE_STRUCT:
                res = dict() if type_obj is dict else list()
                for elem in obj:
                    if type(obj) is dict:
                        res[elem] = self.convert_prim2obj(obj[elem], init)
                    else:
                        res.append(self.convert_prim2obj(elem, init))
                res = type_obj(res)
            else:
                if type_obj not in [str, unicode]:
                    res = copy.copy(obj)
                elif '<object>|' in obj:
                    res = self.deserialize(obj, init)
                else:
                    res = copy.copy(obj)
        return res


class Namespace:

    def __init__(self, vars={}, filename_snapshot="last_snapshot.snap"):
        if CHILDREN not in vars:
            vars[CHILDREN] = dict()
        self.vars = vars
        self.last_snapshot = {}
        self.fn_snap = filename_snapshot

    def fork(self, is_deep_copy=False):
        return Namespace(copy.copy(self.vars)) if not is_deep_copy \
            else Namespace(copy.deepcopy(self.vars))

    def snapshot(self, ignore=['__children__', '__init_task__',
                               '__restore__']):
        snapshot = {}
        to_primitive_cls = ConvertNamespace()
        for k, v in self.vars.iteritems():
            if k not in ignore:
                snapshot[k] = to_primitive_cls.convert_obj2prim(v)
        self.last_snapshot = snapshot
        return True

    def save_last_snapshot(self):
        with open(self.fn_snap, "w+") as f:
            f.write(json.dumps(self.last_snapshot))

    def load_last_snapshot(self):
        with open(self.fn_snap, "r+") as f:
            o = f.read()
            return json.loads(o)

    def restore(self, init, only_system_vars=False):
        from_primitive_cls = ConvertNamespace()
        o = self.load_last_snapshot()
        nm_vars = from_primitive_cls.convert_prim2obj(o, init)
        if only_system_vars:
            self.vars = {k: v
                         for k, v in nm_vars.iteritems() if k in SYSTEM_VARS}
        else:
            self.vars = nm_vars
        self.vars["__init_task__"] = init
        self.vars["__children__"] = {}
        self.snapshot()
