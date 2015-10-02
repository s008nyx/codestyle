#!/usr/bin/env python
"""Code style checker application"""

from __future__ import absolute_import
import os
import sys
import argparse

import checkers
from utils import check_external_deps, DependencyError, import_class
import settings


class Application(object):
    """
    Codestyle checker application
    """

    CHECKERS = (
        ('.php', checkers.PHPChecker),
        ('.js', checkers.JSChecker),
        ('.py', checkers.PythonChecker),
        (('.css', '.less'), checkers.LessChecker)
    )

    def __init__(self, settings):
        self.settings = settings
        self.params = None
        self.checkers = None

    def create_checkers(self):
        self.checkers = {}
        for ext, checker_class in self.CHECKERS:
            if not issubclass(checker_class, checkers.BaseChecker):
                raise TypeError('expected BaseChecker subclass')
            checker_instance = checker_class(application=self)
            if isinstance(ext, (list, tuple)):
                for ex in ext:
                    self.checkers[ex] = checker_instance
            else:
                self.checkers[ext] = checker_instance

    def get_checker(self, ext):
        if self.checkers is None:
            self.create_checkers()
        return self.checkers.get(ext, None)

    def get_config_path(self, filename):
        """
        Get path of the config file by name
        """

        return os.path.join(self.get_standard_dir(), filename)

    def parse_cmd_args(self):
        """
        Get parsed command line arguments
        """

        parser = argparse.ArgumentParser(
            description='Check and fix code style')
        parser.add_argument('target', metavar='target', type=str, nargs='+',
                            help='files for checking')
        parser.add_argument('-i', '--try-fix', dest='fix', action='store_true',
                            help='Auto fix codestyle errors', default=False)
        parser.add_argument('-c', '--compact', dest='compact',
                            action='store_true', help='Show compact output',
                            default=False)
        parser.add_argument('-s', '--standard', dest='standard', type=str,
                            help='Path to the coding standard directory',
                            default=self.settings.DEFAULT_STANDARD_DIR,
                            metavar='standard-dir')
        return parser.parse_args()

    def get_standard_dir(self):
        """
        Get coding standard directory path
        """

        return self.params.standard

    def log(self, string, newline=True, file=sys.stdout):
        """
        Log message to STDOUT
        """

        if newline:
            string += '\n'
        file.write(string)

    def log_error(self, string, newline=True):
        """
        Log error message (to STDERR)
        """

        self.log(string, newline, sys.stderr)

    def exit_with_error(self, message, retcode=1):
        """
        Put error message to STDERR and exit
        """

        self.log_error("%s: %s" % (sys.argv[0], message))
        sys.exit(retcode)

    def process_file(self, path):
        """Process file to check or keep it"""

        checker = self.get_checker(os.path.splitext(path)[1])
        if checker is None:
            return None

        if self.params.compact:
            self.log("Checking: " + path + "...", False)

        result = checker.check(path)

        if self.params.compact:
            if result.is_success():
                self.log(" OK")
            else:
                self.log(" Fail")
        else:
            if result.output:
                self.log("\n")

        if self.params.fix:
            if self.params.compact:
                self.log("Trying fix errors...")
            try:
                fix_result = checker.fix(path)
                if self.params.compact:
                    if fix_result.is_success():
                        self.log("Some errors has been fixed\n")
                    else:
                        self.log("Cannot fix errors\n")
            except NotImplementedError:
                self.log_error(
                    "Auto fixing is not supported for this language\n"
                )

        return result

    def process_dir(self, path):
        """
        Check code in directory (recursive)
        """

        for root, subdirs, files in os.walk(path):
            for subfile in files:
                yield self.process_file(os.path.join(root, subfile))

    def process_path(self, path):
        """
        Check file or directory (recursive)
        """

        if not os.path.exists(path):
            self.exit_with_error("no such file or directory: " + path)
        elif os.path.isfile(path):
            yield self.process_file(path)
        elif os.path.isdir(path):
            for result in self.process_dir(path):
                yield result

    def run(self):
        """
        Run code checking
        """

        self.params = self.parse_cmd_args()

        try:
            check_external_deps()
        except DependencyError as e:
            self.log_error(str(e))
            sys.exit(1)

        total_success = 0
        total_failed = 0

        for path in self.params.target:
            for result in self.process_path(path):
                if result is not None:
                    if result.is_success():
                        total_success += 1
                    else:
                        total_failed += 1

        self.log("Total success: %d" % total_success)
        self.log("Total failed: %s" % total_failed)

        if total_failed > 0:
            return False
        return True


if __name__ == "__main__":
    app = Application(settings)
    if app.run() is False:
        sys.exit(1)
