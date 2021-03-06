#  Copyright 2015-2020 SWIM.AI inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import asyncio
import inspect

from collections.abc import Callable
from abc import abstractmethod, ABC
from typing import TYPE_CHECKING, Any

from swimai.recon import Recon
from swimai.structures import Absent, Value, Bool, Num, Text, RecordConverter
from swimai.warp import SyncRequest, CommandMessage, Envelope, LinkRequest
from ..utils import URI
from .downlink_utils import before_open, UpdateRequest, RemoveRequest, convert_to_async

# Imports for type annotations
if TYPE_CHECKING:
    from ..swim_client import SwimClient
    from ..connections import DownlinkManager


class DownlinkModel(ABC):

    def __init__(self, client: 'SwimClient') -> None:
        self.client = client
        self.host_uri = None
        self.node_uri = None
        self.lane_uri = None
        self.task = None
        self.connection = None
        self.linked = asyncio.Event()
        self.downlink_manager = None

    def open(self) -> 'DownlinkModel':
        self.task = self.client.schedule_task(self.connection.wait_for_messages)
        return self

    def close(self) -> 'DownlinkModel':
        self.client.schedule_task(self.__close)
        return self

    async def __close(self) -> None:
        self.task.cancel()

    async def receive_message(self, message: 'Envelope') -> None:
        if message.tag == 'linked':
            await self.receive_linked()
        elif message.tag == 'synced':
            await self.receive_synced()
        elif message.tag == 'event':
            await self.receive_event(message)
        elif message.tag == 'unlinked':
            await self.receive_unlinked(message)

    async def receive_linked(self):
        self.linked.set()

    async def receive_unlinked(self, message: 'Envelope') -> None:
        if message.body.tag == 'laneNotFound':
            raise Exception(f'Lane "{self.lane_uri}" was not found on the remote agent!')

    @abstractmethod
    async def receive_synced(self):
        raise NotImplementedError

    @abstractmethod
    async def receive_event(self, message: 'Envelope'):
        raise NotImplementedError

    @abstractmethod
    async def establish_downlink(self) -> None:
        raise NotImplementedError


class DownlinkView(ABC):

    def __init__(self, client: 'SwimClient') -> None:
        self.client = client
        self.host_uri = None
        self.node_uri = None
        self.lane_uri = None
        self.is_open = False
        self.connection = None
        self.model = None
        self.downlink_manager = None

        self.__registered_classes = dict()
        self.__deregister_classes = set()
        self.__strict = False

    @property
    def route(self) -> str:
        return f'{self.node_uri}/{self.lane_uri}'

    @before_open
    def set_host_uri(self, host_uri: str) -> 'DownlinkView':
        self.host_uri = URI.normalise_warp_scheme(host_uri)
        return self

    @before_open
    def set_node_uri(self, node_uri: str) -> 'DownlinkView':
        self.node_uri = node_uri
        return self

    @before_open
    def set_lane_uri(self, lane_uri: str) -> 'DownlinkView':
        self.lane_uri = lane_uri
        return self

    def open(self) -> 'DownlinkView':
        if not self.is_open:
            self.is_open = True
            self.client.schedule_task(self.client.add_downlink_view, self)

        return self

    def close(self) -> 'DownlinkView':

        if self.is_open:
            self.is_open = False
            self.client.schedule_task(self.client.remove_downlink_view, self)

        return self

    @property
    def registered_classes(self) -> dict:
        if self.downlink_manager is None:
            return self.__registered_classes
        else:
            return self.downlink_manager.registered_classes

    @property
    def strict(self) -> bool:
        if self.downlink_manager is None:
            return self.__strict
        else:
            return self.downlink_manager.strict

    @strict.setter
    def strict(self, strict: bool) -> None:
        if self.downlink_manager is not None:
            self.downlink_manager.strict = self.__strict
        else:
            self.__strict = strict

    def register_classes(self, classes_list: list) -> None:
        for custom_class in classes_list:
            self.__register_class(custom_class)

    def register_class(self, custom_class: Any) -> None:
        self.__register_class(custom_class)

    def deregister_all_classes(self) -> None:
        if self.downlink_manager is not None:
            self.__deregister_classes.update(set(self.downlink_manager.registered_classes.keys()))
            self.downlink_manager.registered_classes.clear()
        else:
            self.__registered_classes.clear()

    def deregister_classes(self, classes_list: list) -> None:
        for custom_class in classes_list:
            self.deregister_class(custom_class)

    def deregister_class(self, custom_class: Any) -> None:
        if self.downlink_manager is not None:
            self.downlink_manager.registered_classes.pop(custom_class.__name__, None)
        else:
            self.__registered_classes.pop(custom_class.__name__, None)
            self.__deregister_classes.add(custom_class.__name__)

    def __register_class(self, custom_class: Any) -> None:
        try:
            custom_class()

            if self.downlink_manager is not None:
                self.downlink_manager.registered_classes[custom_class.__name__] = custom_class
            else:
                self.__registered_classes[custom_class.__name__] = custom_class
                self.__deregister_classes.discard(custom_class.__name__)

        except Exception:
            raise Exception(
                f'Class {custom_class.__name__} must have a default constructor or default values for all arguments!')

    async def assign_manager(self, manager: 'DownlinkManager') -> None:
        self.model = manager.downlink_model
        manager.registered_classes.update(self.registered_classes)
        manager.strict = self.strict
        self.downlink_manager = manager

    async def initalise_model(self, downlink_manager: 'DownlinkManager', model: 'DownlinkModel') -> None:
        downlink_manager.registered_classes = self.registered_classes
        downlink_manager.strict = self.strict
        model.downlink_manager = downlink_manager
        model.host_uri = self.host_uri
        model.node_uri = self.node_uri
        model.lane_uri = self.lane_uri

    @staticmethod
    def validate_callback(callback: 'Callable') -> 'Callable':

        if not inspect.iscoroutinefunction(callback) and isinstance(callback, Callable):
            callback = convert_to_async(callback)

        if inspect.iscoroutinefunction(callback):
            return callback
        else:
            raise TypeError('Callback must be a coroutine or a function!')

    @abstractmethod
    async def register_manager(self, manager: 'DownlinkManager') -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_downlink_model(self, downlink_manager: 'DownlinkManager') -> 'DownlinkModel':
        raise NotImplementedError


class EventDownlinkModel(DownlinkModel):

    async def establish_downlink(self) -> None:
        link_request = LinkRequest(self.node_uri, self.lane_uri)
        await self.connection.send_message(await link_request.to_recon())

    async def receive_synced(self):
        raise TypeError('Event downlink does not support synced responses!')

    async def receive_event(self, message: Envelope):

        if message.body == Absent.get_absent():
            event = Value.absent()
        elif isinstance(message.body, (Text, Num, Bool)):
            event = message.body
        else:
            converter = RecordConverter.get_converter()
            event = converter.record_to_object(message.body, self.downlink_manager.registered_classes,
                                               self.downlink_manager.strict)

        await self.downlink_manager.subscribers_on_event(event)


class EventDownlinkView(DownlinkView):

    def __init__(self, client: 'SwimClient') -> None:
        super().__init__(client)
        self.on_event_callback = None

    async def register_manager(self, manager: 'DownlinkManager') -> None:
        await self.assign_manager(manager)

    async def create_downlink_model(self, downlink_manager: 'DownlinkManager') -> 'DownlinkModel':
        model = EventDownlinkModel(self.client)
        await self.initalise_model(downlink_manager, model)
        return model

    # noinspection PyAsyncCall
    async def execute_on_event(self, event: Any) -> None:
        if self.on_event_callback:
            self.client.schedule_task(self.on_event_callback, event)

    def on_event(self, function: Callable) -> 'EventDownlinkView':
        self.on_event_callback = self.validate_callback(function)
        return self


class ValueDownlinkModel(DownlinkModel):

    def __init__(self, client: 'SwimClient') -> None:
        super().__init__(client)
        self.value = Value.absent()
        self.synced = asyncio.Event()

    async def establish_downlink(self) -> None:
        """
        Send a `sync` request in order to initiate a connection to a lane from the remote agent.
        """
        sync_request = SyncRequest(self.node_uri, self.lane_uri)
        await self.connection.send_message(await sync_request.to_recon())

    async def receive_synced(self):
        self.synced.set()

    async def receive_event(self, message: 'Envelope') -> None:
        await self.__set_value(message)

    async def send_message(self, message: 'Envelope') -> None:
        """
        Send a message to the remote agent of the downlink.

        :param message:         - Message to send to the remote agent.
        """
        await self.linked.wait()
        await self.connection.send_message(await message.to_recon())

    async def get_value(self) -> Any:
        """
        Get the value of the downlink after it has been synced.

        :return:                - The current value of the downlink.
        """
        await self.synced.wait()
        return self.value

    async def __set_value(self, message: 'Envelope') -> None:
        """
        Set the value of the the downlink and trigger the `did_set` callback of the downlink subscribers.

        :param message:        - The message from the remote agent.
        :return:
        """
        old_value = self.value

        if message.body == Absent.get_absent():
            self.value = Value.absent()
        elif isinstance(message.body, (Text, Num, Bool)):
            self.value = message.body
        else:
            converter = RecordConverter.get_converter()
            self.value = converter.record_to_object(message.body, self.downlink_manager.registered_classes,
                                                    self.downlink_manager.strict)

        await self.downlink_manager.subscribers_did_set(self.value, old_value)


class ValueDownlinkView(DownlinkView):

    def __init__(self, client: 'SwimClient') -> None:
        super().__init__(client)
        self.did_set_callback = None
        self.initialised = asyncio.Event()

    async def register_manager(self, manager: 'DownlinkManager') -> None:
        await self.assign_manager(manager)

        if manager.is_open:
            await self.execute_did_set(self.model.value, Value.absent())

        self.initialised.set()

    async def create_downlink_model(self, downlink_manager: 'DownlinkManager') -> 'ValueDownlinkModel':
        model = ValueDownlinkModel(self.client)
        await self.initalise_model(downlink_manager, model)
        return model

    def did_set(self, function: Callable) -> 'ValueDownlinkView':
        self.did_set_callback = self.validate_callback(function)
        return self

    @property
    def value(self) -> 'Any':
        if self.model is None:
            return Value.absent()
        else:
            return self.model.value

    async def __get_value(self) -> 'Any':
        await self.initialised.wait()
        return await self.model.get_value()

    def get(self, wait_sync: bool = False) -> Any:
        """
        Return the value of the downlink.

        :param wait_sync:       - If True, wait for the initial `sync` to be completed before returning.
                                  If False, return immediately.
        :return:                - The value of the Downlink.
        """
        if self.is_open:
            if wait_sync:
                task = self.client.schedule_task(self.__get_value)
                return task.result()
            else:
                return self.value
        else:
            raise RuntimeError('Link is not open!')

    def set(self, value: Any, blocking: bool = False) -> None:
        """
        Send a command message to set the value of the lane on the remote agent to the given value.

        :param blocking:        - If True, block until the value has been sent to the server.
        :param value:           - New value for the lane of the remote agent.
        """
        if self.is_open:
            task = self.client.schedule_task(self.send_message, value)

            if blocking:
                task.result()

        else:
            raise RuntimeError('Link is not open!')

    # noinspection PyAsyncCall
    async def execute_did_set(self, current_value: Any, old_value: Any) -> None:
        """
        Execute the custom `did_set` callback of the current downlink view.

        :param current_value:       - The new value of the downlink.
        :param old_value:           - The previous value of the downlink.
        """
        if self.did_set_callback:
            self.client.schedule_task(self.did_set_callback, current_value, old_value)

    async def send_message(self, value: Any) -> None:
        """
        Send a message to the remote agent of the downlink.

        :param value:           - New value for the lane of the remote agent.
        """
        await self.initialised.wait()

        recon = RecordConverter.get_converter().object_to_record(value)
        message = CommandMessage(self.node_uri, self.lane_uri, recon)

        await self.model.send_message(message)


class MapDownlinkModel(DownlinkModel):

    def __init__(self, client: 'SwimClient') -> None:
        super().__init__(client)
        self.map = {}
        self.synced = asyncio.Event()

    async def establish_downlink(self) -> None:
        """
        Send a `sync` request in order to initiate a connection to a lane from the remote agent.
        """
        sync_request = SyncRequest(self.node_uri, self.lane_uri)
        await self.connection.send_message(await sync_request.to_recon())

    async def receive_synced(self):
        self.synced.set()

    async def receive_event(self, message: 'Envelope'):
        if message.body.tag == 'update':
            await self.__receive_update(message)
        if message.body.tag == 'remove':
            await self.__receive_remove(message)

    async def __receive_update(self, message: 'Envelope') -> None:
        key = RecordConverter.get_converter().record_to_object(message.body.get_head().value.get_head().value,
                                                               self.downlink_manager.registered_classes,
                                                               self.downlink_manager.strict)

        value = RecordConverter.get_converter().record_to_object(message.body.get_body(),
                                                                 self.downlink_manager.registered_classes,
                                                                 self.downlink_manager.strict)

        recon_key = await Recon.to_string(message.body.get_head().value.get_head().value)
        old_value = self.map.get(recon_key, [Value.absent()])[0]

        self.map[recon_key] = (key, value)
        await self.downlink_manager.subscribers_did_update(key, value, old_value)

    async def __receive_remove(self, message: 'Envelope') -> None:
        key = RecordConverter.get_converter().record_to_object(message.body.get_head().value.get_head().value,
                                                               self.downlink_manager.registered_classes,
                                                               self.downlink_manager.strict)

        recon_key = await Recon.to_string(message.body.get_head().value.get_head().value)
        old_value = self.map.pop(recon_key, [Value.absent()])[0]

        await self.downlink_manager.subscribers_did_remove(key, old_value)

    async def send_message(self, message: 'Envelope') -> None:
        """
        Send a message to the remote agent of the downlink.

        :param message:         - Message to send to the remote agent.
        """
        await self.linked.wait()
        await self.connection.send_message(await message.to_recon())

    async def get_value(self, key=None) -> Any:
        """
        Get the value of the downlink after it has been synced.

        :return:                - The current value of the downlink.
        """
        await self.synced.wait()

        if key is None:
            return self.map.values()
        else:
            return self.map.get(key, [Value.absent()])[0]


class MapDownlinkView(DownlinkView):

    def __init__(self, client: 'SwimClient') -> None:
        super().__init__(client)
        self.did_update_callback = None
        self.did_remove_callback = None
        self.initialised = asyncio.Event()

        self.did_update_callback = None

    async def register_manager(self, manager: 'DownlinkManager') -> None:
        await self.assign_manager(manager)

        if manager.is_open:
            for key, value in self.model.map:
                await self.execute_did_update(key, value, Value.absent())

        self.initialised.set()

    async def create_downlink_model(self, downlink_manager: 'DownlinkManager') -> 'MapDownlinkModel':
        model = MapDownlinkModel(self.client)
        await self.initalise_model(downlink_manager, model)
        return model

    def map(self, key: Any) -> [Value, dict]:
        if self.model is None:
            return Value.absent()
        else:
            if key is None:
                return self.model.map.values()
            else:
                return self.model.map.get(key, Value.absent())

    async def __get_value(self, key: Any) -> Any:
        await self.initialised.wait()
        return await self.model.get_value(key)

    def get(self, key: Any = None, wait_sync: bool = False) -> Any:
        if self.is_open:
            if wait_sync:
                task = self.client.schedule_task(self.__get_value, key)
                return task.result()
            else:
                return self.map(key)
        else:
            raise RuntimeError('Link is not open!')

    def put(self, key: Any, value: Any, blocking: bool = False) -> None:
        """
        Send a command message to put the given key and value in the remote map lane.

        :param key:             - Entry key.
        :param value:           - Entry value.
        :param blocking:        - If True, block until the value has been sent to the server.
        """
        if self.is_open:
            task = self.client.schedule_task(self.put_message, key, value)

            if blocking:
                task.result()

        else:
            raise RuntimeError('Link is not open!')

    def remove(self, key: Any, blocking: bool = False) -> None:
        """
        Send a command message to remove the given key from the remote map lane.

        :param key:             - Entry key.
        :param blocking:        - If True, block until the value has been sent to the server.
        """
        if self.is_open:
            task = self.client.schedule_task(self.remove_message, key)

            if blocking:
                task.result()

        else:
            raise RuntimeError('Link is not open!')

    async def put_message(self, key: Any, value: Any) -> None:
        """
        Send a message to the remote agent of the downlink.

        :param key:             - Key for the new entry in the map lane of the remote agent.
        :param value:           - Value for the new entry in the map lane of the remote agent.
        """
        await self.initialised.wait()

        message = CommandMessage(self.node_uri, self.lane_uri, UpdateRequest(key, value).to_record())
        await self.model.send_message(message)

    async def remove_message(self, key: Any) -> None:
        await self.initialised.wait()

        message = CommandMessage(self.node_uri, self.lane_uri, RemoveRequest(key).to_record())
        await self.model.send_message(message)

    # noinspection PyAsyncCall
    async def execute_did_update(self, key: Any, new_value: Any, old_value: Any) -> None:
        if self.did_update_callback:
            self.client.schedule_task(self.did_update_callback, key, new_value, old_value)

    # noinspection PyAsyncCall
    async def execute_did_remove(self, key: Any, old_value: Any) -> None:
        if self.did_remove_callback:
            self.client.schedule_task(self.did_remove_callback, key, old_value)

    def did_update(self, function: Callable) -> 'MapDownlinkView':
        self.did_update_callback = self.validate_callback(function)
        return self

    def did_remove(self, function: Callable) -> 'MapDownlinkView':
        self.did_remove_callback = self.validate_callback(function)
        return self
