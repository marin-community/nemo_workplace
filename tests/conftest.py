# Copyright The Marin Authors
# SPDX-License-Identifier: Apache-2.0

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--container-image",
        help="Run server transport tests in this already-built Docker image",
    )


@pytest.fixture
def container_image(request):
    return request.config.getoption("--container-image")
