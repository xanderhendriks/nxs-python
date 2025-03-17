import os
import pytest

from datetime import datetime, timezone
from multiprocessing import Process, Manager, Queue
from pathlib import Path
from threading import Thread
from typing import Callable, List


def run_discovery(test_directory: str, shared_list):
    """
    Target function for test discovery to be executed in a separate process.

    Args:
        test_directory (str): Directory to search for tests.
        shared_list (ListProxy): A multiprocessing.Manager list to store test cases.
    """
    class CollectionPlugin:
        """
        A pytest plugin for collecting test cases during discovery.
        """
        def __init__(self, collected_tests):
            self.collected_tests = collected_tests

        def pytest_collectreport(self, report):
            if report.outcome == 'passed':
                for test in report.result:
                    self.collected_tests.append(test.nodeid)

    test_dir = Path(test_directory)
    if not test_dir.is_dir():
        return  # Invalid directory; no tests discovered

    pytest_args = [str(test_dir), '--collect-only', '-q']
    collected_tests = []
    result = pytest.main(pytest_args, plugins=[CollectionPlugin(collected_tests)])
    if result == 0:
        # Filter only individual test functions (exclude modules and directories)
        shared_list.extend([test for test in collected_tests if "::" in test])


def run_pytest(test_cases: List[str], extra_pytest_args: List[str], env_fields: dict, queue: Queue):
    """
    Run pytest with a custom plugin for progress tracking.
    Messages are sent to the provided queue.
    """
    class ProgressPlugin:
        def __init__(self):
            self.current_index = 0
            self.total_tests = 0

        def pytest_collection_modifyitems(self, items):
            self.total_tests = len(items)

        def pytest_runtest_protocol(self, item, nextitem):
            self.current_index += 1
            queue.put({
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'test_name': item.nodeid,
                'current_index': self.current_index,
                'total_tests': self.total_tests,
                'reason': 'running',
            })

        def pytest_runtest_logreport(self, report):
            if report.when == 'call':
                queue.put({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'test_name': report.nodeid,
                    'outcome': report.outcome,
                    'duration': report.duration,
                    'stdout': report.capstdout,
                    'stderr': report.capstderr,
                    'reason': 'completed',
                })

    os.environ.update(env_fields)
    pytest_args = ['-s', '--capture=tee-sys'] + extra_pytest_args + test_cases
    pytest.main(pytest_args, plugins=[ProgressPlugin()])


class PytestRunner:
    def __init__(self, callback: Callable[[dict], None]):
        """
        Initializes the PytestRunner.

        Args:
            callback (Callable): A function to report the test being executed,
                its index, and the total number of tests.
                Signature: callback(message: dict)
        """
        self.callback = callback
        self._running_process = None
        self._message_queue = None
        self._monitor_thread = None
        self.initialized = True

    def discover_tests(self, test_directory: str):
        """
        Discovers all test cases in the given directory in a separate process.

        Args:
            test_directory (str): Path to the directory containing test files.

        Returns:
            List[str]: List of test paths in pytest-compatible format.
        """
        # Use multiprocessing.Manager to share data between processes
        with Manager() as manager:
            shared_list = manager.list()
            discovery_process = Process(target=run_discovery, args=(test_directory, shared_list))
            discovery_process.start()
            discovery_process.join()  # Wait for the process to finish

            # Convert shared_list back to a regular list
            discovered_tests = list(shared_list)

        return discovered_tests

    def _process_queue(self):
        """
        Process messages from the queue and invoke the callback.
        Terminates when the running process finishes.
        """
        while self._running_process.is_alive() or not self._message_queue.empty():
            try:
                message = self._message_queue.get(timeout=0.5)  # Adjust timeout if needed
                self.callback(message)
            except Exception:  # Handle queue timeout or unexpected exceptions
                pass

        # Ensure all remaining messages are processed
        while not self._message_queue.empty():
            message = self._message_queue.get_nowait()
            self.callback(message)

    def start_tests(self, test_cases: List[str], env_fields: dict = None, extra_pytest_args: List[str] = None):
        """
        Start running the provided test cases in a separate process and handle messages in a thread.

        This method initializes a multiprocessing process to execute pytest with the provided test cases.
        A separate thread monitors a message queue for test progress updates and passes them to the callback
        function. The thread stops automatically when the test process completes.

        Args:
            test_cases (List[str]): A list of pytest-compatible test case identifiers to run.
                Example: ['test_module.py::test_function'].
            env_fields (dict, optional): Environment variables to be set for the test process.
                Defaults to None.
            extra_pytest_args (List[str], optional): Additional arguments to pass to pytest.
                Example: ['--maxfail=2', '--verbose']. Defaults to None.

        Raises:
            RuntimeError: If tests are already running when this function is called.
        """
        if self._running_process and self._running_process.is_alive():
            raise RuntimeError('Tests are already running.')

        extra_pytest_args = extra_pytest_args or []
        env_fields = env_fields or {}

        self._message_queue = Queue()
        self._running_process = Process(
            target=run_pytest,
            args=(test_cases, extra_pytest_args, env_fields, self._message_queue),
        )
        self._running_process.start()

        # Start a thread to monitor the queue
        self._monitor_thread = Thread(target=self._process_queue)
        self._monitor_thread.start()

    def stop_tests(self):
        """
        Stop the running tests by terminating the process.
        """
        if self._running_process and self._running_process.is_alive():
            self._running_process.terminate()
            self._running_process.join()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join()

        self.callback({'timestamp': datetime.now(timezone.utc).isoformat(), 'reason': 'cancelled'})
