try:
    from corehq.apps.reportfixtures.tests.test_indicator_fixture import *
except ImportError, e:
    # for some reason the test harness squashes these so log them here for clarity
    # otherwise debugging is a pain
    import logging
    logging.exception(e)
    raise
