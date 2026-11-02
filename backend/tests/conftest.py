def pytest_addoption(parser):
    parser.addoption("--postgres", action="store_true", default=False,
                     help="Use temporary PostgreSQL tables for remaining-backend integration tests")
