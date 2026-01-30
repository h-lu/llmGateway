"""Pytest configuration for stress tests."""
import pytest


def pytest_addoption(parser):
    """Add command line options for stress tests."""
    parser.addoption(
        "--stress-users",
        action="store",
        default=10,
        type=int,
        help="压力测试并发用户数"
    )
    parser.addoption(
        "--stress-duration",
        action="store",
        default=30,
        type=int,
        help="压力测试时长（秒）"
    )
    parser.addoption(
        "--stress-base-url",
        action="store",
        default="http://localhost:8000",
        help="网关基础 URL"
    )
