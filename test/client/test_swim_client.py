#  Copyright 2015-2019 SWIM.AI inc.
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
import unittest
from concurrent.futures.thread import ThreadPoolExecutor
from threading import Thread
from unittest.mock import patch

from aiounittest import async_test
from swimai.client.downlinks import ValueDownlinkView
from swimai.structures import Text
from test.utils import mock_async_callback, mock_sync_callback, MockWebsocketConnect, MockWebsocket, MockAsyncFunction
from swimai import SwimClient


class TestSwimClient(unittest.TestCase):

    def setUp(self):
        MockWebsocket.clear()

    def test_swim_client_start(self):
        # Given
        client = SwimClient()
        # When
        actual = client.start()
        # Then
        self.assertEqual(actual, client)
        self.assertIsInstance(actual.loop, asyncio.events.AbstractEventLoop)
        self.assertIsInstance(actual.loop_thread, Thread)
        self.assertFalse(actual.loop.is_closed())
        self.assertTrue(actual.loop_thread.is_alive())
        self.assertIsNone(actual.executor)
        client.stop()

    def test_swim_client_stop(self):
        # Given
        client = SwimClient()
        client.start()
        # When
        actual = client.stop()
        # Then
        self.assertEqual(client, actual)
        self.assertIsInstance(actual.loop, asyncio.events.AbstractEventLoop)
        self.assertIsInstance(actual.loop_thread, Thread)
        self.assertTrue(actual.loop.is_closed())
        self.assertFalse(actual.loop_thread.is_alive())
        self.assertIsNone(actual.executor)

    def test_swim_client_with_statement(self):
        # When
        with SwimClient() as swim_client:
            # Then
            self.assertIsInstance(swim_client, SwimClient)
            self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
            self.assertIsInstance(swim_client.loop_thread, Thread)
            self.assertFalse(swim_client.loop.is_closed())

        self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
        self.assertIsInstance(swim_client.loop_thread, Thread)
        self.assertTrue(swim_client.loop.is_closed())
        self.assertFalse(swim_client.loop_thread.is_alive())
        self.assertIsNone(swim_client.executor)

    @patch('builtins.print')
    @patch('traceback.print_tb')
    def test_swim_client_with_statement_exception_no_handler(self, mock_print_tb, mock_print):
        # When
        with SwimClient() as swim_client:
            # Then
            self.assertIsInstance(swim_client, SwimClient)
            self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
            self.assertIsInstance(swim_client.loop_thread, Thread)
            self.assertFalse(swim_client.loop.is_closed())
            self.assertTrue(swim_client.loop_thread.is_alive())

            swim_client.task_with_exception = lambda: (_ for _ in ()).throw(Exception,
                                                                            Exception('Mock exception in task'))

            swim_client.task_with_exception()

        mock_print.assert_called_once()
        mock_print_tb.assert_called_once()
        self.assertEqual('Mock exception in task', mock_print.call_args_list[0][0][0].args[0])
        self.assertTrue(swim_client.loop.is_closed())
        self.assertFalse(swim_client.loop_thread.is_alive())
        self.assertIsNone(swim_client.executor)

    @patch('builtins.print')
    @patch('traceback.print_tb')
    @patch('os._exit')
    def test_swim_client_with_statement_exception_terminate(self, mock_exit, mock_print_tb, mock_print):
        # When
        with SwimClient(terminate_on_exception=True) as swim_client:
            # Then
            self.assertIsInstance(swim_client, SwimClient)
            self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
            self.assertFalse(swim_client.loop.is_closed())
            self.assertIsInstance(swim_client.loop_thread, Thread)
            self.assertTrue(swim_client.loop_thread.is_alive())

            swim_client.task_with_exception = lambda: (_ for _ in ()).throw(Exception,
                                                                            Exception('Mock exception in task'))

            swim_client.task_with_exception()

        self.assertTrue(swim_client.loop.is_closed())
        self.assertEqual('Mock exception in task', mock_print.call_args_list[0][0][0].args[0])
        mock_print_tb.assert_called_once()
        mock_print.assert_called_once()
        mock_exit.assert_called_once_with(1)
        self.assertFalse(swim_client.loop_thread.is_alive())
        self.assertIsNone(swim_client.executor)

    @patch('builtins.print')
    @patch('traceback.print_tb')
    def test_swim_client_with_statement_exception_async_callback(self, mock_print_tb, mock_print):
        # Given
        mock_callback = mock_async_callback
        # When
        with SwimClient(execute_on_exception=mock_callback) as swim_client:
            # Then
            self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
            self.assertIsInstance(swim_client, SwimClient)
            self.assertTrue(swim_client.loop_thread.is_alive())
            self.assertFalse(swim_client.loop.is_closed())
            self.assertIsInstance(swim_client.loop_thread, Thread)

            swim_client.task_with_exception = lambda: (_ for _ in ()).throw(Exception,
                                                                            Exception('Mock exception in task'))

            swim_client.task_with_exception()

        self.assertEqual('Mock exception in task', mock_print.call_args_list[0][0][0].args[0])
        self.assertEqual('Mock async callback', mock_print.call_args_list[1][0][0])
        self.assertEqual(2, mock_print.call_count)
        mock_print_tb.assert_called_once()
        self.assertTrue(swim_client.loop.is_closed())
        self.assertFalse(swim_client.loop_thread.is_alive())
        self.assertIsNone(swim_client.executor)

    @patch('builtins.print')
    @patch('traceback.print_tb')
    def test_swim_client_with_statement_exception_sync_callback(self, mock_print_tb, mock_print):
        # Given
        mock_callback = mock_sync_callback
        # When
        with SwimClient(execute_on_exception=mock_callback) as swim_client:
            # Then
            self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
            self.assertTrue(swim_client.loop_thread.is_alive())
            self.assertIsInstance(swim_client, SwimClient)
            self.assertFalse(swim_client.loop.is_closed())
            self.assertIsInstance(swim_client.loop_thread, Thread)

            swim_client.task_with_exception = lambda: (_ for _ in ()).throw(Exception,
                                                                            Exception('Mock exception in task'))

            swim_client.task_with_exception()

        self.assertEqual('Mock sync callback', mock_print.call_args_list[1][0][0])
        self.assertEqual('Mock exception in task', mock_print.call_args_list[0][0][0].args[0])
        self.assertEqual(2, mock_print.call_count)
        self.assertTrue(swim_client.loop.is_closed())
        mock_print_tb.assert_called_once()
        self.assertFalse(swim_client.loop_thread.is_alive())
        self.assertIsInstance(swim_client.executor, ThreadPoolExecutor)

    @patch('builtins.print')
    @patch('traceback.print_tb')
    @patch('os._exit')
    def test_swim_client_with_statement_exception_callback_and_terminate(self, mock_exit, mock_print_tb, mock_print):
        # Given
        mock_callback = mock_async_callback
        # When
        with SwimClient(terminate_on_exception=True, execute_on_exception=mock_callback) as swim_client:
            # Then
            self.assertIsInstance(swim_client, SwimClient)
            self.assertIsInstance(swim_client.loop, asyncio.events.AbstractEventLoop)
            self.assertFalse(swim_client.loop.is_closed())
            self.assertTrue(swim_client.loop_thread.is_alive())
            self.assertIsInstance(swim_client.loop_thread, Thread)

            swim_client.task_with_exception = lambda: (_ for _ in ()).throw(Exception,
                                                                            Exception('Mock exception in task'))

            swim_client.task_with_exception()

        mock_exit.assert_called_once_with(1)
        self.assertTrue(swim_client.loop.is_closed())
        self.assertEqual('Mock exception in task', mock_print.call_args_list[0][0][0].args[0])
        mock_print_tb.assert_called_once()
        mock_print.assert_called_once()
        self.assertIsNone(swim_client.executor)
        self.assertFalse(swim_client.loop_thread.is_alive())

    @patch('websockets.connect', new_callable=MockWebsocketConnect)
    def test_swim_client_command(self, mock_websocket_connect):
        # Given
        host_uri = 'ws://localhost:9001'
        node_uri = 'moo'
        lane_uri = 'cow'
        expected = '@command(node:moo,lane:cow)"Hello, World!"'
        with SwimClient() as swim_client:
            # When
            swim_client.command(host_uri, node_uri, lane_uri, Text.create_from('Hello, World!'))
        # Then
        mock_websocket_connect.assert_called_once_with(host_uri)
        self.assertEqual(expected, MockWebsocket.get_mock_websocket().sent_messages[0])

    def test_swim_client_downlink_value(self):
        # Given
        with SwimClient() as swim_client:
            # When
            downlink_view = swim_client.downlink_value()

        # Then
        self.assertIsInstance(downlink_view, ValueDownlinkView)
        self.assertEqual(downlink_view.client, swim_client)

    @patch('swimai.client.connections.ConnectionPool.add_downlink_view', new_callable=MockAsyncFunction)
    @async_test
    async def test_swim_client_add_downlink_view(self, mock_add_downlink):
        # Given
        host_uri = 'ws://localhost:9001'
        node_uri = 'moo'
        lane_uri = 'cow'

        MockWebsocket.get_mock_websocket().messages_to_send.append('@synced(node:"moo",lane:"cow")')

        with SwimClient() as swim_client:
            downlink_view = swim_client.downlink_value()
            downlink_view.host_uri = host_uri
            downlink_view.node_uri = node_uri
            downlink_view.lane_uri = lane_uri
            # When
            await swim_client.add_downlink_view(downlink_view)

        # Then
        mock_add_downlink.assert_called_once_with(downlink_view)

    @patch('swimai.client.connections.ConnectionPool.add_downlink_view', new_callable=MockAsyncFunction)
    @patch('swimai.client.connections.ConnectionPool.remove_downlink_view', new_callable=MockAsyncFunction)
    @async_test
    async def test_swim_client_remove_downlink_view(self, mock_remove_downlink, mock_add_downlink):
        # Given
        host_uri = 'ws://localhost:9001'
        node_uri = 'moo'
        lane_uri = 'cow'

        MockWebsocket.get_mock_websocket().messages_to_send.append('@synced(node:"moo",lane:"cow")')

        with SwimClient() as swim_client:
            downlink_view = swim_client.downlink_value()
            downlink_view.host_uri = host_uri
            downlink_view.node_uri = node_uri
            downlink_view.lane_uri = lane_uri
            await swim_client.add_downlink_view(downlink_view)
            # When
            await swim_client.remove_downlink_view(downlink_view)

        # Then
        mock_add_downlink.assert_called_once_with(downlink_view)
        mock_remove_downlink.assert_called_once_with(downlink_view)

    @patch('swimai.client.connections.ConnectionPool.get_connection', new_callable=MockAsyncFunction)
    @async_test
    async def test_swim_client_get_connection(self, mock_get_connection):
        # Given
        host_uri = 'ws://localhost:9001'
        node_uri = 'moo'
        lane_uri = 'cow'

        MockWebsocket.get_mock_websocket().messages_to_send.append('@synced(node:"moo",lane:"cow")')

        with SwimClient() as swim_client:
            downlink_view = swim_client.downlink_value()
            downlink_view.host_uri = host_uri
            downlink_view.node_uri = node_uri
            downlink_view.lane_uri = lane_uri
            # When
            await swim_client.get_connection(host_uri)

        # Then
        mock_get_connection.assert_called_once_with(host_uri)
