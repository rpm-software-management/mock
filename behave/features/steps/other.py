""" Generic testing steps """

import glob
import importlib
import json
import os
import shutil
import tempfile

from hamcrest import (
    assert_that,
    contains_string,
    ends_with,
    equal_to,
    has_item,
    has_entries,
    has_length,
    not_,
)
import jsonschema
from behave import given, when, then  # pylint: disable=no-name-in-module

from testlib import no_output, run

# flake8: noqa
# pylint: disable=missing-function-docstring,function-redefined
# mypy: disable-error-code="no-redef"


def _first_int(string, max_lines=20):
    for line in string.split("\n")[:max_lines]:
        if not line:
            continue
        first_word = line.split()[0]
        if first_word.isdigit():
            return first_word
    raise Exception("unexpected dnf history output")


def add_cleanup_last_transaction(context):
    # TODO: DNF5 support https://github.com/rpm-software-management/dnf5/issues/140
    dnf = ["sudo", "/usr/bin/dnf-3", "-y", "history"]
    _, out, _ = run(dnf + ["list"])
    transaction_id = _first_int(out)

    def _revert_transaction(_context):
        cmd = dnf + ["undo", transaction_id]
        assert_that(run(cmd)[0], equal_to(0))

    context.add_cleanup(_revert_transaction, context)

@given(u'an unique mock namespace')
def step_impl(context):
    print("using uniqueext {}".format(context.uniqueext))
    context.uniqueext_used = True


@given(u'the {package} package {state} installed on host')
def step_impl(context, package, state):
    """
    Install the package, and uninstall in post- action.  If state is "not", then
    just check it is not installed.
    """
    is_installed, _, _ = run(["rpm", "-q", package])
    # exit_status 0 => installed
    is_installed = bool(not is_installed)

    if "not" in state:
        if not is_installed:
            return  # nothing to do

        # Remove the package and schedule its removal
        cmd = ["sudo", "dnf", "-y", "remove", package]
        assert_that(run(cmd)[0], equal_to(0))
        # schedule removal
        add_cleanup_last_transaction(context)
        return

    if is_installed:
        return

    # install the package, and schedule removal
    def _uninstall_pkg(_context):
        cmd = ["sudo", "dnf", "-y", "remove", package]
        assert_that(run(cmd)[0], equal_to(0))

    cmd = ["sudo", "dnf", "-y", "install", package]
    assert_that(run(cmd)[0], equal_to(0))
    context.add_cleanup(_uninstall_pkg, context)


def _mock_cleanup(context):
    with no_output():
        context.mock.clean()


@given(u'pre-intitialized chroot')
def step_impl(context):
    context.mock.init()
    context.add_cleanup(_mock_cleanup, context)


@given(u'a custom third-party repository is used for builds')
def step_impl(context):
    context.add_repos.append(
        "https://raw.githubusercontent.com/rpm-software-management/"
        "mock-test-data/main/repo/"
    )


@given("a created local repository")
def step_impl(context):
    context.local_repo = tempfile.mkdtemp(prefix="mock-tests-local-repo-")
    run(["createrepo_c", context.local_repo])


@given(u'the local repo contains a "{rpm}" RPM')
def step_impl(context, rpm):
    rpm = context.download_rpm(rpm)
    shutil.move(rpm, context.local_repo)
    run(["createrepo_c", context.local_repo])


@given("the local repo is used for builds")
def step_impl(context):
    context.add_repos.append(context.local_repo)


@when(u'a build is depending on third-party repo requested')
@when(u'a build which requires the "always-installable" RPM is requested')
def step_impl(context):
    local_file = context.download_rpm("buildrequires-always-installable")
    context.mock.rebuild([local_file])


@then(u'the build succeeds')
def step_impl(context):
    assert os.path.exists(context.mock.resultdir)
    rpms = glob.glob(os.path.join(context.mock.resultdir, "*.rpm"))
    print("Found RPMs: " + ", ".join(rpms))
    assert_that(rpms, has_item(ends_with(".src.rpm")))
    assert_that(rpms, has_item(not_(ends_with(".src.rpm"))))


@when('mock is run with "{options}" options')
def step_impl(context, options):
    options = options.split()
    context.last_cmd = run(['mock'] + options)


@given('mock is always executed with "{options}"')
def step_impl(context, options):
    options = options.split()
    context.mock.common_opts += options


@then('the exit code is {code}')
def step_impl(context, code):
    code = int(code)
    assert_that(context.last_cmd[0], equal_to(code))


@then('the one-liner error contains "{expected_message}"')
def step_impl(context, expected_message):
    err = context.last_cmd[2].splitlines()
    assert_that(err, has_length(1))
    assert_that(err[0], contains_string(expected_message))


@when('an online source RPM is rebuilt')
def step_impl(context):
    url = context.test_storage + "mock-test-bump-version-1-0.src.rpm"
    context.mock.rebuild([url])


@then('{output} contains "{text}"')
def step_impl(context, output, text):
    index = 1 if output == "stdout" else 2
    real_output = context.last_cmd[index]
    assert_that(real_output, contains_string(text))


@when('{call} method from {module} is called with {args} args')
def step_impl(context, call, module, args):
    imp = importlib.import_module(module)
    method = getattr(imp, call)
    args = args.split()
    context.last_method_call_retval = method(*args)


@then('the return value contains a field "{field}={value}"')
def step_impl(context, field, value):
    assert_that(context.last_method_call_retval[field],
                equal_to(value))


@when('deps for {srpm} are calculated against {chroot}')
def step_impl(context, srpm, chroot):
    url = context.test_storage + srpm
    context.mock.calculate_deps(url, chroot)


@when('a local repository is created from lockfile')
def step_impl(context):
    mock_run = context.mock_runs["calculate-build-deps"][-1]
    lockfile = mock_run["lockfile"]

    context.local_repo = tempfile.mkdtemp(prefix="mock-tests-local-repo-")
    cmd = ["mock-isolated-repo", "--lockfile", lockfile, "--output-repo",
           context.local_repo]
    assert_that(run(cmd)[0], equal_to(0))


@when('an isolated build is retriggered with the lockfile and repository')
def step_impl(context):
    context.mock.isolated_build()


@then('the produced lockfile is validated properly')
def step_impl(context):
    mock_run = context.mock_runs["calculate-build-deps"][-1]
    lockfile = mock_run["lockfile"]
    with open(lockfile, "r", encoding="utf-8") as fd:
        lockfile_data = json.load(fd)

    assert_that(lockfile_data["buildroot"]["rpms"],
                has_item(has_entries({"name": "filesystem"})))

    schemafile = os.path.join(os.path.dirname(__file__), '..', '..', '..',
                              "mock", "docs",
                              "buildroot-lock-schema-1.0.0.json")
    with open(schemafile, "r", encoding="utf-8") as fd:
        schema = json.load(fd)

    jsonschema.validate(lockfile_data, schema)


@given('next mock call uses {option} option')
def step_impl(context, option):
    context.next_mock_options.append(option)
