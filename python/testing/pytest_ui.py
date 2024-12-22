from .pytest_runner import PytestRunner
from collections import defaultdict
from nicegui import ui
from typing import Callable


class PytestUI():
    def __init__(self, stepper, test_path, callback: Callable[[dict], None]):
        self.stepper = stepper
        self.test_path = test_path
        self.callback = callback

        self.pytest_runner = PytestRunner(self.test_callback)
        test_cases = self.pytest_runner.discover_tests(self.test_path)

        grouped_tests = defaultdict(list)
        for test_case in test_cases:
            test_case_fields = test_case.split('.py::')
            module_name = test_case_fields[0]
            test_name = test_case_fields[1]
            grouped_tests[module_name].append({'id': f'{module_name}.py::{test_name}', 'label': test_name})

        self.test_cases_tree_list = [{'id': 'test_cases', 'label': 'test cases', 'children': [{'id': module, 'label': module, 'children': children} for module, children in grouped_tests.items()]}]

        self.ui_elements()

    def test_callback(self, message: dict):
        if message.get('reason') == 'running':
            print(f"{message['timestamp']}: Running test {message['current_index']}/{message['total_tests']}: {message['test_name']}")
        elif message.get('reason') == 'completed':
            print(f"{message['timestamp']}: Test {message['test_name']} finished with result: {message}")
            self.test_results_table.rows[self.test_index]['result'] = message['outcome']
            self.test_results_table.update()
            print(self.test_index, self.test_total)
            self.test_index += 1
            if self.test_index == self.test_total:
                self.done_button.enable()
        elif message.get('reason') == 'error':
            print(f"{message['timestamp']}: Error: {message['stderror']}")
        elif message.get('reason') == 'cancelled':
            print(f"{message['timestamp']}: Test run was cancelled.")
        elif message.get('reason') == 'log':
            print(f"{message['timestamp']}: {message['stdout']}")

    def execute_tests(self):
        """
        Executes the tests that have been ticked in the test_cases_tree.
        """
        self.stepper.next()
        self.done_button.disable()
        self.test_results_table.style("background-color: white")
        self.test_results_log.clear()

        # Retrieve selected test cases using the `ticks` attribute
        selected_test_cases = self.test_cases_tree._props['ticked']

        # Filter only valid test cases (not folders or non-test items)
        selected_test_cases = [test_case for test_case in selected_test_cases if "::" in test_case]
        self.test_total = len(selected_test_cases)

        if not selected_test_cases:
            print("No test cases selected.")
            return

        # Prepare rows for the results table
        rows = [{'test_case': test_case, 'result': '-'} for test_case in selected_test_cases]
        self.test_results_table.rows = rows

        # Reset test execution state
        self.test_index = 0
        self.end_result = 'Passed'

        # Start the tests
        self.pytest_runner.start_tests([str(self.test_path / x) for x in selected_test_cases])

    def cancel_back(self):
        self.pytest_runner.stop_tests()
        self.stepper.previous()

    def ui_elements(self):
        with ui.step('Select tests'):
            self.test_cases_tree = ui.tree(self.test_cases_tree_list, tick_strategy='leaf') # , on_tick=on_tick_test_cases)
            self.test_cases_tree.expand(['test_cases'])
            self.test_cases_tree.tick()

            with ui.stepper_navigation():
                self.execute_button = ui.button('Execute test', on_click=lambda: self.execute_tests())
                self.back_button = ui.button('Back', on_click=lambda: self.callback({'reason': 'back'}))
        with ui.step('Execute tests'):
            columns = [
                {'name': 'test_case', 'label': 'Test case', 'field': 'test_case', 'required': True, 'align': 'left'},
                {'name': 'result', 'label': 'Result', 'field': 'result', 'sortable': True},
            ]
            self.test_results_table = ui.table(columns=columns, rows=[], row_key='name')
            self.test_results_log = ui.log().classes('max-w-full h-40')

            with ui.stepper_navigation():
                self.done_button = ui.button('Done', on_click=lambda: self.callback({'reason': 'done'}))
                self.cancel_back_button = ui.button('Cancel/Back', on_click=lambda: self.cancel_back())
